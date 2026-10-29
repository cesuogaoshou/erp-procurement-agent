import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import create_engine, select, event

from backend.app.db.session import create_session_factory
from backend.app.models import AgentRun, ApprovalRecord, AuditLog, PurchaseOrder, ToolTrace
from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import MockLLMProvider, ToolCall
from backend.app.services.approvals import (
    AuthContext,
    ApprovalActionInput,
    ApprovalConflict,
    approve_order,
    submit_for_approval,
)
from backend.app.services.purchase_drafts import DraftItemInput, PurchaseDraftInput, create_purchase_draft
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.recommendations import recommend_for_material


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


def _draft_with_current_evidence(session, key: str):
    quantity = Decimal("120")
    budget = Decimal("5000.00")
    forecast = get_demand_forecast(session, material_id=1, horizon_days=30)
    recommendations = recommend_for_material(
        session, material_id=1, quantity=quantity, required_in_days=20, budget=budget,
    )
    assert Decimal(str(forecast["shortage_quantity"])) >= quantity
    assert any(item.supplier_id == 1 for item in recommendations.recommendations)
    return create_purchase_draft(
        session,
        PurchaseDraftInput(
            total_budget=Decimal("5000"),
            supplier_id=1,
            items=[DraftItemInput(material_id=1, quantity=quantity)],
            idempotency_key=key,
            evidence_refs=[forecast["evidence_ref"], f"recommendation:1:1:{quantity}:20:{budget}"],
        ),
    )


def test_mysql_approval_concurrency_rollback_and_agent_persistence(mysql_engine):
    run_key = str(int(time.time() * 1000))
    report: dict[str, object] = {"run_key": run_key}
    factory = create_session_factory(mysql_engine)

    with factory() as session:
        order = _draft_with_current_evidence(session, f"mysql-concurrency-{run_key}")
        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))
        order_id = pending.id
        expected_version = pending.version
        session.commit()

    approval_barrier = Barrier(2)

    def approve_once(actor_suffix: str) -> dict[str, str]:
        local_factory = create_session_factory(mysql_engine)
        with local_factory() as session:
            approval_barrier.wait(timeout=10)
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
            except ApprovalConflict as exc:
                session.rollback()
                return {"status": "conflict", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result() for future in as_completed([executor.submit(approve_once, "a"), executor.submit(approve_once, "b")])]

    with factory() as session:
        stored = session.get(PurchaseOrder, order_id)
        approvals = list(session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == order_id)))
        audits = list(session.scalars(select(AuditLog).where(AuditLog.order_id == order_id)))

    assert sorted(outcome["status"] for outcome in outcomes) == ["approved", "conflict"]
    assert [outcome["error"] for outcome in outcomes if outcome["status"] == "conflict"] == ["order_not_pending_approval"]
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
        rollback_order = _draft_with_current_evidence(session, f"mysql-rollback-{run_key}")
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
    assert rollback_stored.formal_order_number is None
    assert rollback_records == []
    assert [audit.action for audit in rollback_audits] == ["submitted_for_approval"]
    report["rollback"] = {
        "order_id": rollback_order_id,
        "status": rollback_stored.status,
        "version": rollback_stored.version,
        "formal_order_number": rollback_stored.formal_order_number,
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
                        "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"],
                    },
                ),
            ]
        ),
    ).run("Need 120 units of material 1 within 20 days", total_budget=Decimal("5000"))
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

    _write_report_section("core", report)


def test_mysql_duplicate_approval_idempotency_uses_existing_record(mysql_engine):
    run_key = str(int(time.time() * 1000))
    factory = create_session_factory(mysql_engine)

    with factory() as session:
        order = _draft_with_current_evidence(session, f"mysql-duplicate-approval-{run_key}")
        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))
        order_id = pending.id
        expected_version = pending.version
        request = ApprovalActionInput(
            expected_order_version=expected_version,
            idempotency_key=f"mysql-duplicate-approval-key-{run_key}",
        )
        first = approve_order(session, order_id, AuthContext(user_id="approver-1", role="approver"), request)
        second = approve_order(session, order_id, AuthContext(user_id="approver-1", role="approver"), request)
        session.commit()

    with factory() as session:
        stored = session.get(PurchaseOrder, order_id)
        approvals = list(session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == order_id)))
        audits = list(session.scalars(select(AuditLog).where(AuditLog.order_id == order_id)))

    assert first.id == second.id == order_id
    assert stored.status == "approved"
    assert len(approvals) == 1
    assert [audit.action for audit in audits].count("approved") == 1
    _write_report_section(
        "duplicate_approval",
        {
            "order_id": order_id,
            "status": stored.status,
            "approval_records": len(approvals),
            "audit_actions": [audit.action for audit in audits],
        },
    )


