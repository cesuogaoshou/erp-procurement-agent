import csv
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    DemandHistory,
    Inventory,
    Material,
    Supplier,
    SupplierMaterial,
    SupplierPerformance,
)
from backend.app.services.seed import DEMO_BASE_DATE, DEMO_HISTORY_DAYS, DEMO_SEED


def export_seed_dataset(session: Session, output_dir: str | Path) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    _write_csv(
        path / "materials.csv",
        ["id", "code", "name", "unit", "safety_stock"],
        [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "unit": item.unit,
                "safety_stock": item.safety_stock,
            }
            for item in session.scalars(select(Material).order_by(Material.id))
        ],
    )
    _write_csv(
        path / "inventory_snapshots.csv",
        ["material_id", "on_hand", "reserved", "version", "snapshot_date", "inbound_confirmed"],
        [
            {
                "material_id": item.material_id,
                "on_hand": item.on_hand,
                "reserved": item.reserved,
                "version": item.version,
                "snapshot_date": DEMO_BASE_DATE.isoformat(),
                "inbound_confirmed": Decimal("0"),
            }
            for item in session.scalars(select(Inventory).order_by(Inventory.material_id))
        ],
    )
    _write_csv(
        path / "demand_history.csv",
        ["material_id", "demand_date", "quantity"],
        [
            {
                "material_id": item.material_id,
                "demand_date": item.demand_date.isoformat(),
                "quantity": item.quantity,
            }
            for item in session.scalars(
                select(DemandHistory).order_by(DemandHistory.material_id, DemandHistory.demand_date)
            )
        ],
    )
    _write_csv(
        path / "suppliers.csv",
        ["id", "name", "active"],
        [
            {"id": item.id, "name": item.name, "active": item.active}
            for item in session.scalars(select(Supplier).order_by(Supplier.id))
        ],
    )
    _write_csv(
        path / "supplier_materials.csv",
        ["supplier_id", "material_id", "unit_price", "lead_time_days", "moq", "capacity"],
        [
            {
                "supplier_id": item.supplier_id,
                "material_id": item.material_id,
                "unit_price": item.unit_price,
                "lead_time_days": item.lead_time_days,
                "moq": item.moq,
                "capacity": item.capacity,
            }
            for item in session.scalars(
                select(SupplierMaterial).order_by(SupplierMaterial.material_id, SupplierMaterial.supplier_id)
            )
        ],
    )
    _write_csv(
        path / "supplier_performance.csv",
        [
            "supplier_id",
            "material_id",
            "observed_until",
            "avg_price",
            "promised_deliveries",
            "on_time_deliveries",
            "inspected_quantity",
            "accepted_quantity",
            "complaint_count",
        ],
        [
            {
                "supplier_id": item.supplier_id,
                "material_id": item.material_id,
                "observed_until": item.observed_until.isoformat(),
                "avg_price": item.avg_price,
                "promised_deliveries": item.promised_deliveries,
                "on_time_deliveries": item.on_time_deliveries,
                "inspected_quantity": item.inspected_quantity,
                "accepted_quantity": item.accepted_quantity,
                "complaint_count": item.complaint_count,
            }
            for item in session.scalars(
                select(SupplierPerformance).order_by(
                    SupplierPerformance.material_id,
                    SupplierPerformance.supplier_id,
                )
            )
        ],
    )
    _write_csv(path / "data_splits.csv", ["split", "start_date", "end_date"], _split_rows())
    (path / "generation_metadata.json").write_text(
        json.dumps(_metadata(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})


def _csv_value(value):
    if isinstance(value, Decimal):
        return str(value)
    return value


def _split_rows() -> list[dict[str, str]]:
    start = DEMO_BASE_DATE - timedelta(days=DEMO_HISTORY_DAYS)
    validation_start = DEMO_BASE_DATE - timedelta(days=120)
    test_start = DEMO_BASE_DATE - timedelta(days=60)
    return [
        {
            "split": "train",
            "start_date": start.isoformat(),
            "end_date": (validation_start - timedelta(days=1)).isoformat(),
        },
        {
            "split": "validation",
            "start_date": validation_start.isoformat(),
            "end_date": (test_start - timedelta(days=1)).isoformat(),
        },
        {
            "split": "test",
            "start_date": test_start.isoformat(),
            "end_date": (DEMO_BASE_DATE - timedelta(days=1)).isoformat(),
        },
    ]


def _metadata() -> dict:
    return {
        "dataset": "simulated_erp_procurement",
        "seed": DEMO_SEED,
        "history_days": DEMO_HISTORY_DAYS,
        "base_date": DEMO_BASE_DATE.isoformat(),
        "materials": 10,
        "suppliers": 10,
        "demand_pattern": "trend + weekly seasonality + annual seasonal bump + noise + intermittent spikes",
        "inventory_snapshot_date": DEMO_BASE_DATE.isoformat(),
        "inbound_supply_policy": "not modeled in Phase 1; inbound_confirmed is exported as 0",
        "encoding": "utf-8",
    }
