from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.algorithms.shortage import calculate_shortage
from backend.app.models import DemandHistory, Material
from backend.app.services.inventory import get_inventory_snapshot


def baseline_forecast(session: Session, material_id: int, horizon_days: int) -> dict:
    material = session.get(Material, material_id)
    if material is None:
        raise LookupError(f"material not found: {material_id}")

    rows = list(
        session.scalars(
            select(DemandHistory)
            .where(DemandHistory.material_id == material_id)
            .order_by(DemandHistory.demand_date.desc())
            .limit(30)
        )
    )
    if not rows:
        raise LookupError(f"demand history not found for material_id={material_id}")

    daily_average = sum(Decimal(row.quantity) for row in rows) / Decimal(len(rows))
    forecast_demand = (daily_average * Decimal(horizon_days)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    inventory = get_inventory_snapshot(session, material_id)
    shortage = calculate_shortage(
        forecast_demand=forecast_demand,
        safety_stock=Decimal(material.safety_stock),
        available_supply=Decimal(inventory["available_supply"]),
    )
    return {
        "material_id": material_id,
        "horizon_days": horizon_days,
        "model_name": "moving_average_30d_baseline",
        "forecast_demand": forecast_demand,
        "safety_stock": material.safety_stock,
        "available_supply": inventory["available_supply"],
        "shortage_quantity": shortage,
        "notes": ["Phase 1 simplification: confirmed inbound supply is not included."],
    }


def get_demand_forecast(session: Session, material_id: int, horizon_days: int) -> dict:
    forecast = baseline_forecast(session, material_id, horizon_days)
    inventory = get_inventory_snapshot(session, material_id)
    evidence_ref = f"forecast:{material_id}:{horizon_days}:{inventory['version']}"
    return {
        "tool_name": "get_demand_forecast",
        "evidence_ref": evidence_ref,
        "material_id": material_id,
        "horizon_days": horizon_days,
        "forecast_demand": forecast["forecast_demand"],
        "shortage_quantity": forecast["shortage_quantity"],
        "inventory": inventory,
        "model_name": forecast["model_name"],
        "notes": forecast["notes"],
    }
