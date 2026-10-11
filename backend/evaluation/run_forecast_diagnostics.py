import csv
import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from sqlalchemy import select

from backend.app.algorithms.shortage import calculate_shortage
from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import DemandHistory, Inventory
from backend.app.services.seed import seed_demo_data
from backend.app.services.forecasting import ProphetForecastConfig, dynamic_prophet_config, frozen_forecast_strategy_config
from backend.evaluation.metrics import evaluate_regression
from backend.evaluation.run_baseline import _metrics_to_dict
from backend.evaluation.run_forecast_comparison import (
    _build_windows,
    _moving_average_predict,
)


OUTPUT_DIR = Path("reports/generated/forecast_diagnostics")
DEFAULT_REPORT_PATH = OUTPUT_DIR / "forecast_diagnostics.json"
DEFAULT_ROWS_PATH = OUTPUT_DIR / "forecast_window_diagnostics.csv"
DEFAULT_CURVE_DIR = OUTPUT_DIR / "curves"
SPLIT_PATH = Path("data/raw/data_splits.csv")


def main() -> None:
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        result = run_forecast_diagnostics(session)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_forecast_diagnostics(session, horizon_days: int = 30) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_CURVE_DIR.mkdir(parents=True, exist_ok=True)
    windows = _build_windows(session, horizon_days)
    splits = _load_splits(SPLIT_PATH)
    prophet_config = dynamic_prophet_config()
    rows = _build_window_rows(windows, prophet_config, splits)
    _write_rows(rows, DEFAULT_ROWS_PATH)
    curve_paths = _write_representative_curves(session, rows, DEFAULT_CURVE_DIR)
    validation_rows = [
        row
        for row in rows
        if row["holdout_start"] >= splits["validation"]["start_date"]
        and row["holdout_end"] <= splits["validation"]["end_date"]
    ]
    validation_grid = _run_validation_grid(validation_rows, windows)

    return {
        "generated_at": date.today().isoformat(),
        "dataset": "simulated_demo_seed_20261010",
        "horizon_days": horizon_days,
        "baseline_reference": "reports/generated/forecast_diagnostics/baseline_20261011",
        "row_output": str(DEFAULT_ROWS_PATH),
        "curve_outputs": curve_paths,
        "implementation_checks": _implementation_checks(session, windows, horizon_days),
        "inventory_scope": _inventory_scope(session),
        "split_usage": _split_usage(rows, splits),
        "data_shape": _data_shape_summary(session),
        "service_strategy_config": asdict(frozen_forecast_strategy_config()),
        "selected_prophet_config": _config_to_report(prophet_config),
        "validation_grid": validation_grid,
        "model_diagnostics": _model_diagnostics(rows),
        "notes": [
            "Diagnostics use the already-inspected rolling windows; they are not an untouched final test set.",
            "The frozen demand data and recommendation labels were not regenerated or modified.",
            "Shortage metrics are a fixed-inventory scenario using the same static 2026-10-10 inventory snapshot for all windows.",
        ],
    }


def _build_window_rows(windows: list[dict], config: ProphetForecastConfig, splits: dict[str, dict[str, str]]) -> list[dict]:
    rows = []
    prophet_predict = _make_prophet_predictor(config)
    for window in windows:
        metadata = window["metadata"]
        actual_demand = sum(Decimal(row.quantity) for row in window["holdout"])
        ma_demand = _moving_average_predict(window)
        available_supply = Decimal(window["inventory"].on_hand) - Decimal(window["inventory"].reserved)
        safety_stock = Decimal(window["material"].safety_stock)
        actual_shortage = calculate_shortage(actual_demand, safety_stock, available_supply)
        ma_shortage = calculate_shortage(ma_demand, safety_stock, available_supply)
        row = {
            **metadata,
            "split_overlap": _classify_window(metadata, splits),
            "train_sample_count": len(window["train"]),
            "holdout_sample_count": len(window["holdout"]),
            "available_supply": str(available_supply),
            "safety_stock": str(safety_stock),
            "actual_demand": str(actual_demand),
            "moving_average_demand": str(ma_demand),
            "moving_average_demand_error": str(abs(actual_demand - ma_demand)),
            "moving_average_demand_ape_percent": _percent_error(actual_demand, ma_demand),
            "actual_shortage": str(actual_shortage),
            "moving_average_shortage": str(ma_shortage),
            "moving_average_shortage_error": str(abs(actual_shortage - ma_shortage)),
            "moving_average_shortage_ape_percent": _percent_error(actual_shortage, ma_shortage),
            "prophet_status": "ok",
            "prophet_demand": "",
            "prophet_demand_error": "",
            "prophet_demand_ape_percent": "",
            "prophet_shortage": "",
            "prophet_shortage_error": "",
            "prophet_shortage_ape_percent": "",
            "prophet_error": "",
        }
        try:
            prophet_demand = prophet_predict(window)
            prophet_shortage = calculate_shortage(prophet_demand, safety_stock, available_supply)
            row.update(
                {
                    "prophet_demand": str(prophet_demand),
                    "prophet_demand_error": str(abs(actual_demand - prophet_demand)),
                    "prophet_demand_ape_percent": _percent_error(actual_demand, prophet_demand),
                    "prophet_shortage": str(prophet_shortage),
                    "prophet_shortage_error": str(abs(actual_shortage - prophet_shortage)),
                    "prophet_shortage_ape_percent": _percent_error(actual_shortage, prophet_shortage),
                }
            )
        except Exception as exc:
            row["prophet_status"] = "failed"
            row["prophet_error"] = str(exc)
        rows.append(row)
    return rows