def test_mysql_two_session_stale_approval_conflicts_after_first_commit(mysql_engine):
    run_key = str(int(time.time() * 1000))
    factory = create_session_factory(mysql_engine)

    with factory() as setup:
        order = _draft_with_current_evidence(setup, f"mysql-two-session-{run_key}")
        pending = submit_for_approval(setup, order.id, AuthContext(user_id="buyer-1", role="buyer"))
        order_id = pending.id
        expected_version = pending.version
        setup.commit()

    session_a = factory()
    session_b = factory()
    try:
        with pytest.raises(ApprovalConflict, match="^order_version_conflict$"):
            approve_order(
                session_b, order_id, AuthContext(user_id="approver-b", role="approver"),
                ApprovalActionInput(
                    expected_order_version=expected_version - 1,
                    idempotency_key=f"mysql-wrong-version-{run_key}",
                ),
            )
        session_b.rollback()
        first = approve_order(
            session_a,
            order_id,
            AuthContext(user_id="approver-a", role="approver"),
            ApprovalActionInput(
                expected_order_version=expected_version,
                idempotency_key=f"mysql-two-session-a-{run_key}",
            ),
        )
        session_a.commit()

        try:
            approve_order(
                session_b,
                order_id,
                AuthContext(user_id="approver-b", role="approver"),
                ApprovalActionInput(
                    expected_order_version=expected_version,
                    idempotency_key=f"mysql-two-session-b-{run_key}",
                ),
            )
        except ApprovalConflict as exc:
            session_b.rollback()
            conflict = str(exc)
        else:
            session_b.commit()
            conflict = ""
    finally:
        session_a.close()
        session_b.close()

    with factory() as session:
        stored = session.get(PurchaseOrder, order_id)
        approvals = list(session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == order_id)))

    assert first.status == "approved"
    assert conflict == "order_not_pending_approval"
    assert stored.status == "approved"
    assert len(approvals) == 1
    _write_report_section(
        "two_session_stale_approval",
        {
            "order_id": order_id,
            "first_status": first.status,
            "second_error": conflict,
            "wrong_version_error": "order_version_conflict",
            "stored_status": stored.status,
            "approval_records": len(approvals),
        },
    )


def _write_report_section(section: str, payload: dict[str, object]) -> None:
    report_path = os.getenv("MYSQL_INTEGRATION_REPORT_PATH")
    if not report_path:
        return
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
    else:
        report = {}
    report[section] = payload
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("other_buyer", [False, True])
def test_mysql_same_key_create_really_competes(mysql_engine, other_buyer):
    """Barrier is at INSERT, after BOTH requests have missed the existing key."""
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    from backend.app.services.auth import issue_token, DEMO_ACCOUNTS
    key = f"extreme-race-{time.time_ns()}"
    factory = create_session_factory(mysql_engine)
    with factory() as session:
        forecast = get_demand_forecast(session, material_id=1, horizon_days=30)
    payload = {"supplier_id": 1, "items": [{"material_id": 1, "quantity": "120.00"}],
               "idempotency_key": key, "total_budget": "5000.00",
               "evidence_refs": [forecast["evidence_ref"], "recommendation:1:1:120:20:5000"]}
    barrier = Barrier(2)
    arrivals = []
    def before_insert(mapper, connection, order):
        if order.idempotency_key == key:
            arrivals.append(connection)
            barrier.wait(timeout=20)
    event.listen(PurchaseOrder, "before_insert", before_insert)
    DEMO_ACCOUNTS.setdefault("extreme-buyer-2", {"password": "test-only", "user_id": "extreme-buyer-2", "role": "buyer"})
    def create_once(user):
        token = issue_token(username=user, user_id="buyer-1" if user == "buyer" else user, role="buyer", secret="race-secret")
        with TestClient(create_app(mysql_engine, auth_secret="race-secret")) as client:
            response = client.post("/purchase-drafts", json=payload, headers={"Authorization": f"Bearer {token}"})
            return {"status": response.status_code, "body": response.json()}
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create_once, user) for user in ["buyer", "extreme-buyer-2" if other_buyer else "buyer"]]
            outcomes = [f.result() for f in futures]
    finally:
        event.remove(PurchaseOrder, "before_insert", before_insert)
    assert len(arrivals) == 2 and arrivals[0] is not arrivals[1]
    assert sorted(o["status"] for o in outcomes) == ([200, 403] if other_buyer else [200, 200])
    for outcome in outcomes:
        if outcome["status"] == 200:
            assert len(outcome["body"]["items"]) == 1
            assert Decimal(outcome["body"]["items"][0]["quantity"]) == Decimal("120")
    with factory() as session:
        orders = session.scalars(select(PurchaseOrder).where(PurchaseOrder.idempotency_key == key)).all()
        assert len(orders) == 1
        audits = session.scalars(select(AuditLog).where(AuditLog.order_id == orders[0].id, AuditLog.action == "created_draft")).all()
        assert len(audits) == 1
        _write_report_section("create_race_cross_buyer" if other_buyer else "create_race_same_buyer", {
            "order_id": orders[0].id, "insert_barrier_arrivals": len(arrivals), "outcomes": outcomes,
            "creation_audits": len(audits), "creator": audits[0].actor_user_id})
