from decimal import Decimal

from backend.app.db.session import create_sqlite_engine, session_scope
from sqlalchemy import select

from backend.app.models import AgentRun, ToolTrace
from backend.app.services.agent_loop import AgentLoop, AgentRunLimitExceeded
from backend.app.services.agent_provider import MockLLMProvider, ToolCall
from backend.app.services.agent_tools import build_agent_tools, execute_agent_tool
from backend.app.services.seed import seed_demo_data


def _engine():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    return engine


def test_agent_tool_schema_excludes_approval_tools_and_includes_read_only_plus_draft():
    tools = build_agent_tools()
    names = [tool.name for tool in tools]

    assert names == [
        "list_materials",
        "resolve_material",
        "get_inventory",
        "get_demand_forecast",
        "recommend_suppliers",
        "create_purchase_draft",
    ]
    assert all("approve" not in name and "reject" not in name for name in names)
    assert tools[-1].write_mode == "create_draft"


def test_agent_get_inventory_tool_returns_serializable_inventory_snapshot():
    engine = _engine()
    with session_scope(engine) as session:
        snapshot = execute_agent_tool(session, "get_inventory", {"material_id": 1})

    assert snapshot["material_id"] == 1
    assert "available_supply" in snapshot
    assert "version" in snapshot


def test_agent_loop_runs_read_only_tools_before_creating_purchase_draft():
    provider = MockLLMProvider(
        [
            ToolCall("list_materials", {}),
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
                    "idempotency_key": "agent-draft-001",
                    "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"],
                },
            ),
        ]
    )
    loop = AgentLoop(engine=_engine(), provider=provider, max_tool_calls=5)

    result = loop.run("Need 120 units of material 1 within 20 days", total_budget=Decimal("5000"))

    assert result.status == "draft_created"
    assert result.tool_calls == ["list_materials", "get_demand_forecast", "recommend_suppliers", "create_purchase_draft"]
    assert result.purchase_order_id is not None
    assert result.total_amount == Decimal("972.00")


def test_agent_loop_rejects_provider_attempt_to_call_approval_tool():
    provider = MockLLMProvider([ToolCall("approve_order", {"order_id": 1})])
    loop = AgentLoop(engine=_engine(), provider=provider, max_tool_calls=4)

    result = loop.run("Approve order 1", total_budget=Decimal("5000"))

    assert result.status == "tool_not_allowed"
    assert result.error == "tool_not_allowed:approve_order"


def test_agent_loop_enforces_tool_call_limit():
    provider = MockLLMProvider(
        [
            ToolCall("list_materials", {}),
            ToolCall("list_materials", {}),
            ToolCall("list_materials", {}),
        ]
    )
    loop = AgentLoop(engine=_engine(), provider=provider, max_tool_calls=2)

    try:
        loop.run("loop forever", total_budget=Decimal("5000"))
    except AgentRunLimitExceeded as exc:
        assert str(exc) == "max_tool_calls_exceeded"
    else:
        raise AssertionError("expected AgentRunLimitExceeded")


def test_agent_loop_persists_tool_call_limit_state_for_restart_query():
    engine = _engine()
    provider = MockLLMProvider(
        [
            ToolCall("list_materials", {}),
            ToolCall("list_materials", {}),
            ToolCall("list_materials", {}),
        ]
    )
    loop = AgentLoop(engine=engine, provider=provider, max_tool_calls=2)

    try:
        loop.run("loop forever", total_budget=Decimal("5000"))
    except AgentRunLimitExceeded:
        pass
    else:
        raise AssertionError("expected AgentRunLimitExceeded")

    with session_scope(engine) as session:
        run = session.scalars(select(AgentRun)).one()
        traces = session.scalars(select(ToolTrace).where(ToolTrace.run_id == run.id)).all()

    assert run.status == "max_tool_calls_exceeded"
    assert run.error == "max_tool_calls_exceeded"
    assert [trace.tool_name for trace in traces] == ["list_materials", "list_materials"]