def _make_prophet_predictor(config: ProphetForecastConfig):
    from prophet import Prophet  # type: ignore

    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

    def predict(window: dict) -> Decimal:
        import pandas as pd  # type: ignore

        if len(window["train"]) < config.min_train_days:
            raise ValueError(f"insufficient_history: required {config.min_train_days}, got {len(window['train'])}")
        train = window["train"][-config.train_window_days :] if config.train_window_days else window["train"]
        frame = pd.DataFrame([{"ds": row.demand_date.isoformat(), "y": float(row.quantity)} for row in train])
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

    return predict


def _run_validation_grid(validation_rows: list[dict], windows: list[dict]) -> list[dict]:
    if not validation_rows:
        return []
    validation_keys = {(row["material_id"], row["cutoff_date"]) for row in validation_rows}
    validation_windows = [
        window
        for window in windows
        if (window["metadata"]["material_id"], window["metadata"]["cutoff_date"]) in validation_keys
    ]
    configs = [
        ProphetForecastConfig(name="weekly_yearly_min365", min_train_days=365),
        dynamic_prophet_config(),
        ProphetForecastConfig(name="weekly_only_min90", min_train_days=90, yearly_seasonality=False, short_history_mode="weekly_only"),
        ProphetForecastConfig(name="trend_only_min180", min_train_days=180, weekly_seasonality=False, yearly_seasonality=False),
        ProphetForecastConfig(name="weekly_only_recent180", min_train_days=180, train_window_days=180, yearly_seasonality=False, short_history_mode="weekly_only"),
    ]
    results = []
    for config in configs:
        predictor = _make_prophet_predictor(config)
        started = time.perf_counter()
        actual = []
        predicted = []
        failures = []
        for window in validation_windows:
            try:
                actual.append(sum(Decimal(row.quantity) for row in window["holdout"]))
                predicted.append(predictor(window))
            except Exception as exc:
                failures.append({"window": window["metadata"], "error": str(exc)})
        item = {
            "config": _config_to_report(config),
            "runtime_ms": int((time.perf_counter() - started) * 1000),
            "failures": failures,
        }
        if predicted:
            item["demand_metrics"] = _metrics_to_dict(evaluate_regression(actual, predicted))
        results.append(item)
    return results


def _implementation_checks(session, windows: list[dict], horizon_days: int) -> dict:
    issues = []
    for window in windows:
        train_dates = [row.demand_date for row in window["train"]]
        holdout_dates = [row.demand_date for row in window["holdout"]]
        if train_dates != sorted(train_dates) or holdout_dates != sorted(holdout_dates):
            issues.append({"window": window["metadata"], "issue": "dates_not_sorted"})
        if train_dates[-1] >= holdout_dates[0]:
            issues.append({"window": window["metadata"], "issue": "train_overlaps_holdout"})
        if len(holdout_dates) != horizon_days:
            issues.append({"window": window["metadata"], "issue": "holdout_length_mismatch"})
        if _missing_dates(train_dates):
            issues.append({"window": window["metadata"], "issue": "missing_train_dates"})
        if _missing_dates(holdout_dates):
            issues.append({"window": window["metadata"], "issue": "missing_holdout_dates"})
    demand_date_range = session.execute(
        select(DemandHistory.material_id, DemandHistory.demand_date).order_by(DemandHistory.material_id, DemandHistory.demand_date)
    ).all()
    return {
        "window_count": len(windows),
        "issues": issues,
        "demand_rows_checked": len(demand_date_range),
        "checks": [
            "train dates sorted before holdout",
            "holdout length equals horizon",
            "train and holdout daily continuity",
            "negative Prophet predictions clipped before 30-day sum",
            "shortage formula reused from backend calculate_shortage",
        ],
    }


