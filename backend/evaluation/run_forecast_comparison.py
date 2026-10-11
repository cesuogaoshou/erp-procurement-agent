import json
import time
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable

from sqlalchemy import select

from backend.app.algorithms.shortage import calculate_shortage
from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import DemandHistory, Inventory, Material
from backend.app.services.seed import seed_demo_data
from backend.app.services.forecasting import (
    ProphetForecastConfig,
    dynamic_prophet_config,
    frozen_forecast_strategy_config,
)
from backend.evaluation.metrics import evaluate_regression
from backend.evaluation.run_baseline import _metrics_to_dict


def long_history_prophet_config() -> ProphetForecastConfig:
    return ProphetForecastConfig(
        name="prophet_weekly_yearly_min365",
        min_train_days=365,
        yearly_min_train_days=None,
        short_history_mode="fail",
    )


def main() -> None:
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        result = run_forecast_comparison(session)
    output = Path("reports/generated/forecast_comparison.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_forecast_comparison(session, horizon_days: int = 30) -> dict:
    windows = _build_windows(session, horizon_days)
    moving_average = _evaluate_model(windows, "moving_average_30d", _moving_average_predict)
    prophet = _evaluate_prophet(windows, config=long_history_prophet_config())
    prophet_success_keys = {
        _window_key(window)
        for window in prophet.get("evaluated_windows", {}).get("items", [])
    }
    prophet_success_windows = [
        window for window in windows if _window_key(window["metadata"]) in prophet_success_keys
    ]
    same_window_moving_average = _evaluate_model(
        prophet_success_windows,
        "moving_average_30d_on_prophet_success_windows",
        _moving_average_predict,
    )
    same_window_moving_average["comparison_scope"] = "prophet_success_windows_only"
    same_window_moving_average["paired_model"] = "prophet"
    dynamic_prophet = _evaluate_prophet(windows, config=dynamic_prophet_config(), model_name="prophet_dynamic_seasonality")
    hybrid = _evaluate_hybrid_dynamic_prophet(windows, dynamic_prophet)
    return {
        "generated_at": date.today().isoformat(),
        "dataset": "simulated_demo_seed_20261010",
        "horizon_days": horizon_days,
        "service_strategy_config": asdict(frozen_forecast_strategy_config()),
        "windows": {"sample_count": len(windows), "items": [window["metadata"] for window in windows]},
        "models": {
            "moving_average_30d": moving_average,
            "prophet": prophet,
            "moving_average_30d_on_prophet_success_windows": same_window_moving_average,
            "prophet_dynamic_seasonality": dynamic_prophet,
            "hybrid_dynamic_prophet_or_moving_average_30d": hybrid,
        },
        "notes": [
            "Both models use identical material/cutoff windows.",
            "Prophet long-history and dynamic-seasonality results are reported separately from the hybrid fallback strategy.",
            "The 365-day yearly-seasonality threshold is an engineering strategy for this simulated dataset, not a universal Prophet requirement.",
            "No target threshold is assumed; results are raw comparison outputs.",
        ],
    }


def _build_windows(session, horizon_days: int) -> list[dict]:
    windows = []
    for material in session.scalars(select(Material).order_by(Material.id)):
        history = list(
            session.scalars(
                select(DemandHistory)
                .where(DemandHistory.material_id == material.id)
                .order_by(DemandHistory.demand_date)
            )
        )
        inventory = session.scalar(select(Inventory).where(Inventory.material_id == material.id))
        if inventory is None:
            continue
        for cutoff_index in range(45, len(history) - horizon_days + 1, 30):
            train = history[:cutoff_index]
            holdout = history[cutoff_index : cutoff_index + horizon_days]
            windows.append(
                {
                    "material": material,
                    "inventory": inventory,
                    "train": train,
                    "holdout": holdout,
                    "metadata": {
                        "material_id": material.id,
                        "cutoff_date": holdout[0].demand_date.isoformat(),
                        "train_start": train[0].demand_date.isoformat(),
                        "train_end": train[-1].demand_date.isoformat(),
                        "holdout_start": holdout[0].demand_date.isoformat(),
                        "holdout_end": holdout[-1].demand_date.isoformat(),
                    },
                }
            )
    return windows


def _evaluate_model(windows: list[dict], model_name: str, predictor: Callable[[dict], Decimal]) -> dict:
    started = time.perf_counter()
    actual_demands = []
    predicted_demands = []
    actual_shortages = []
    predicted_shortages = []
    failures = []
    successful_windows = []
    window_predictions = []
    for window in windows:
        try:
            predicted_demand = predictor(window)
            actual_demand = sum(Decimal(row.quantity) for row in window["holdout"])
            available_supply = Decimal(window["inventory"].on_hand) - Decimal(window["inventory"].reserved)
            predicted_shortage = calculate_shortage(
                forecast_demand=predicted_demand,
                safety_stock=Decimal(window["material"].safety_stock),
                available_supply=available_supply,
            )
            actual_shortage = calculate_shortage(
                forecast_demand=actual_demand,
                safety_stock=Decimal(window["material"].safety_stock),
                available_supply=available_supply,
            )
            predicted_demands.append(predicted_demand)
            actual_demands.append(actual_demand)
            predicted_shortages.append(predicted_shortage)
            actual_shortages.append(actual_shortage)
            successful_windows.append(window["metadata"])
            window_predictions.append(
                {
                    "window": window["metadata"],
                    "actual_demand": str(actual_demand),
                    "predicted_demand": str(predicted_demand),
                    "actual_shortage": str(actual_shortage),
                    "predicted_shortage": str(predicted_shortage),
                }
            )
        except Exception as exc:
            failures.append({"window": window["metadata"], "error": str(exc)})
    runtime_ms = int((time.perf_counter() - started) * 1000)
    if not predicted_demands:
        return {
            "status": "failed",
            "model_name": model_name,
            "runtime_ms": runtime_ms,
            "success_rate": _success_rate(0, len(windows)),
            "evaluated_windows": {"sample_count": 0, "items": []},
            "failures": failures,
        }
    return {
        "status": "ok" if not failures else "partial",
        "model_name": model_name,
        "runtime_ms": runtime_ms,
        "demand_metrics": _metrics_to_dict(evaluate_regression(actual_demands, predicted_demands)),
        "shortage_metrics": _metrics_to_dict(evaluate_regression(actual_shortages, predicted_shortages)),
        "zero_shortage_coverage": _zero_shortage_coverage(actual_shortages, predicted_shortages),
        "success_rate": _success_rate(len(successful_windows), len(windows)),
        "evaluated_windows": {"sample_count": len(successful_windows), "items": successful_windows},
        "window_predictions": window_predictions,
        "failures": failures,
    }


def _moving_average_predict(window: dict) -> Decimal:
    train = window["train"][-30:]
    return sum(Decimal(row.quantity) for row in train)


def _evaluate_prophet(windows: list[dict], config: ProphetForecastConfig | None = None, model_name: str = "prophet") -> dict:
    config = config or ProphetForecastConfig()
    try:
        from prophet import Prophet  # type: ignore
    except Exception as exc:
        return {
            "status": "failed",
            "model_name": model_name,
            "config": asdict(config),
            "runtime_ms": 0,
            "success_rate": _success_rate(0, len(windows)),
            "evaluated_windows": {"sample_count": 0, "items": []},
            "failures": [{"error": f"prophet_unavailable:{exc.__class__.__name__}"}],
        }

    def prophet_predict(window: dict) -> Decimal:
        import pandas as pd  # type: ignore

        if len(window["train"]) < config.min_train_days:
            raise ValueError(
                f"insufficient_history: required {config.min_train_days}, got {len(window['train'])}"
            )
        train = window["train"][-config.train_window_days :] if config.train_window_days else window["train"]
        frame = pd.DataFrame(
            [{"ds": row.demand_date.isoformat(), "y": float(row.quantity)} for row in train]
        )
        yearly_seasonality = config.yearly_seasonality
        if config.yearly_min_train_days is not None and len(window["train"]) < config.yearly_min_train_days:
            yearly_seasonality = False
        model = Prophet(
            daily_seasonality=config.daily_seasonality,
            weekly_seasonality=config.weekly_seasonality,
            yearly_seasonality=yearly_seasonality,
            changepoint_prior_scale=config.changepoint_prior_scale,
            seasonality_prior_scale=config.seasonality_prior_scale,
        )
        model.fit(frame)
        future = model.make_future_dataframe(periods=len(window["holdout"]), freq="D", include_history=False)
        forecast = model.predict(future)
        return Decimal(str(forecast["yhat"].clip(lower=0).sum())).quantize(Decimal("0.01"))

    result = _evaluate_model(windows, model_name, prophet_predict)
    result["config"] = asdict(config)
    return result


def _evaluate_hybrid_dynamic_prophet(windows: list[dict], dynamic_prophet_result: dict) -> dict:
    config = dynamic_prophet_config()
    prophet_predictions = {
        _window_key(item["window"]): Decimal(item["predicted_demand"])
        for item in dynamic_prophet_result.get("window_predictions", [])
    }
    prophet_failures = {
        _window_key(item["window"]): item.get("error", "prophet_failed")
        for item in dynamic_prophet_result.get("failures", [])
        if "window" in item
    }
    global_failure = next(
        (item.get("error", "prophet_failed") for item in dynamic_prophet_result.get("failures", []) if "window" not in item),
        "prophet_failed",
    )
    fallback_windows = []

    def hybrid_predict(window: dict) -> Decimal:
        key = _window_key(window["metadata"])
        if key in prophet_predictions:
            return prophet_predictions[key]
        fallback_windows.append({"window": window["metadata"], "reason": prophet_failures.get(key, global_failure)})
        return _moving_average_predict(window)

    result = _evaluate_model(windows, "hybrid_dynamic_prophet_or_moving_average_30d", hybrid_predict)
    result["strategy_type"] = "hybrid_prophet_or_baseline"
    result["prophet_config"] = asdict(config)
    result["fallback_model"] = "moving_average_30d"
    result["fallback_count"] = len(fallback_windows)
    result["fallback_rate_percent"] = _rate_percent(len(fallback_windows), len(windows))
    result["fallback_windows"] = fallback_windows
    result["notes"] = [
        "This is a hybrid strategy over all windows, not a pure Prophet metric.",
        "Prophet failures are filled with the moving-average baseline for operational coverage.",
    ]
    return result


def _make_prophet_predictor(config: ProphetForecastConfig) -> Callable[[dict], Decimal]:
    from prophet import Prophet  # type: ignore

    def prophet_predict(window: dict) -> Decimal:
        import pandas as pd  # type: ignore

        if len(window["train"]) < config.min_train_days:
            raise ValueError(
                f"insufficient_history: required {config.min_train_days}, got {len(window['train'])}"
            )
        train = window["train"][-config.train_window_days :] if config.train_window_days else window["train"]
        frame = pd.DataFrame(
            [{"ds": row.demand_date.isoformat(), "y": float(row.quantity)} for row in train]
        )
        yearly_seasonality = config.yearly_seasonality
        if config.yearly_min_train_days is not None and len(window["train"]) < config.yearly_min_train_days:
            yearly_seasonality = False
        model = Prophet(
            daily_seasonality=config.daily_seasonality,
            weekly_seasonality=config.weekly_seasonality,
            yearly_seasonality=yearly_seasonality,
            changepoint_prior_scale=config.changepoint_prior_scale,
            seasonality_prior_scale=config.seasonality_prior_scale,
        )
        model.fit(frame)
        future = model.make_future_dataframe(periods=len(window["holdout"]), freq="D", include_history=False)
        forecast = model.predict(future)
        return Decimal(str(forecast["yhat"].clip(lower=0).sum())).quantize(Decimal("0.01"))

    return prophet_predict


def _zero_shortage_coverage(actual: list[Decimal], predicted: list[Decimal]) -> dict:
    zero_actual = [index for index, value in enumerate(actual) if value == 0]
    if not zero_actual:
        return {
            "status": "not_applicable",
            "actual_zero_count": 0,
            "predicted_zero_count": 0,
            "coverage_percent": None,
        }
    predicted_zero = sum(1 for index in zero_actual if predicted[index] == 0)
    return {
        "status": "ok",
        "actual_zero_count": len(zero_actual),
        "predicted_zero_count": predicted_zero,
        "coverage_percent": str((Decimal(predicted_zero) / Decimal(len(zero_actual)) * Decimal("100")).quantize(Decimal("0.01"))),
    }


def _success_rate(successful: int, total: int) -> dict:
    return {
        "successful_windows": successful,
        "total_windows": total,
        "percent": _rate_percent(successful, total),
    }


def _rate_percent(count: int, total: int) -> str:
    if total == 0:
        return "0.00"
    return str((Decimal(count) / Decimal(total) * Decimal("100")).quantize(Decimal("0.01")))


def _window_key(metadata: dict) -> tuple[int, str]:
    return (int(metadata["material_id"]), metadata["cutoff_date"])


if __name__ == "__main__":
    main()
