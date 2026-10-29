import json
import hashlib
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.exc import IntegrityError

from backend.app.models import PurchaseOrder, PurchaseOrderItem, SupplierMaterial
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.recommendations import recommend_for_material
from backend.app.schemas.procurement import ForecastRequest, RecommendationIn


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
    total_budget: Decimal | None = None


def create_purchase_draft(session: Session, request: PurchaseDraftInput) -> PurchaseOrder:
    if not request.evidence_refs:
        raise ValueError("evidence_required")
    if not request.items:
        raise ValueError("items_required")

    existing = session.scalar(
        select(PurchaseOrder).where(PurchaseOrder.idempotency_key == request.idempotency_key)
    )
    if existing is not None:
        validate_replay(existing, request)
        return existing

    if request.total_budget is None:
        raise ValueError("budget_confirmation_required")
    if not request.total_budget.is_finite() or request.total_budget <= 0:
        raise ValueError("budget_must_be_positive_finite")

    order_items: list[PurchaseOrderItem] = []
    total_amount = Decimal("0.00")
    aggregated = aggregate_items(request.items)
    for item in aggregated:
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
        # Requested aggregate is checked before rounding. MOQ/package rounding
        # is allowed above shortage, but only with capacity and evidence support.
        forecast = _forecast_evidence_for_item(session, request, item.material_id)
        if item.quantity > Decimal(str(forecast["shortage_quantity"])):
            raise ValueError("quantity_exceeds_forecast_shortage")
        if order_quantity > relationship.capacity:
            raise ValueError("capacity_below_quantity")
        _validate_item_evidence(
            session=session,
            request=request,
            item=item,
            order_quantity=order_quantity,
        )

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

    if total_amount > request.total_budget:
        raise ValueError("order_budget_exceeded")
    order = PurchaseOrder(
        supplier_id=request.supplier_id,
        status="draft",
        idempotency_key=request.idempotency_key,
        total_amount=total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        total_budget=request.total_budget,
        request_fingerprint=request_fingerprint(request),
        requested_items_json=json.dumps([{ "material_id": item.material_id, "quantity": str(item.quantity)} for item in aggregated]),
        evidence_refs_json=_evidence_json(request),
        items=order_items,
    )
    try:
        # Savepoint rollback leaves the caller's run/log transaction usable.
        with session.begin_nested():
            session.add(order)
            session.flush()
    except IntegrityError as exc:
        if not is_idempotency_collision(exc):
            raise
        # Locking read sees the winner even under MySQL REPEATABLE READ.
        existing = session.scalar(select(PurchaseOrder).where(
            PurchaseOrder.idempotency_key == request.idempotency_key).with_for_update())
        if existing is None:
            raise
        # Lazy loading would use the transaction's old consistent snapshot and
        # could return no items. Both winner and items require current reads.
        items = list(session.scalars(select(PurchaseOrderItem).where(
            PurchaseOrderItem.order_id == existing.id).with_for_update()))
        set_committed_value(existing, "items", items)
        validate_replay(existing, request)
        return existing
    return order


def aggregate_items(items: list[DraftItemInput]) -> list[DraftItemInput]:
    quantities: dict[int, Decimal] = {}
    for item in items:
        if not item.quantity.is_finite() or item.quantity <= 0:
            raise ValueError("quantity_must_be_positive_finite")
        quantities[item.material_id] = quantities.get(item.material_id, Decimal("0")) + item.quantity
    return [DraftItemInput(material, quantity) for material, quantity in sorted(quantities.items())]


def request_fingerprint(request: PurchaseDraftInput) -> str:
    def canonical_decimal(value):
        try:
            number = Decimal(value)
            if not number.is_finite() or number <= 0:
                raise ValueError("recommendation_evidence_invalid")
            return format(number.normalize(), "f")
        except ArithmeticError as exc:
            raise ValueError("recommendation_evidence_invalid") from exc
    refs = []
    for ref in request.evidence_refs:
        parts = ref.split(":")
        if parts[0] == "recommendation" and len(parts) in {5, 6}:
            parts[3] = canonical_decimal(parts[3])
            if len(parts) == 6 and parts[5] != "none":
                parts[5] = canonical_decimal(parts[5])
        refs.append(":".join(parts))
    payload = {"supplier_id": request.supplier_id,
               "items": [(item.material_id, canonical_decimal(item.quantity)) for item in aggregate_items(request.items)],
               "total_budget": None if request.total_budget is None else canonical_decimal(request.total_budget),
               "evidence_refs": sorted(set(refs))}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def validate_replay(order: PurchaseOrder, request: PurchaseDraftInput) -> None:
    if order.request_fingerprint is None:
        raise ValueError("idempotency_payload_unknown")
    if order.request_fingerprint != request_fingerprint(request):
        raise ValueError("idempotency_payload_conflict")


def is_idempotency_collision(exc: IntegrityError) -> bool:
    args = getattr(exc.orig, "args", ())
    if args and args[0] == 1062:
        # Match ONLY the order idempotency index, not other unique constraints.
        message = str(args[1])
        return any(f"'{key}'" in message for key in (
            "purchase_orders.idempotency_key", "idempotency_key",
            "purchase_orders.ix_purchase_orders_idempotency_key", "ix_purchase_orders_idempotency_key"))
    return "UNIQUE constraint failed: purchase_orders.idempotency_key" == str(exc.orig)


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
        ForecastRequest(material_id=material_id, horizon_days=horizon_days)
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
            RecommendationIn(material_id=rec_material_id, quantity=rec_quantity,
                             required_in_days=required_in_days, budget=budget)
            if rec_supplier_id <= 0:
                raise ValueError("invalid_supplier_id")
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