def _inventory_scope(session) -> dict:
    inventory_rows = list(session.scalars(select(Inventory).order_by(Inventory.material_id)))
    return {
        "experiment_type": "fixed_inventory_scenario",
        "snapshot_date": "2026-10-10",
        "inventory_row_count": len(inventory_rows),
        "can_reconstruct_historical_inventory": False,
        "reason": (
            "The available seed/export data contains one static inventory row per material and no dated "
            "historical inventory movement table. Therefore the shortage evaluation is not a true historical "
            "inventory backtest."
        ),
    }


def _data_shape_summary(session) -> dict:
    result = {}
    for material_id in session.scalars(select(DemandHistory.material_id).distinct().order_by(DemandHistory.material_id)):
        rows = list(
            session.scalars(
                select(DemandHistory)
                .where(DemandHistory.material_id == material_id)
                .order_by(DemandHistory.demand_date)
            )
        )
        values = [Decimal(row.quantity) for row in rows]
        first_30 = sum(values[:30])
        last_30 = sum(values[-30:])
        result[str(material_id)] = {
            "row_count": len(rows),
            "start_date": rows[0].demand_date.isoformat(),
            "end_date": rows[-1].demand_date.isoformat(),
            "min_daily": str(min(values)),
            "max_daily": str(max(values)),
            "first_30d_sum": str(first_30),
            "last_30d_sum": str(last_30),
            "last_vs_first_30d_delta": str(last_30 - first_30),
        }
    return result


def _model_diagnostics(rows: list[dict]) -> dict:
    ok_prophet_rows = [row for row in rows if row["prophet_status"] == "ok"]
    by_cutoff = defaultdict(list)
    by_material = defaultdict(list)
    for row in rows:
        by_cutoff[row["cutoff_date"]].append(row)
        by_material[row["material_id"]].append(row)
    return {
        "moving_average": _metrics_from_rows(rows, "moving_average"),
        "prophet_successful_windows": _metrics_from_rows(ok_prophet_rows, "prophet"),
        "prophet_failure_count": len(rows) - len(ok_prophet_rows),
        "prophet_failure_reasons": _failure_reasons(rows),
        "by_cutoff": [_group_summary(cutoff, group) for cutoff, group in sorted(by_cutoff.items())],
        "by_material": [_group_summary(material_id, group) for material_id, group in sorted(by_material.items(), key=lambda item: int(item[0]))],
        "worst_prophet_windows": sorted(
            ok_prophet_rows,
            key=lambda row: Decimal(row["prophet_demand_ape_percent"] or "0"),
            reverse=True,
        )[:10],
    }


def _metrics_from_rows(rows: list[dict], prefix: str) -> dict:
    actual_demand = []
    predicted_demand = []
    actual_shortage = []
    predicted_shortage = []
    for row in rows:
        demand_key = f"{prefix}_demand"
        shortage_key = f"{prefix}_shortage"
        if row.get(demand_key) in ("", None):
            continue
        actual_demand.append(Decimal(row["actual_demand"]))
        predicted_demand.append(Decimal(row[demand_key]))
        actual_shortage.append(Decimal(row["actual_shortage"]))
        predicted_shortage.append(Decimal(row[shortage_key]))
    if not actual_demand:
        return {"sample_count": 0}
    return {
        "demand_metrics": _metrics_to_dict(evaluate_regression(actual_demand, predicted_demand)),
        "shortage_metrics": _metrics_to_dict(evaluate_regression(actual_shortage, predicted_shortage)),
        "zero_shortage_coverage": _zero_shortage_coverage(actual_shortage, predicted_shortage),
    }


def _group_summary(group_key, rows: list[dict]) -> dict:
    return {
        "group": str(group_key),
        "sample_count": len(rows),
        "avg_train_sample_count": str((sum(Decimal(row["train_sample_count"]) for row in rows) / Decimal(len(rows))).quantize(Decimal("0.01"))),
        "moving_average_demand_mape_percent": _average_decimal(row["moving_average_demand_ape_percent"] for row in rows),
        "prophet_ok_count": sum(1 for row in rows if row["prophet_status"] == "ok"),
        "prophet_demand_mape_percent": _average_decimal(
            row["prophet_demand_ape_percent"] for row in rows if row["prophet_status"] == "ok"
        ),
    }


def _split_usage(rows: list[dict], splits: dict[str, dict[str, str]]) -> dict:
    counts = defaultdict(int)
    for row in rows:
        counts[row["split_overlap"]] += 1
    return {
        "declared_splits": splits,
        "window_overlap_counts": dict(sorted(counts.items())),
        "unused_tail_days_for_30d_stride": {
            "start": "2026-09-25",
            "end": "2026-10-09",
            "note": "The 30-day stride cannot form another complete 30-day holdout before data ends.",
        },
    }


