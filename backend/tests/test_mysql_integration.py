import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from backend.app.db.session import create_session_factory
from backend.app.models import AgentRun, ApprovalRecord, AuditLog, PurchaseOrder, ToolTrace
from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import MockLLMProvider, ToolCall
from backend.app.services.approvals import (
    AuthContext,
    ApprovalActionInput,
    approve_order,
    submit_for_approval,
)
from backend.app.services.purchase_drafts import DraftItemInput, PurchaseDraftInput, create_purchase_draft


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MYSQL_INTEGRATION") != "1",
    reason="set RUN_MYSQL_INTEGRATION=1 to run MySQL integration checks",
)


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is not configured")
    if not url.startswith(("mysql://", "mysql+pymysql://")):
        pytest.skip("DATABASE_URL is not a MySQL connection")
    return url


@pytest.fixture()
def mysql_engine():
    engine = create_engine(_database_url(), pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


def test_mysql_approval_concurrency_rollback_and_agent_persistence(mysql_engine):
    run_key = str(int(time.time() * 1000))
    report: dict[str, object] = {"run_key": run_key}
    factory = create_session_factory(mysql_engine)

    with factory() as session:
        order = create_purchase_draft(
            session,
            PurchaseDraftInput(
                supplier_id=1,
                items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
                idempotency_key=f"mysql-concurrency-{run_key}",
                evidence_refs=["recommendation:mysql-integration"],
            ),
        )
        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))
        order_id = pending.id
        expected_version = pending.version
        session.commit()

    def approve_once(actor_suffix: str) -> dict[str, str]:
        local_factory = create_session_factory(mysql_engine)
        with local_factory() as session:
            try:
                approved = approve_order(
                    session,
                    order_id,
                    AuthContext(user_id=f"approver-{actor_suffix}", role="approver"),
                    ApprovalActionInput(
                        expected_order_version=expected_version,
                        idempotency_key=f"mysql-concurrent-approve-{run_key}-{actor_suffix}",
                    ),
                )
                session.commit()
                return {"status": "approved", "order_status": approved.status}
            except Exception as exc:
                session.rollback()
                return {"status": "conflict", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result() for future in as_completed([executor.submit(approve_once, "a"), executor.submit(approve_once, "b")])]

    with factory() as session:
        stored = session.get(PurchaseOrder, order_id)
        approvals = list(session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == order_id)))
        audits = list(session.scalars(select(AuditLog).where(AuditLog.order_id == order_id)))

    assert sorted(outcome["status"] for outcome in outcomes) == ["approved", "conflict"]
    assert stored.status == "approved"
    assert stored.formal_order_number == f"PO-{order_id:06d}"
    assert len(approvals) == 1
    assert [audit.action for audit in audits].count("approved") == 1
    report["approval_concurrency"] = {
        "order_id": order_id,
        "outcomes": outcomes,
        "approval_records": len(approvals),
        "audit_actions": [audit.action for audit in audits],
    }

    with factory() as session:
        rollback_order = create_purchase_draft(
            session,
            PurchaseDraftInput(
                supplier_id=1,
                items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
                idempotency_key=f"mysql-rollback-{run_key}",
                evidence_refs=["recommendation:mysql-integration"],
            ),
        )
        rollback_pending = submit_for_approval(session, rollback_order.id, AuthContext(user_id="buyer-1", role="buyer"))
        rollback_order_id = rollback_pending.id
        rollback_version = rollback_pending.version
        session.commit()

    with factory() as session:
        with pytest.raises(RuntimeError, match="forced rollback after flush"):
            approve_order(
                session,
                rollback_order_id,
                AuthContext(user_id="approver-rollback", role="approver"),
                ApprovalActionInput(
                    expected_order_version=rollback_version,
                    idempotency_key=f"mysql-rollback-approve-{run_key}",
                ),
            )
            raise RuntimeError("forced rollback after flush")
        session.rollback()

    with factory() as session:
        rollback_stored = session.get(PurchaseOrder, rollback_order_id)
        rollback_records = list(session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == rollback_order_id)))
        rollback_audits = list(session.scalars(select(AuditLog).where(AuditLog.order_id == rollback_order_id)))

    assert rollback_stored.status == "pending_approval"
    assert rollback_stored.version == rollback_version
    assert rollback_records == []
    assert [audit.action for audit in rollback_audits] == ["submitted_for_approval"]
    report["rollback"] = {
        "order_id": rollback_order_id,
        "status": rollback_stored.status,
        "approval_records": len(rollback_records),
        "audit_actions": [audit.action for audit in rollback_audits],
    }

    agent_result = AgentLoop(
        engine=mysql_engine,
        provider=MockLLMProvider(
            [
                ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 30}),
                ToolCall(
                    "recommend_suppliers",
                    {"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000.00"},
                ),
                ToolCall(
                    "create_purchase_draft",
                    {
                        "supplier_id": 1,
                        "items": [{"material_id": 1, "quantity": "120"}],
                        "idempotency_key": f"mysql-agent-draft-{run_key}",
                        "evidence_refs": ["use_latest_forecast", "recommendation:mysql-integration"],
                    },
                ),
            ]
        ),
    ).run("Need 120 units of material 1 within 20 days")
    assert agent_result.status == "draft_created"

    with factory() as session:
        pending_agent_order = submit_for_approval(
            session,
            agent_result.purchase_order_id,
            AuthContext(user_id="buyer-1", role="buyer"),
        )
        session.commit()

    mysql_engine.dispose()
    restarted_engine = create_engine(_database_url(), pool_pre_ping=True)
    try:
        restarted_factory = create_session_factory(restarted_engine)
        with restarted_factory() as session:
            stored_run = session.get(AgentRun, agent_result.run_id)
            traces = list(session.scalars(select(ToolTrace).where(ToolTrace.run_id == agent_result.run_id).order_by(ToolTrace.step_index)))
            stored_order = session.get(PurchaseOrder, agent_result.purchase_order_id)
    finally:
        restarted_engine.dispose()

    assert stored_run.status == "draft_created"
    assert [trace.tool_name for trace in traces] == [
        "get_demand_forecast",
        "recommend_suppliers",
        "create_purchase_draft",
    ]
    assert stored_order.status == "pending_approval"
    assert pending_agent_order.status == "pending_approval"
    report["agent_persistence"] = {
        "run_id": agent_result.run_id,
        "purchase_order_id": agent_result.purchase_order_id,
        "run_status": stored_run.status,
        "trace_tools": [trace.tool_name for trace in traces],
        "order_status_after_reconnect": stored_order.status,
    }

    report_path = os.getenv("MYSQL_INTEGRATION_REPORT_PATH")
    if report_path:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
