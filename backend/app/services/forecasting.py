import logging
from dataclasses import asdict, dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.algorithms.shortage import calculate_shortage
from backend.app.models import DemandHistory, Material
from backend.app.services.inventory import get_inventory_snapshot


@dataclass(frozen=True)
class ProphetForecastConfig:
    name: str = "prophet_dynamic_weekly_then_yearly"
    min_train_days: int = 90
    train_window_days: int | None = None
    daily_seasonality: bool = False
    weekly_seasonality: bool = True
    yearly_seasonality: bool = True
    yearly_min_train_days: int | None = 365
    short_history_mode: str = "weekly_only"
    changepoint_prior_scale: float = 0.05
    seasonality_prior_scale: float = 10.0


@dataclass(frozen=True)
class ForecastStrategyConfig:
    config_version: str = "forecast_strategy_v1_20261011"
    model_name: str = "hybrid_dynamic_prophet_or_moving_average_30d"
    strategy_type: str = "hybrid_prophet_or_baseline"
    fallback_model_name: str = "moving_average_30d"
    prophet: ProphetForecastConfig = ProphetForecastConfig()


def dynamic_prophet_config() -> ProphetForecastConfig:
    return ProphetForecastConfig()


def frozen_forecast_strategy_config() -> ForecastStrategyConfig:
    return ForecastStrategyConfig()


def baseline_forecast(session: Session, material_id: int, horizon_days: int) -> dict:
    return hybrid_forecast(session, material_id, horizon_days)


def hybrid_forecast(session: Session, material_id: int, horizon_days: int) -> dict:
    strategy = frozen_forecast_strategy_config()
    material = session.get(Material, material_id)
    if material is None:
        raise LookupError(f"material not found: {material_id}")

    rows = _history_rows(session, material_id)
    if not rows:
        raise LookupError(f"demand history not found for material_id={material_id}")

    fallback_reason = None
    selected_model_name = strategy.prophet.name
    try:
        forecast_demand = _prophet_forecast_demand(rows, horizon_days, strategy.prophet)
    except ValueError as exc:
        selected_model_name = strategy.fallback_model_name
        fallback_reason = str(exc)
        forecast_demand = _moving_average_forecast_demand(rows, horizon_days)
    except Exception as exc:
        selected_model_name = strategy.fallback_model_name
        fallback_reason = f"prophet_error:{exc.__class__.__name__}"
        forecast_demand = _moving_average_forecast_demand(rows, horizon_days)

    training_range = _training_range(rows)
    forecast_start = rows[-1].demand_date + timedelta(days=1)
    forecast_end = forecast_start + timedelta(days=horizon_days - 1)
    inventory = get_inventory_snapshot(session, material_id)
    shortage = calculate_shortage(
        forecast_demand=forecast_demand,
        safety_stock=Decimal(material.safety_stock),
        available_supply=Decimal(inventory["available_supply"]),
    )
    evidence_ref = _evidence_ref(
        material_id=material_id,
        horizon_days=horizon_days,
        inventory_version=inventory["version"],
        config_version=strategy.config_version,
        selected_model_name=selected_model_name,
        train_end=training_range["end_date"],
    )
    evidence = {
        "evidence_ref": evidence_ref,
        "material_id": material_id,
        "horizon_days": horizon_days,
        "model_name": strategy.model_name,
        "strategy_type": strategy.strategy_type,
        "selected_model_name": selected_model_name,
        "config_version": strategy.config_version,
        "training_range": training_range,
        "forecast_range": {
            "start_date": forecast_start.isoformat(),
            "end_date": forecast_end.isoformat(),
        },
        "fallback_reason": fallback_reason,
        "config": _strategy_to_dict(strategy),
        "forecast_demand": str(forecast_demand),
        "shortage_quantity": str(shortage),
        "inventory_version": inventory["version"],
    }
    notes = [
        "Phase 1 simplification: confirmed inbound supply is not included.",
        "Forecast strategy is frozen for course delivery; do not retune without creating a new experiment.",
        "Hybrid strategy is not a pure Prophet metric.",
    ]
    if fallback_reason is not None:
        notes.append(f"Forecast downgraded to moving average: {fallback_reason}")
    if strategy.prophet.yearly_min_train_days is not None:
        notes.append(
            "The 365-day yearly-seasonality guard is a project engineering strategy, not a Prophet universal requirement."
        )
    return {
        "material_id": material_id,
        "horizon_days": horizon_days,
        "model_name": strategy.model_name,
        "strategy_type": strategy.strategy_type,
        "selected_model_name": selected_model_name,
        "config_version": strategy.config_version,
        "fallback_model_name": strategy.fallback_model_name,
        "fallback_reason": fallback_reason,
        "training_range": training_range,
        "forecast_range": evidence["forecast_range"],
        "config": evidence["config"],
        "evidence_ref": evidence_ref,
        "forecast_evidence": evidence,
        "forecast_demand": forecast_demand,
        "safety_stock": material.safety_stock,
        "available_supply": inventory["available_supply"],
        "shortage_quantity": shortage,
        "notes": notes,
    }