def _write_rows(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_representative_curves(session, rows: list[dict], curve_dir: Path) -> list[str]:
    import matplotlib.pyplot as plt  # type: ignore

    curve_dir.mkdir(parents=True, exist_ok=True)
    selected = []
    failed = next((row for row in rows if row["prophet_status"] == "failed"), None)
    ok_rows = [row for row in rows if row["prophet_status"] == "ok"]
    worst = max(ok_rows, key=lambda row: Decimal(row["prophet_demand_ape_percent"] or "0")) if ok_rows else None
    best = min(ok_rows, key=lambda row: Decimal(row["prophet_demand_ape_percent"] or "0")) if ok_rows else None
    for row in (failed, worst, best):
        if row and (row["material_id"], row["cutoff_date"]) not in {(item["material_id"], item["cutoff_date"]) for item in selected}:
            selected.append(row)

    paths = []
    for row in selected:
        history = list(
            session.scalars(
                select(DemandHistory)
                .where(DemandHistory.material_id == int(row["material_id"]))
                .order_by(DemandHistory.demand_date)
            )
        )
        holdout_start = _parse_date(row["holdout_start"])
        holdout_end = _parse_date(row["holdout_end"])
        plot_rows = [item for item in history if holdout_start.replace(day=1) <= item.demand_date <= holdout_end]
        plt.figure(figsize=(9, 4))
        plt.plot([item.demand_date for item in plot_rows], [float(item.quantity) for item in plot_rows], label="actual daily demand")
        plt.axvline(holdout_start, color="black", linestyle="--", linewidth=1, label="forecast cutoff")
        title = f"material {row['material_id']} cutoff {row['cutoff_date']} prophet {row['prophet_status']}"
        plt.title(title)
        plt.xlabel("date")
        plt.ylabel("daily demand")
        plt.legend()
        plt.tight_layout()
        path = curve_dir / f"material_{row['material_id']}_cutoff_{row['cutoff_date']}.png"
        plt.savefig(path)
        plt.close()
        paths.append(str(path))
    return paths


def _load_splits(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            row["split"]: {
                "start_date": row["start_date"],
                "end_date": row["end_date"],
            }
            for row in reader
        }


def _classify_window(metadata: dict, splits: dict[str, dict[str, str]]) -> str:
    start = metadata["holdout_start"]
    end = metadata["holdout_end"]
    train_end = metadata["train_end"]
    for name, bounds in splits.items():
        if start >= bounds["start_date"] and end <= bounds["end_date"]:
            if name == "test" and train_end >= bounds["start_date"]:
                return "test_holdout_with_test_training"
            return f"{name}_holdout"
    if start <= splits["test"]["end_date"] and end >= splits["test"]["start_date"]:
        return "overlaps_test_holdout"
    if start <= splits["validation"]["end_date"] and end >= splits["validation"]["start_date"]:
        return "overlaps_validation_holdout"
    return "outside_declared_split"


def _failure_reasons(rows: list[dict]) -> dict[str, int]:
    counts = defaultdict(int)
    for row in rows:
        if row["prophet_status"] == "failed":
            reason = row["prophet_error"].split(":", 1)[0]
            counts[reason] += 1
    return dict(sorted(counts.items()))


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


def _average_decimal(values: Iterable[str]) -> str | None:
    valid = [Decimal(value) for value in values if value not in ("", None)]
    if not valid:
        return None
    return str((sum(valid) / Decimal(len(valid))).quantize(Decimal("0.01")))


def _percent_error(actual: Decimal, predicted: Decimal) -> str | None:
    if actual == 0:
        return None
    return str((abs(actual - predicted) / abs(actual) * Decimal("100")).quantize(Decimal("0.01")))


def _missing_dates(values: list[date]) -> bool:
    return any((right - left).days != 1 for left, right in zip(values, values[1:], strict=False))


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _config_to_report(config: ProphetForecastConfig) -> dict:
    return {
        "name": config.name,
        "min_train_days": config.min_train_days,
        "train_window_days": config.train_window_days,
        "daily_seasonality": config.daily_seasonality,
        "weekly_seasonality": config.weekly_seasonality,
        "yearly_seasonality": config.yearly_seasonality,
        "yearly_min_train_days": config.yearly_min_train_days,
        "short_history_mode": config.short_history_mode,
        "changepoint_prior_scale": config.changepoint_prior_scale,
        "seasonality_prior_scale": config.seasonality_prior_scale,
    }


if __name__ == "__main__":
    main()
