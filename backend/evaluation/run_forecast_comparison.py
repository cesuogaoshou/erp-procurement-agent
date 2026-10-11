import json
import time
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable

from sqlalchemy import select

from backend.app.algorithms.shortage import calculate_shortage
from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import DemandHistory, Inventory, Material
from backend.app.services.seed import seed_demo_data
from backend.evaluation.metrics import evaluate_regression
from backend.evaluation.run_baseline import _metrics_to_dict


@dataclass(frozen=True)
class ProphetForecastConfig:
    name: str = "prophet_weekly_yearly_min365"
    min_train_days: int = 365
    train_window_days: int | None = None
    daily_seasonality: bool = False
    weekly_seasonality: bool = True
    yearly_seasonality: bool = True
    changepoint_prior_scale: float = 0.05
    seasonality_prior_scale: float = 10.0


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
    return {
        "generated_at": date.today().isoformat(),
        "dataset": "simulated_demo_seed_20261010",
        "horizon_days": horizon_days,
        "windows": {"sample_count": len(windows), "items": [window["metadata"] for window in windows]},
        "models": {
            "moving_average_30d": _evaluate_model(windows, "moving_average_30d", _moving_average_predict),
            "prophet": _evaluate_prophet(windows),
        },
        "notes": [
            "Both models use identical material/cutoff windows.",
            "Prophet requires enough training history and reports insufficient windows as failures.",
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
        except Exception as exc:
            failures.append({"window": window["metadata"], "error": str(exc)})
    runtime_ms = int((time.perf_counter() - started) * 1000)
    if not predicted_demands:
        return {
            "status": "failed",
            "model_name": model_name,
            "runtime_ms": runtime_ms,
            "failures": failures,
        }
    return {
        "status": "ok" if not failures else "partial",
        "model_name": model_name,
        "runtime_ms": runtime_ms,
        "demand_metrics": _metrics_to_dict(evaluate_regression(actual_demands, predicted_demands)),
        "shortage_metrics": _metrics_to_dict(evaluate_regression(actual_shortages, predicted_shortages)),
        "zero_shortage_coverage": _zero_shortage_coverage(actual_shortages, predicted_shortages),
        "failures": failures,
    }


def _moving_average_predict(window: dict) -> Decimal:
    train = window["train"][-30:]
    return sum(Decimal(row.quantity) for row in train)


def _evaluate_prophet(windows: list[dict], config: ProphetForecastConfig | None = None) -> dict:
    config = config or ProphetForecastConfig()
    try:
        from prophet import Prophet  # type: ignore
    except Exception as exc:
        return {
            "status": "failed",
            "model_name": "prophet",
            "config": asdict(config),
            "runtime_ms": 0,
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
        model = Prophet(
            daily_seasonality=config.daily_seasonality,
            weekly_seasonality=config.weekly_seasonality,
            yearly_seasonality=config.yearly_seasonality,
            changepoint_prior_scale=config.changepoint_prior_scale,
            seasonality_prior_scale=config.seasonality_prior_scale,
        )
        model.fit(frame)
        future = model.make_future_dataframe(periods=len(window["holdout"]), freq="D", include_history=False)
        forecast = model.predict(future)
        return Decimal(str(forecast["yhat"].clip(lower=0).sum())).quantize(Decimal("0.01"))

    result = _evaluate_model(windows, "prophet", prophet_predict)
    result["config"] = asdict(config)
    return result


def _zero_shortage_coverage(actual: list[Decimal], predicted: list[Decimal]) -> dict:
    zero_actual = [index for index, value in enumerate(actual) if value == 0]
    if not zero_actual:
        return {"actual_zero_count": 0, "predicted_zero_count": 0, "coverage_percent": "0.00"}
    predicted_zero = sum(1 for index in zero_actual if predicted[index] == 0)
    return {
        "actual_zero_count": len(zero_actual),
        "predicted_zero_count": predicted_zero,
        "coverage_percent": str((Decimal(predicted_zero) / Decimal(len(zero_actual)) * Decimal("100")).quantize(Decimal("0.01"))),
    }


if __name__ == "__main__":
    main()