def get_demand_forecast(session: Session, material_id: int, horizon_days: int) -> dict:
    forecast = hybrid_forecast(session, material_id, horizon_days)
    inventory = get_inventory_snapshot(session, material_id)
    return {
        "tool_name": "get_demand_forecast",
        "evidence_ref": forecast["evidence_ref"],
        "material_id": material_id,
        "horizon_days": horizon_days,
        "forecast_demand": forecast["forecast_demand"],
        "shortage_quantity": forecast["shortage_quantity"],
        "inventory": inventory,
        "model_name": forecast["model_name"],
        "strategy_type": forecast["strategy_type"],
        "selected_model_name": forecast["selected_model_name"],
        "config_version": forecast["config_version"],
        "fallback_model_name": forecast["fallback_model_name"],
        "fallback_reason": forecast["fallback_reason"],
        "training_range": forecast["training_range"],
        "forecast_range": forecast["forecast_range"],
        "config": forecast["config"],
        "forecast_evidence": forecast["forecast_evidence"],
        "notes": forecast["notes"],
    }


def _history_rows(session: Session, material_id: int) -> list[DemandHistory]:
    return list(
        session.scalars(
            select(DemandHistory)
            .where(DemandHistory.material_id == material_id)
            .order_by(DemandHistory.demand_date)
        )
    )


def _moving_average_forecast_demand(rows: list[DemandHistory], horizon_days: int) -> Decimal:
    train = rows[-30:]
    daily_average = sum(Decimal(row.quantity) for row in train) / Decimal(len(train))
    return (daily_average * Decimal(horizon_days)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _prophet_forecast_demand(
    rows: list[DemandHistory],
    horizon_days: int,
    config: ProphetForecastConfig,
    prophet_factory: Callable | None = None,
) -> Decimal:
    if len(rows) < config.min_train_days:
        raise ValueError(f"insufficient_history: required {config.min_train_days}, got {len(rows)}")
    try:
        import pandas as pd  # type: ignore
        from prophet import Prophet  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"prophet_unavailable:{exc.__class__.__name__}") from exc

    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
    train = rows[-config.train_window_days :] if config.train_window_days else rows
    frame = pd.DataFrame([{"ds": row.demand_date.isoformat(), "y": float(row.quantity)} for row in train])
    yearly_seasonality = config.yearly_seasonality
    if config.yearly_min_train_days is not None and len(rows) < config.yearly_min_train_days:
        yearly_seasonality = False
    factory = prophet_factory or Prophet
    model = factory(
        daily_seasonality=config.daily_seasonality,
        weekly_seasonality=config.weekly_seasonality,
        yearly_seasonality=yearly_seasonality,
        changepoint_prior_scale=config.changepoint_prior_scale,
        seasonality_prior_scale=config.seasonality_prior_scale,
    )
    model.fit(frame)
    future = model.make_future_dataframe(periods=horizon_days, freq="D", include_history=False)
    forecast = model.predict(future)
    return Decimal(str(forecast["yhat"].clip(lower=0).sum())).quantize(Decimal("0.01"))


def _training_range(rows: list[DemandHistory]) -> dict:
    return {
        "sample_count": len(rows),
        "start_date": rows[0].demand_date.isoformat(),
        "end_date": rows[-1].demand_date.isoformat(),
    }


def _evidence_ref(
    *,
    material_id: int,
    horizon_days: int,
    inventory_version: int,
    config_version: str,
    selected_model_name: str,
    train_end: str,
) -> str:
    return (
        f"forecast:{material_id}:{horizon_days}:inventory-v{inventory_version}:"
        f"{config_version}:{selected_model_name}:train-end-{train_end}"
    )


def _strategy_to_dict(strategy: ForecastStrategyConfig) -> dict:
    result = asdict(strategy)
    result["prophet"] = asdict(strategy.prophet)
    return result
