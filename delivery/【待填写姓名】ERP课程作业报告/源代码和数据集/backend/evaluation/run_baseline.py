import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from backend.app.algorithms.shortage import calculate_shortage
from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import DemandHistory, Inventory, Material
from backend.app.services.seed import seed_demo_data
from backend.evaluation.metrics import evaluate_regression


def main() -> None:
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        result = run_shortage_backtest(session)

    output_path = Path("reports/generated/baseline_eval.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_shortage_backtest(session, horizon_days: int = 30) -> dict:
    actual_shortages: list[Decimal] = []
    predicted_shortages: list[Decimal] = []
    actual_demands: list[Decimal] = []
    predicted_demands: list[Decimal] = []
    windows: list[dict] = []

    materials = list(session.scalars(select(Material).order_by(Material.id)))
    for material in materials:
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
            train = history[cutoff_index - 30 : cutoff_index]
            holdout = history[cutoff_index : cutoff_index + horizon_days]
            predicted_demand = sum(Decimal(row.quantity) for row in train)
            actual_demand = sum(Decimal(row.quantity) for row in holdout)
            available_supply = Decimal(inventory.on_hand) - Decimal(inventory.reserved)
            predicted_shortage = calculate_shortage(
                forecast_demand=predicted_demand,
                safety_stock=Decimal(material.safety_stock),
                available_supply=available_supply,
            )
            actual_shortage = calculate_shortage(
                forecast_demand=actual_demand,
                safety_stock=Decimal(material.safety_stock),
                available_supply=available_supply,
            )
            predicted_demands.append(predicted_demand)
            actual_demands.append(actual_demand)
            predicted_shortages.append(predicted_shortage)
            actual_shortages.append(actual_shortage)
            windows.append(
                {
                    "material_id": material.id,
                    "cutoff_date": holdout[0].demand_date.isoformat(),
                    "train_start": train[0].demand_date.isoformat(),
                    "train_end": train[-1].demand_date.isoformat(),
                    "holdout_start": holdout[0].demand_date.isoformat(),
                    "holdout_end": holdout[-1].demand_date.isoformat(),
                }
            )

    shortage_metrics = evaluate_regression(actual_shortages, predicted_shortages)
    demand_metrics = evaluate_regression(actual_demands, predicted_demands)
    return {
        "generated_at": date.today().isoformat(),
        "dataset": "simulated_demo_seed_20261010",
        "horizon_days": horizon_days,
        "shortage_metrics": _metrics_to_dict(shortage_metrics),
        "demand_metrics": _metrics_to_dict(demand_metrics),
        "backtest_windows": windows,
        "notes": [
            "Baseline uses 30-day moving sum from simulated data.",
            "Phase 1 simplification: confirmed inbound supply is not included.",
            "Shortage MAPE excludes actual zero-shortage samples and reports coverage counts.",
        ],
    }


def _metrics_to_dict(metrics) -> dict:
    return {
        "sample_count": metrics.sample_count,
        "positive_actual_count": metrics.positive_actual_count,
        "zero_actual_count": metrics.zero_actual_count,
        "mape_coverage_percent": str(metrics.mape_coverage_percent),
        "mape_percent": _decimal_or_none(metrics.mape_percent),
        "mae": str(metrics.mae),
        "wape_percent": _decimal_or_none(metrics.wape_percent),
    }


def _decimal_or_none(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


if __name__ == "__main__":
    main()
