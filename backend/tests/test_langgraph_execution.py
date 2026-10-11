from decimal import Decimal

from sqlalchemy import select

from backend.app.db.session import create_session_factory, create_sqlite_engine, session_scope
from backend.app.models import AgentRun, PurchaseOrder, ToolTrace
from backend.app.services.approvals import AuthContext, ApprovalActionInput, approve_order, submit_for_approval
from backend.app.services.langgraph_runner import run_langgraph_procurement
from backend.app.services.agent_provider import MockLLMProvider, ToolCall
from backend.app.services.seed import seed_demo_data


def _engine():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    return engine


def test_langgraph_executes_agent_loop_and_persists_state_across_new_session():
    engine = _engine()

    result = run_langgraph_procurement(
        engine=engine,
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
                        "idempotency_key": "langgraph-agent-draft",
                        "evidence_refs": ["use_latest_forecast", "recommendation:langgraph"],
                    },
                ),
            ]
        ),
        prompt="need material 1",
        thread_id="langgraph-test-1",
    )

    factory = create_session_factory(engine)
    with factory() as session:
        stored_run = session.get(AgentRun, result["run_id"])
        traces = list(session.scalars(select(ToolTrace).where(ToolTrace.run_id == result["run_id"]).order_by(ToolTrace.step_index)))
        order = session.get(PurchaseOrder, result["purchase_order_id"])

    assert result["langgraph_executed"] is True
    assert result["status"] == "draft_created"
    assert result["tool_calls"] == ["get_demand_forecast", "recommend_suppliers", "create_purchase_draft"]
    assert stored_run.status == "draft_created"
    assert [trace.tool_name for trace in traces] == result["tool_calls"]
    assert order.status == "draft"
    assert order.total_amount == Decimal("972.00")


def test_langgraph_draft_pending_approval_can_be_queried_and_approved_after_restart_scope():
    engine = _engine()
    result = run_langgraph_procurement(
        engine=engine,
        provider=MockLLMProvider(
            [
                ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 30}),
                ToolCall(
                    "create_purchase_draft",
                    {
                        "supplier_id": 1,
                        "items": [{"material_id": 1, "quantity": "120"}],
                        "idempotency_key": "langgraph-approval-resume",
                        "evidence_refs": ["use_latest_forecast"],
                    },
                ),
            ]
        ),
        prompt="need approval recovery",
        thread_id="langgraph-test-approval",
    )

    factory = create_session_factory(engine)
    with factory() as session:
        pending = submit_for_approval(
            session,
            result["purchase_order_id"],
            AuthContext(user_id="buyer-1", role="buyer"),
        )
        pending_version = pending.version
        session.commit()

    restarted_factory = create_session_factory(engine)
    with restarted_factory() as session:
        stored = session.get(PurchaseOrder, result["purchase_order_id"])
        assert stored.status == "pending_approval"
        approved = approve_order(
            session,
            stored.id,
            AuthContext(user_id="approver-1", role="approver"),
            ApprovalActionInput(
                expected_order_version=pending_version,
                idempotency_key="langgraph-resume-approve",
            ),
        )
        session.commit()

    assert approved.status == "approved"
    assert approved.formal_order_number == f"PO-{approved.id:06d}"
