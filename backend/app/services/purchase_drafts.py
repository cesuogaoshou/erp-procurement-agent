import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import PurchaseOrder, PurchaseOrderItem, SupplierMaterial


@dataclass(frozen=True)
class DraftItemInput:
    material_id: int
    quantity: Decimal


@dataclass(frozen=True)
class PurchaseDraftInput:
    supplier_id: int
    items: list[DraftItemInput]
    idempotency_key: str
    evidence_refs: list[str]
    evidence_payloads: list[dict] | None = None


def create_purchase_draft(session: Session, request: PurchaseDraftInput) -> PurchaseOrder:
    if not request.evidence_refs:
        raise ValueError("evidence_required")
    if not request.items:
        raise ValueError("items_required")

    existing = session.scalar(
        select(PurchaseOrder).where(PurchaseOrder.idempotency_key == request.idempotency_key)
    )
    if existing is not None:
        return existing

    order_items: list[PurchaseOrderItem] = []
    total_amount = Decimal("0.00")
    for item in request.items:
        if item.quantity <= 0:
            raise ValueError("quantity_must_be_positive")
        relationship = session.scalar(
            select(SupplierMaterial).where(
                SupplierMaterial.supplier_id == request.supplier_id,
                SupplierMaterial.material_id == item.material_id,
            )
        )
        if relationship is None or not relationship.supplier.active:
            raise ValueError("supplier_material_not_found")
        order_quantity = _round_order_quantity(
            requested=item.quantity,
            moq=Decimal(relationship.moq),
            package_multiple=Decimal(relationship.package_multiple),
        )
        if order_quantity > relationship.capacity:
            raise ValueError("capacity_below_quantity")

        unit_price = Decimal(relationship.unit_price).quantize(Decimal("0.01"))
        line_amount = (unit_price * order_quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_amount += line_amount
        order_items.append(
            PurchaseOrderItem(
                material_id=item.material_id,
                quantity=order_quantity,
                unit_price=unit_price,
                line_amount=line_amount,
            )
        )

    order = PurchaseOrder(
        supplier_id=request.supplier_id,
        status="draft",
        idempotency_key=request.idempotency_key,
        total_amount=total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        evidence_refs_json=_evidence_json(request),
        items=order_items,
    )
    session.add(order)
    session.flush()
    return order


def _round_order_quantity(*, requested: Decimal, moq: Decimal, package_multiple: Decimal) -> Decimal:
    if package_multiple <= 0:
        raise ValueError("package_multiple_must_be_positive")
    base = max(requested, moq)
    units = (base / package_multiple).to_integral_value(rounding=ROUND_CEILING)
    return units * package_multiple


def _evidence_json(request: PurchaseDraftInput) -> str:
    if request.evidence_payloads is None:
        return json.dumps(request.evidence_refs, ensure_ascii=False)
    return json.dumps(
        {
            "refs": request.evidence_refs,
            "forecast_evidence": request.evidence_payloads,
        },
        ensure_ascii=False,
    )
