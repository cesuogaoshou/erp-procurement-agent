from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.algorithms.recommendation import (
    RecommendationRequest,
    SupplierCandidate,
    recommend_suppliers,
)
from backend.app.models import SupplierMaterial, SupplierPerformance


def recommend_for_material(
    session: Session,
    material_id: int,
    quantity: Decimal,
    required_in_days: int,
    budget: Decimal | None,
):
    rows = list(
        session.scalars(
            select(SupplierMaterial).where(SupplierMaterial.material_id == material_id)
        )
    )
    candidates = [_candidate_from_row(session, row) for row in rows]
    return recommend_suppliers(
        RecommendationRequest(
            material_id=material_id,
            quantity=quantity,
            required_in_days=required_in_days,
            budget=budget,
        ),
        candidates,
    )


def _candidate_from_row(session: Session, row: SupplierMaterial) -> SupplierCandidate:
    performance = session.scalar(
        select(SupplierPerformance)
        .where(
            SupplierPerformance.supplier_id == row.supplier_id,
            SupplierPerformance.material_id == row.material_id,
        )
        .order_by(SupplierPerformance.observed_until.desc())
        .limit(1)
    )
    if performance is None:
        on_time_rate = Decimal("0.50")
        quality_rate = Decimal("0.50")
        complaint_rate = Decimal("0.10")
    else:
        on_time_rate = Decimal(performance.on_time_deliveries) / Decimal(performance.promised_deliveries)
        quality_rate = Decimal(performance.accepted_quantity) / Decimal(performance.inspected_quantity)
        complaint_rate = Decimal(performance.complaint_count) / Decimal(performance.promised_deliveries)

    return SupplierCandidate(
        supplier_id=row.supplier_id,
        supplier_name=row.supplier.name,
        active=row.supplier.active,
        material_id=row.material_id,
        unit_price=Decimal(row.unit_price),
        lead_time_days=row.lead_time_days,
        capacity=Decimal(row.capacity),
        moq=Decimal(row.moq),
        on_time_rate=on_time_rate.quantize(Decimal("0.0001")),
        quality_rate=quality_rate.quantize(Decimal("0.0001")),
        complaint_rate=complaint_rate.quantize(Decimal("0.0001")),
    )
