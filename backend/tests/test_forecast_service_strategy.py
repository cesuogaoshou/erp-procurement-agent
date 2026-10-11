import json
from decimal import Decimal

from sqlalchemy import delete, select

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import DemandHistory, PurchaseOrder, PurchaseOrderItem, ToolTrace
from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import MockLLMProvider, ToolCall
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.seed import seed_demo_data


def _engine():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    return engine


def test_demand_forecast_uses_frozen_hybrid_strategy_metadata():
    engine = _engine()
    with session_scope(engine) as session:
        forecast = get_demand_forecast(session, material_id=1, horizon_days=30)

    assert forecast["model_name"] == "hybrid_dynamic_prophet_or_moving_average_30d"
    assert forecast["strategy_type"] == "hybrid_prophet_or_baseline"
    assert forecast["config_version"] == "forecast_strategy_v1_20261011"
    assert forecast["selected_model_name"] == "prophet_dynamic_weekly_then_yearly"
    assert forecast["fallback_reason"] is None
    assert forecast["training_range"]["sample_count"] == 540
    assert forecast["training_range"]["start_date"] == "2025-04-18"
    assert forecast["training_range"]["end_date"] == "2026-10-09"
    assert forecast["forecast_evidence"]["model_name"] == forecast["model_name"]
    assert forecast["forecast_evidence"]["selected_model_name"] == forecast["selected_model_name"]
    assert forecast["forecast_evidence"]["config_version"] == forecast["config_version"]
    assert "forecast_strategy_v1_20261011" in forecast["evidence_ref"]


def test_demand_forecast_short_history_falls_back_to_moving_average():
    engine = _engine()
    with session_scope(engine) as session:
        keep_ids = [
            row_id
            for row_id in session.scalars(
                select(DemandHistory.id)
                .where(DemandHistory.material_id == 1)
                .order_by(DemandHistory.demand_date.desc())
                .limit(45)
            )
        ]
        session.execute(
            delete(DemandHistory).where(
                DemandHistory.material_id == 1,
                DemandHistory.id.not_in(keep_ids),
            )
        )
        forecast = get_demand_forecast(session, material_id=1, horizon_days=30)

    assert forecast["model_name"] == "hybrid_dynamic_prophet_or_moving_average_30d"
    assert forecast["selected_model_name"] == "moving_average_30d"
    assert forecast["fallback_reason"] == "insufficient_history: required 90, got 45"
    assert forecast["training_range"]["sample_count"] == 45
    assert forecast["forecast_demand"] > 0


def test_agent_forecast_evidence_is_persisted_to_trace_and_purchase_draft_with_rounding():
    engine = _engine()
    loop = AgentLoop(
        engine=engine,
        provider=MockLLMProvider(
            [
                ToolCall("get_demand_forecast", {"material_id": 9, "horizon_days": 30}),
                ToolCall(
                    "create_purchase_draft",
                    {
                        "supplier_id": 1,
                        "items": [{"material_id": 9, "quantity": "121"}],
                        "idempotency_key": "forecast-evidence-package-chain",
                        "evidence_refs": ["use_latest_forecast"],
                    },
                ),
            ]
        ),
    )

    result = loop.run("buy material 9 with forecast evidence")

    with session_scope(engine) as session:
        forecast_trace = session.scalar(
            select(ToolTrace)
            .where(ToolTrace.run_id == result.run_id, ToolTrace.tool_name == "get_demand_forecast")
        )
        order = session.scalar(
            select(PurchaseOrder).where(PurchaseOrder.idempotency_key == "forecast-evidence-package-chain")
        )
        order_item = session.scalar(select(PurchaseOrderItem).where(PurchaseOrderItem.order_id == order.id))

    forecast_output = json.loads(forecast_trace.output_json)
    persisted_evidence = json.loads(order.evidence_refs_json)

    assert result.status == "draft_created"
    assert forecast_output["forecast_evidence"]["config_version"] == "forecast_strategy_v1_20261011"
    assert forecast_output["forecast_evidence"]["model_name"] == "hybrid_dynamic_prophet_or_moving_average_30d"
    assert persisted_evidence["refs"] == [forecast_output["evidence_ref"]]
    assert persisted_evidence["forecast_evidence"][0]["evidence_ref"] == forecast_output["evidence_ref"]
    assert persisted_evidence["forecast_evidence"][0]["model_name"] == "hybrid_dynamic_prophet_or_moving_average_30d"
    assert order_item.quantity == Decimal("130.00")
