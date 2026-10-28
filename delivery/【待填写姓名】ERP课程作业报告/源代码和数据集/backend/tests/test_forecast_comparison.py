from decimal import Decimal

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.seed import seed_demo_data
from backend.evaluation import run_forecast_comparison as comparison
from backend.evaluation.run_forecast_comparison import (
    ProphetForecastConfig,
    _build_windows,
    _evaluate_prophet,
    _zero_shortage_coverage,
    run_forecast_comparison,
)


def test_forecast_comparison_reports_baseline_and_prophet_sections(monkeypatch):
    monkeypatch.setattr(comparison, "_evaluate_prophet", _fake_evaluate_prophet)

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
    assert result["models"]["prophet"]["status"] in {"ok", "partial", "failed"}
    assert "failures" in result["models"]["prophet"]


def test_forecast_comparison_reports_same_window_baseline_and_hybrid_strategy(monkeypatch):
    monkeypatch.setattr(comparison, "_evaluate_prophet", _fake_evaluate_prophet)

    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        result = run_forecast_comparison(session, horizon_days=30)

    models = result["models"]
    full_baseline = models["moving_average_30d"]
    prophet = models["prophet"]
    same_window_baseline = models["moving_average_30d_on_prophet_success_windows"]
    dynamic_prophet = models["prophet_dynamic_seasonality"]
    hybrid = models["hybrid_dynamic_prophet_or_moving_average_30d"]

    assert full_baseline["demand_metrics"]["sample_count"] == 160
    assert prophet["success_rate"] == {"successful_windows": 50, "total_windows": 160, "percent": "31.25"}
    assert same_window_baseline["demand_metrics"]["sample_count"] == prophet["demand_metrics"]["sample_count"]
    assert same_window_baseline["comparison_scope"] == "prophet_success_windows_only"
    assert dynamic_prophet["config"]["yearly_min_train_days"] == 365
    assert dynamic_prophet["config"]["short_history_mode"] == "weekly_only"
    assert hybrid["strategy_type"] == "hybrid_prophet_or_baseline"
    assert hybrid["fallback_model"] == "moving_average_30d"
    assert hybrid["fallback_count"] == len(dynamic_prophet["failures"])
    assert hybrid["demand_metrics"]["sample_count"] == 160


def _fake_evaluate_prophet(windows, config=None, model_name="prophet"):
    success_count = 50 if model_name == "prophet" else 140
    successful_windows = windows[-success_count:]
    failed_windows = windows[:-success_count]
    actual_demands = [
        sum(Decimal(row.quantity) for row in window["holdout"])
        for window in successful_windows
    ]
    predictions = []
    for window, actual_demand in zip(successful_windows, actual_demands, strict=True):
        predictions.append(
            {
                "window": window["metadata"],
                "actual_demand": str(actual_demand),
                "predicted_demand": str(actual_demand),
                "actual_shortage": "0",
                "predicted_shortage": "0",
            }
        )
    return {
        "status": "partial",
        "model_name": model_name,
        "runtime_ms": 1,
        "demand_metrics": {"sample_count": len(successful_windows)},
        "shortage_metrics": {"sample_count": len(successful_windows)},
        "zero_shortage_coverage": {"status": "not_applicable"},
        "success_rate": comparison._success_rate(len(successful_windows), len(windows)),
        "evaluated_windows": {
            "sample_count": len(successful_windows),
            "items": [window["metadata"] for window in successful_windows],
        },
        "window_predictions": predictions,
        "failures": [
            {"window": window["metadata"], "error": "insufficient_history: fake"}
            for window in failed_windows
        ],
        "config": comparison.asdict(config or comparison.ProphetForecastConfig()),
    }


def test_zero_shortage_coverage_is_not_applicable_when_no_actual_zero_shortage():
    result = _zero_shortage_coverage([1, 2], [1, 2])

    assert result["actual_zero_count"] == 0
    assert result["predicted_zero_count"] == 0
    assert result["coverage_percent"] is None
    assert result["status"] == "not_applicable"


def test_prophet_reports_insufficient_history_without_fitting_short_windows():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        windows = _build_windows(session, horizon_days=30)[:2]
        result = _evaluate_prophet(
            windows,
            config=ProphetForecastConfig(min_train_days=999),
        )

    assert result["status"] == "failed"
    assert result["failures"]
    assert all("insufficient_history" in item["error"] for item in result["failures"])


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
