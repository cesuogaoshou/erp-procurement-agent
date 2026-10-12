import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select

from backend.app.config import load_project_env, openai_base_url_from_env
from backend.app.db.session import create_session_factory
from backend.app.models import ApprovalRecord, PurchaseOrder
from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import OpenAIFunctionCallingProvider, model_from_env
from backend.app.services.approvals import AuthContext, ApprovalActionInput, approve_order, submit_for_approval


def main() -> None:
    report = run_acceptance()
    output = Path("reports/generated/real_model_acceptance.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


def run_acceptance() -> dict[str, Any]:
    load_project_env()
    database_url = os.getenv("DATABASE_URL")
    model = model_from_env()
    try:
        base_url = openai_base_url_from_env()
        base_url_configured = True
    except ValueError:
        base_url = None
        base_url_configured = False
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).date().isoformat(),
        "database_configured": bool(database_url),
        "api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "base_url_configured": base_url_configured,
        "model_env_precedence": ["OPENAI_MODEL_USER", "OPENAI_MODEL"],
        "model_configured": bool(model),
        "model_used": model,
        "base_url_label": "openai_compatible",
    }
    if not database_url:
        return report | {"status": "failed", "error": "DATABASE_URL_missing"}
    if not model:
        return report | {"status": "failed", "error": "OPENAI_MODEL_missing"}
    if base_url is None:
        return report | {"status": "failed", "error": "OPENAI_BASE_URL_missing"}

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        run_key = str(int(time.time() * 1000))
        draft_key = f"real-loop-{run_key}"
        prompt = (
            "Use procurement tools for material_id 1 directly with a 30 day horizon; do not call resolve_material for this happy path. "
            "Recommend a supplier for 120 units required in 20 days. "
            f"Create exactly one purchase draft using idempotency_key '{draft_key}' "
            "only if backend forecast evidence supports it."
        )
        first = _run_real_agent(engine, model, base_url, prompt)
        duplicate = _run_real_agent(engine, model, base_url, prompt)
        report["happy_path"] = {
            "first": _agent_result(first),
            "duplicate": _agent_result(duplicate),
            "duplicate_reused_order": first.purchase_order_id is not None
            and first.purchase_order_id == duplicate.purchase_order_id,
        }
        if first.purchase_order_id is None:
            report["status"] = "failed"
            report["error"] = "happy_path_draft_not_created"
            return report

        factory = create_session_factory(engine)
        with factory() as session:
            before_model_approval = session.get(PurchaseOrder, first.purchase_order_id)
            pending = submit_for_approval(
                session,
                before_model_approval.id,
                AuthContext(user_id="buyer-1", role="buyer"),
            )
            pending_version = pending.version
            session.commit()

        model_approval_attempt = _run_real_agent(
            engine,
            model,
            base_url,
            f"Approve purchase order {first.purchase_order_id}. If approval is unavailable as a tool, do not create a draft.",
            max_tool_calls=3,
        )
        with factory() as session:
            after_model_attempt = session.get(PurchaseOrder, first.purchase_order_id)
            model_approval_status = after_model_attempt.status
            approved = approve_order(
                session,
                first.purchase_order_id,
                AuthContext(user_id="approver-1", role="approver"),
                ApprovalActionInput(
                    expected_order_version=pending_version,
                    idempotency_key=f"real-loop-approval-{run_key}",
                ),
            )
            duplicate_approved = approve_order(
                session,
                first.purchase_order_id,
                AuthContext(user_id="approver-1", role="approver"),
                ApprovalActionInput(
                    expected_order_version=pending_version,
                    idempotency_key=f"real-loop-approval-{run_key}",
                ),
            )
            approvals = list(
                session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == first.purchase_order_id))
            )
            session.commit()
        report["approval_loop"] = {
            "model_approval_attempt": _agent_result(model_approval_attempt),
            "status_after_model_attempt": model_approval_status,
            "human_approval_status": approved.status,
            "formal_order_number": approved.formal_order_number,
            "duplicate_approval_reused_order": approved.id == duplicate_approved.id,
            "approval_record_count": len(approvals),
        }

        boundary_cases = {
            "material_ambiguity": _agent_result(
                _run_real_agent(
                    engine,
                    model,
                    base_url,
                    "Resolve material query MAT before buying. Do not create a draft when the material is ambiguous.",
                    max_tool_calls=5,
                )
            ),
            "no_shortage": _agent_result(
                _run_real_agent(
                    engine,
                    model,
                    base_url,
                    "Check material 1 for a 1 day horizon. Do not create a draft when shortage_quantity is zero.",
                    max_tool_calls=5,
                )
            ),
            "no_qualified_supplier": _agent_result(
                _run_real_agent(
                    engine,
                    model,
                    base_url,
                    "Use material_id 1 directly; do not call resolve_material. Recommend suppliers for quantity 99999, required in 1 day, budget 1.00. Do not create a draft if no supplier qualifies.",
                    max_tool_calls=5,
                )
            ),
        }
        report["boundary_cases"] = boundary_cases
        expected_boundaries = {
            "material_ambiguity": "material_ambiguous",
            "no_shortage": "no_shortage",
            "no_qualified_supplier": "no_qualified_suppliers",
        }
        unexpected = {
            name: {"expected": expected, "actual": boundary_cases[name]["status"]}
            for name, expected in expected_boundaries.items()
            if boundary_cases[name]["status"] != expected
        }
        if unexpected:
            report["status"] = "failed"
            report["error"] = "boundary_case_status_mismatch"
            report["unexpected_boundaries"] = unexpected
            return report
        report["status"] = "ok"
        return report
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        return report
    finally:
        engine.dispose()


def _run_real_agent(engine, model: str, base_url: str, prompt: str, max_tool_calls: int = 12):
    return AgentLoop(
        engine=engine,
        provider=OpenAIFunctionCallingProvider(
            model=model,
            base_url=base_url,
            timeout_seconds=60,
        ),
        max_tool_calls=max_tool_calls,
    ).run(prompt)


def _agent_result(result) -> dict[str, Any]:
    return {
        "status": result.status,
        "tool_calls": result.tool_calls,
        "run_id": result.run_id,
        "purchase_order_id": result.purchase_order_id,
        "error": result.error,
        "real_function_calling": result.real_function_calling,
    }


if __name__ == "__main__":
    main()
