import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import PurchaseOrder, PurchaseOrderItem, SupplierMaterial
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.recommendations import recommend_for_material


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
        _validate_item_evidence(
            session=session,
            request=request,
            item=item,
            order_quantity=order_quantity,
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


def _validate_item_evidence(
    *,
    session: Session,
    request: PurchaseDraftInput,
    item: DraftItemInput,
    order_quantity: Decimal,
) -> None:
    forecast = _forecast_evidence_for_item(session, request, item.material_id)
    if item.quantity > Decimal(str(forecast["shortage_quantity"])):
        raise ValueError("quantity_exceeds_forecast_shortage")
    recommendation = _recommendation_evidence_for_item(request, item.material_id)
    if recommendation is None:
        raise ValueError("recommendation_evidence_required")
    rec_material_id, rec_supplier_id, rec_quantity, required_in_days, budget = recommendation
    if rec_material_id != item.material_id or rec_supplier_id != request.supplier_id:
        raise ValueError("recommendation_evidence_invalid")
    if rec_quantity < order_quantity:
        raise ValueError("recommendation_evidence_invalid")
    result = recommend_for_material(
        session=session,
        material_id=item.material_id,
        quantity=rec_quantity,
        required_in_days=required_in_days,
        budget=budget,
    )
    if not any(item.supplier_id == request.supplier_id for item in result.recommendations):
        raise ValueError("recommendation_evidence_invalid")


def _forecast_evidence_for_item(session: Session, request: PurchaseDraftInput, material_id: int) -> dict:
    payloads = request.evidence_payloads or []
    for payload in payloads:
        if int(payload.get("material_id", -1)) == material_id:
            ref = str(payload.get("evidence_ref", ""))
            current = _current_forecast_for_ref(session, ref)
            if current["evidence_ref"] != ref:
                raise ValueError("forecast_evidence_invalid")
            return current
    refs = [ref for ref in request.evidence_refs if ref.startswith(f"forecast:{material_id}:")]
    if not refs:
        raise ValueError("forecast_evidence_required")
    current = _current_forecast_for_ref(session, refs[0])
    if current["evidence_ref"] != refs[0]:
        raise ValueError("forecast_evidence_invalid")
    return current


def _current_forecast_for_ref(session: Session, ref: str) -> dict:
    parts = ref.split(":")
    if len(parts) < 3 or parts[0] != "forecast":
        raise ValueError("forecast_evidence_invalid")
    try:
        material_id = int(parts[1])
        horizon_days = int(parts[2])
    except ValueError as exc:
        raise ValueError("forecast_evidence_invalid") from exc
    return get_demand_forecast(session, material_id=material_id, horizon_days=horizon_days)


def _recommendation_evidence_for_item(
    request: PurchaseDraftInput,
    material_id: int,
) -> tuple[int, int, Decimal, int, Decimal | None] | None:
    prefix = f"recommendation:{material_id}:"
    for ref in request.evidence_refs:
        if not ref.startswith(prefix):
            continue
        parts = ref.split(":")
        if len(parts) not in {5, 6}:
            raise ValueError("recommendation_evidence_invalid")
        try:
            rec_material_id = int(parts[1])
            rec_supplier_id = int(parts[2])
            rec_quantity = Decimal(parts[3])
            required_in_days = int(parts[4])
            budget = None if len(parts) == 5 or parts[5] == "none" else Decimal(parts[5])
        except (ValueError, ArithmeticError) as exc:
            raise ValueError("recommendation_evidence_invalid") from exc
        return rec_material_id, rec_supplier_id, rec_quantity, required_in_days, budget
    return None


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
