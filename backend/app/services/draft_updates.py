"""Buyer-owned manual edits for a pending purchase draft.

A manual edit is deliberately narrow: the supplier and material set stay the
same, only the requested quantities and the confirmed whole-order budget can
change. Every edit regenerates current forecast/recommendation evidence for
the final rounded quantity, so approval still validates server facts rather
than trusting the edited numbers.
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import AuditLog, PurchaseOrder, PurchaseOrderItem, SupplierMaterial
from backend.app.services.approvals import (
    ApprovalConflict,
    ApprovalPermissionError,
    ApprovalValidationError,
    AuthContext,
)
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.purchase_drafts import (
    DraftItemInput,
    PurchaseDraftInput,
    _round_order_quantity,
    aggregate_items,
    request_fingerprint,
)
from backend.app.services.recommendations import recommend_for_material


@dataclass(frozen=True)
class DraftUpdateItem:
    material_id: int
    quantity: Decimal


@dataclass(frozen=True)
class DraftUpdateInput:
    expected_order_version: int
    items: list[DraftUpdateItem]
    total_budget: Decimal | None = None


def update_purchase_draft(
    session: Session,
    order_id: int,
    auth: AuthContext,
    request: DraftUpdateInput,
) -> PurchaseOrder:
    if auth.role != "buyer":
        raise ApprovalPermissionError("buyer_role_required")

    order = session.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == order_id)
        .options(selectinload(PurchaseOrder.items), selectinload(PurchaseOrder.supplier))
        .with_for_update()
    )
    if order is None:
        raise ApprovalConflict("order_not_found")
    if order.status != "draft":
        raise ApprovalConflict("order_not_draft")
    if order.version != request.expected_order_version:
        raise ApprovalConflict("order_version_conflict")

    creator = session.scalar(
        select(AuditLog.actor_user_id)
        .where(AuditLog.order_id == order.id, AuditLog.action == "created_draft")
        .order_by(AuditLog.created_at, AuditLog.id)
        .limit(1)
    )
    if creator != auth.user_id:
        raise ApprovalPermissionError("order_owner_required")

    if not order.items:
        raise ApprovalValidationError("items_required")
    requested = {item.material_id: item.quantity for item in aggregate_items(request.items)}
    existing = {item.material_id: item for item in order.items}
    if set(requested) != set(existing):
        raise ApprovalValidationError("draft_items_must_match_existing_materials")

    budget = request.total_budget if request.total_budget is not None else order.total_budget
    if budget is None:
        raise ApprovalValidationError("budget_confirmation_required")
    if not budget.is_finite() or budget <= 0:
        raise ApprovalValidationError("budget_must_be_positive_finite")

    evidence = _load_evidence(order.evidence_refs_json)
    refs = evidence["refs"]
    forecast_refs = {ref.split(":")[1]: ref for ref in refs if ref.startswith("forecast:") and len(ref.split(":")) >= 3}
    recommendation_refs = {
        ref.split(":")[1]: ref for ref in refs if ref.startswith("recommendation:") and len(ref.split(":")) >= 5
    }
    supplier = order.supplier
    if supplier is None or not supplier.active:
        raise ApprovalValidationError("supplier_inactive")

    new_items: list[PurchaseOrderItem] = []
    new_refs: list[str] = []
    forecast_payloads: list[dict] = []
    total_amount = Decimal("0.00")

    for material_id, requested_quantity in sorted(requested.items()):
        forecast_ref = forecast_refs.get(str(material_id))
        if forecast_ref is None:
            raise ApprovalValidationError("forecast_evidence_required")
        forecast = _current_forecast(session, forecast_ref)
        if requested_quantity > Decimal(str(forecast["shortage_quantity"])):
            raise ApprovalValidationError("quantity_exceeds_forecast_shortage")

        recommendation_ref = recommendation_refs.get(str(material_id))
        if recommendation_ref is None:
            raise ApprovalValidationError("recommendation_evidence_required")
        _, rec_supplier_id, _, required_in_days, rec_budget = _parse_recommendation_ref(recommendation_ref)
        if rec_supplier_id != order.supplier_id:
            raise ApprovalValidationError("recommendation_evidence_invalid")

        relationship = session.scalar(
            select(SupplierMaterial).where(
                SupplierMaterial.supplier_id == order.supplier_id,
                SupplierMaterial.material_id == material_id,
            )
        )
        if relationship is None:
            raise ApprovalValidationError("supplier_material_not_found")
        if not relationship.supplier.active:
            raise ApprovalValidationError("supplier_inactive")
        rounded_quantity = _round_order_quantity(
            requested=requested_quantity,
            moq=Decimal(relationship.moq),
            package_multiple=Decimal(relationship.package_multiple),
        )
        if rounded_quantity > Decimal(relationship.capacity):
            raise ApprovalValidationError("capacity_below_quantity")

        recommendations = recommend_for_material(
            session=session,
            material_id=material_id,
            quantity=rounded_quantity,
            required_in_days=required_in_days,
            budget=rec_budget,
        )
        if not any(item.supplier_id == order.supplier_id for item in recommendations.recommendations):
            raise ApprovalValidationError("recommendation_evidence_invalid")

        unit_price = Decimal(relationship.unit_price).quantize(Decimal("0.01"))
        line_amount = (unit_price * rounded_quantity).quantize(Decimal("0.01"))
        new_items.append(
            PurchaseOrderItem(
                order_id=order.id,
                material_id=material_id,
                quantity=rounded_quantity,
                unit_price=unit_price,
                line_amount=line_amount,
            )
        )
        total_amount += line_amount
        new_refs.append(forecast_ref)
        new_refs.append(
            f"recommendation:{material_id}:{order.supplier_id}:{rounded_quantity}:{required_in_days}:"
            + ("none" if rec_budget is None else str(rec_budget))
        )
        forecast_payloads.append(forecast["forecast_evidence"])

    total_amount = total_amount.quantize(Decimal("0.01"))
    if total_amount > budget:
        raise ApprovalValidationError("order_budget_exceeded")

    order.items.clear()
    for item in new_items:
        order.items.append(item)
    order.total_amount = total_amount
    order.total_budget = budget
    order.requested_items_json = _requested_items_json(requested)
    order.evidence_refs_json = _evidence_json(
        refs=new_refs,
        forecast_payloads=forecast_payloads,
        user_request=evidence.get("user_request"),
        edited_by=auth.user_id,
    )
    order.request_fingerprint = request_fingerprint(
        PurchaseDraftInput(
            supplier_id=order.supplier_id,
            items=[DraftItemInput(material_id=material_id, quantity=quantity) for material_id, quantity in requested.items()],
            idempotency_key=order.idempotency_key,
            evidence_refs=new_refs,
            total_budget=budget,
        )
    )
    before_version = order.version
    order.version += 1
    order.updated_at = datetime.now(UTC)
    session.add(
        AuditLog(
            order_id=order.id,
            actor_user_id=auth.user_id,
            actor_role=auth.role,
            action="updated_draft",
            details_json=_audit_details(before_version, order.version, requested, budget),
        )
    )
    session.flush()
    return order


def _load_evidence(raw: str) -> dict:
    import json

    value = json.loads(raw or "{}")
    if isinstance(value, list):
        return {"refs": value, "forecast_evidence": []}
    value.setdefault("refs", [])
    value.setdefault("forecast_evidence", [])
    return value


def _current_forecast(session: Session, ref: str) -> dict:
    parts = ref.split(":")
    if len(parts) < 3 or parts[0] != "forecast":
        raise ApprovalValidationError("forecast_evidence_invalid")
    try:
        material_id = int(parts[1])
        horizon_days = int(parts[2])
    except ValueError as exc:
        raise ApprovalValidationError("forecast_evidence_invalid") from exc
    forecast = get_demand_forecast(session, material_id=material_id, horizon_days=horizon_days)
    if forecast["evidence_ref"] != ref:
        raise ApprovalValidationError("forecast_evidence_invalid")
    return forecast


def _parse_recommendation_ref(ref: str) -> tuple[int, int, Decimal, int, Decimal | None]:
    parts = ref.split(":")
    if len(parts) not in {5, 6}:
        raise ApprovalValidationError("recommendation_evidence_invalid")
    try:
        material_id = int(parts[1])
        supplier_id = int(parts[2])
        quantity = Decimal(parts[3])
        required_in_days = int(parts[4])
        budget = None if len(parts) == 5 or parts[5] == "none" else Decimal(parts[5])
    except (ValueError, ArithmeticError) as exc:
        raise ApprovalValidationError("recommendation_evidence_invalid") from exc
    return material_id, supplier_id, quantity, required_in_days, budget


def _requested_items_json(requested: dict[int, Decimal]) -> str:
    import json

    return json.dumps(
        [{"material_id": material_id, "quantity": str(quantity)} for material_id, quantity in sorted(requested.items())],
        ensure_ascii=False,
    )


def _evidence_json(*, refs: list[str], forecast_payloads: list[dict], user_request: dict | None, edited_by: str) -> str:
    import json

    return json.dumps(
        {
            "refs": refs,
            "forecast_evidence": forecast_payloads,
            "user_request": user_request,
            "manual_edit": {"edited_by": edited_by, "edited_at": datetime.now(UTC).isoformat()},
        },
        ensure_ascii=False,
    )


def _audit_details(before: int, after: int, requested: dict[int, Decimal], budget: Decimal) -> str:
    import json

    return json.dumps(
        {
            "version_before": before,
            "version_after": after,
            "items": [{"material_id": material_id, "quantity": str(quantity)} for material_id, quantity in sorted(requested.items())],
            "total_budget": str(budget),
        },
        ensure_ascii=False,
    )
