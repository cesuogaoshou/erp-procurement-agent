from decimal import Decimal

from sqlalchemy import select

from backend.app.db.session import create_session_factory, create_sqlite_engine, session_scope
from backend.app.models import AgentRun, PurchaseOrder, ToolTrace
from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import MockLLMProvider, ProviderError, ToolCall
from backend.app.services.seed import seed_demo_data


def _engine():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    return engine


def test_agent_forecast_evidence_is_required_for_purchase_quantity():
    loop = AgentLoop(
        engine=_engine(),
        provider=MockLLMProvider(
            [
                ToolCall(
                    "create_purchase_draft",
                    {
                        "supplier_id": 1,
                        "items": [{"material_id": 1, "quantity": "120"}],
                        "idempotency_key": "no-forecast-evidence",
                        "evidence_refs": ["forecast:made-up"],
                    },
                )
            ]
        ),
    )

    result = loop.run("buy 120 material 1")

    assert result.status == "tool_error"
    assert result.error == "forecast_evidence_required"


def test_agent_rejects_quantity_above_server_forecast_shortage():
    engine = _engine()
    loop = AgentLoop(
        engine=engine,
        provider=MockLLMProvider(
            [
                ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 30}),
                ToolCall(
                    "create_purchase_draft",
                    {
                        "supplier_id": 1,
                        "items": [{"material_id": 1, "quantity": "9999"}],
                        "idempotency_key": "agent-over-forecast-shortage",
                        "evidence_refs": ["use_latest_forecast"],
                    },
                ),
            ]
        ),
    )

    result = loop.run("buy too much material 1")

    assert result.status == "tool_error"
    assert result.error == "quantity_exceeds_forecast_shortage"


def test_agent_persists_run_trace_and_draft_across_new_session():
    engine = _engine()
    loop = AgentLoop(
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
                        "idempotency_key": "persisted-agent-draft",
                        "evidence_refs": ["use_latest_forecast", "recommendation:persisted"],
                    },
                ),
            ]
        ),
    )

    result = loop.run("need material 1")

    factory = create_session_factory(engine)
    with factory() as session:
        stored_run = session.get(AgentRun, result.run_id)
        traces = list(session.scalars(select(ToolTrace).where(ToolTrace.run_id == result.run_id).order_by(ToolTrace.step_index)))
        order = session.scalar(select(PurchaseOrder).where(PurchaseOrder.idempotency_key == "persisted-agent-draft"))

    assert result.status == "draft_created"
    assert stored_run.status == "draft_created"
    assert [trace.tool_name for trace in traces] == [
        "get_demand_forecast",
        "recommend_suppliers",
        "create_purchase_draft",
    ]
    assert order.status == "draft"
    assert order.total_amount == Decimal("972.00")


def test_agent_handles_no_shortage_and_provider_timeout():
    no_shortage_loop = AgentLoop(
        engine=_engine(),
        provider=MockLLMProvider([ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 1})]),
    )
    no_shortage = no_shortage_loop.run("check material 1")

    timeout_loop = AgentLoop(engine=_engine(), provider=MockLLMProvider([], error=ProviderError("provider_timeout")))
    timeout = timeout_loop.run("timeout please")

    assert no_shortage.status in {"completed", "no_shortage"}
    assert timeout.status == "provider_error"
    assert timeout.error == "provider_timeout"


def test_duplicate_agent_draft_request_returns_existing_order():
    engine = _engine()
    calls = [
        ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 30}),
        ToolCall(
            "create_purchase_draft",
            {
                "supplier_id": 1,
                "items": [{"material_id": 1, "quantity": "120"}],
                "idempotency_key": "duplicate-agent-draft",
                "evidence_refs": ["use_latest_forecast"],
            },
        ),
    ]
    first = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("draft once")
    second = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("draft twice")

    assert first.status == "draft_created"
    assert second.status == "draft_created"
    assert first.purchase_order_id == second.purchase_order_id


def test_agent_reports_tool_parameter_error_material_ambiguity_and_no_qualified_supplier():
    parameter_error = AgentLoop(
        engine=_engine(),
        provider=MockLLMProvider([ToolCall("get_demand_forecast", {"horizon_days": 30})]),
    ).run("missing material id")
    ambiguous = AgentLoop(
        engine=_engine(),
        provider=MockLLMProvider([ToolCall("resolve_material", {"query": "MAT"})]),
    ).run("find MAT")
    no_supplier = AgentLoop(
        engine=_engine(),
        provider=MockLLMProvider(
            [
                ToolCall(
                    "recommend_suppliers",
                    {"material_id": 1, "quantity": "99999", "required_in_days": 1, "budget": "1.00"},
                )
            ]
        ),
    ).run("impossible supplier")

    assert parameter_error.status == "tool_error"
    assert parameter_error.error is not None
    assert ambiguous.status == "material_ambiguous"
    assert no_supplier.status == "no_qualified_suppliers"
