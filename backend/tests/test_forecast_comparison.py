from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.seed import seed_demo_data
from backend.evaluation.run_forecast_comparison import run_forecast_comparison


def test_forecast_comparison_reports_baseline_and_prophet_sections():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        result = run_forecast_comparison(session, horizon_days=30)

    assert result["horizon_days"] == 30
    assert result["windows"]["sample_count"] >= 100
    assert result["models"]["moving_average_30d"]["status"] == "ok"
    assert "demand_metrics" in result["models"]["moving_average_30d"]
    assert "shortage_metrics" in result["models"]["moving_average_30d"]
    assert "zero_shortage_coverage" in result["models"]["moving_average_30d"]
    assert "runtime_ms" in result["models"]["moving_average_30d"]
    assert result["models"]["prophet"]["status"] in {"ok", "failed"}
    assert "failures" in result["models"]["prophet"]


def test_get_demand_forecast_returns_inventory_shortage_and_evidence_ref():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        forecast = get_demand_forecast(session, material_id=1, horizon_days=30)

    assert forecast["tool_name"] == "get_demand_forecast"
    assert forecast["material_id"] == 1
    assert forecast["horizon_days"] == 30
    assert forecast["forecast_demand"] > 0
    assert forecast["shortage_quantity"] >= 0
    assert forecast["inventory"]["material_id"] == 1
    assert forecast["evidence_ref"].startswith("forecast:")
