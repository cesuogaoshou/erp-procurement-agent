import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import AgentRun, ApprovalRecord, AuditLog, PurchaseOrder, SupplierMaterial


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str


@dataclass(frozen=True)
class ApprovalActionInput:
    expected_order_version: int
    idempotency_key: str
    reason: str | None = None
    body_actor_user_id: str | None = None
    body_actor_role: str | None = None


class ApprovalPermissionError(PermissionError):
    pass


class ApprovalConflict(ValueError):
    pass


class ApprovalValidationError(ValueError):
    pass


def submit_for_approval(session: Session, order_id: int, auth: AuthContext) -> PurchaseOrder:
    if auth.role != "buyer":
        raise ApprovalPermissionError("buyer_role_required")
    order = _locked_order(session, order_id)
    if order.status == "pending_approval":
        return order
    if order.status != "draft":
        raise ApprovalConflict("order_not_draft")
    order.status = "pending_approval"
    order.version += 1
    order.updated_at = datetime.now(UTC)
    _add_audit_log(
        session,
        order_id=order.id,
        auth=auth,
        action="submitted_for_approval",
        details={"version": order.version},
    )
    session.flush()
    return order


def approve_order(
    session: Session,
    order_id: int,
    auth: AuthContext,
    request: ApprovalActionInput,
) -> PurchaseOrder:
    return _decide_order(session, order_id, auth, request, decision="approved")


def reject_order(
    session: Session,
    order_id: int,
    auth: AuthContext,
    request: ApprovalActionInput,
) -> PurchaseOrder:
    return _decide_order(session, order_id, auth, request, decision="rejected")


def _decide_order(
    session: Session,
    order_id: int,
    auth: AuthContext,
    request: ApprovalActionInput,
    decision: str,
) -> PurchaseOrder:
    if auth.role != "approver":
        raise ApprovalPermissionError("approver_role_required")

    existing_record = session.scalar(
        select(ApprovalRecord).where(ApprovalRecord.idempotency_key == request.idempotency_key)
    )
    if existing_record is not None:
        if existing_record.order_id != order_id or existing_record.decision != decision:
            raise ApprovalConflict("idempotency_key_conflict")
        return _order(session, order_id)

    order = _locked_order(session, order_id)
    if order.status != "pending_approval":
        raise ApprovalConflict("order_not_pending_approval")
    if order.version != request.expected_order_version:
        raise ApprovalConflict("order_version_conflict")
    if decision == "approved":
        _validate_order_snapshot(session, order)

    before = order.version
    order.version += 1
    order.updated_at = datetime.now(UTC)
    order.status = "approved" if decision == "approved" else "rejected"
    if decision == "approved":
        order.formal_order_number = f"PO-{order.id:06d}"

    session.add(
        ApprovalRecord(
            order_id=order.id,
            actor_user_id=auth.user_id,
            decision=decision,
            idempotency_key=request.idempotency_key,
            order_version_before=before,
            order_version_after=order.version,
            reason=request.reason,
        )
    )
    _add_audit_log(
        session,
        order_id=order.id,
        auth=auth,
        action=decision,
        details={
            "version_before": before,
            "version_after": order.version,
            "formal_order_number": order.formal_order_number,
            "reason": request.reason,
        },
    )
    session.flush()
    return order


def _validate_order_snapshot(session: Session, order: PurchaseOrder) -> None:
    from backend.app.services.purchase_drafts import (
        DraftItemInput, PurchaseDraftInput, aggregate_items, _validate_item_evidence, _round_order_quantity,
    )
    if not order.items:
        raise ApprovalValidationError("items_required")
    if not order.supplier.active:
        raise ApprovalValidationError("supplier_inactive")
    if order.total_budget is None:
        raise ApprovalValidationError("budget_confirmation_required")

    evidence = json.loads(order.evidence_refs_json)
    refs = evidence.get("refs", []) if isinstance(evidence, dict) else evidence
    manual_edit = isinstance(evidence, dict) and bool(evidence.get("manual_edit"))
    # The origin is discovered independently of the editable order evidence.
    # Idempotent replays may link later runs to the same order. Its origin is
    # the first creation run, never a later replay which must not retrofit a
    # source anchor onto historical evidence or change approval eligibility.
    originating = list(session.scalars(select(AgentRun).where(
        AgentRun.purchase_order_id == order.id).order_by(AgentRun.id).limit(1)))
    anchored = [json.loads(r.state_json).get('user_request') for r in originating
                if json.loads(r.state_json).get('user_request', {}).get('source_run_id') is not None]
    if anchored and not manual_edit and (not isinstance(evidence, dict) or evidence.get('user_request') not in anchored):
        raise ApprovalValidationError('需求证据与原始执行记录不一致，请重新核对需求。')
    # New orders preserve pre-rounding quantities; historical orders remain
    # explicitly unknown and use their persisted quantity for safety checks.
    requested = [DraftItemInput(int(item["material_id"]), Decimal(item["quantity"]))
                 for item in json.loads(order.requested_items_json)] if order.requested_items_json else [
                     DraftItemInput(item.material_id, Decimal(item.quantity)) for item in order.items]
    request = PurchaseDraftInput(order.supplier_id, requested, order.idempotency_key, refs,
                                 total_budget=order.total_budget)
    if isinstance(evidence, dict) and evidence.get('user_request') and not manual_edit:
        from backend.app.services.business_feedback import check_request_conditions
        from backend.app.services.source_conditions import validate_saved_request
        saved = evidence['user_request']
        try:
            saved = validate_saved_request(session, saved, saved['source_prompt'], order.total_budget)
            check_request_conditions(session, 'create_purchase_draft', {
                'supplier_id': order.supplier_id,
                'items': [{'material_id': i.material_id, 'quantity': i.quantity} for i in order.items],
                'evidence_refs': refs}, saved)
        except ValueError as exc:
            raise ApprovalValidationError(str(exc)) from exc
    actual = {item.material_id: item.quantity for item in aggregate_items([
        DraftItemInput(item.material_id, Decimal(item.quantity)) for item in order.items])}
    try:
        for item in aggregate_items(requested):
            relationship = session.scalar(select(SupplierMaterial).where(
                SupplierMaterial.supplier_id == order.supplier_id, SupplierMaterial.material_id == item.material_id))
            if relationship is None:
                raise ValueError("supplier_material_not_found")
            quantity = actual.get(item.material_id, Decimal("0"))
            if quantity > relationship.capacity:
                raise ValueError("capacity_below_quantity")
            _validate_item_evidence(session=session, request=request, item=item, order_quantity=quantity)
            if quantity != _round_order_quantity(requested=item.quantity, moq=Decimal(relationship.moq),
                                                  package_multiple=Decimal(relationship.package_multiple)):
                raise ValueError("order_quantity_mismatch")
        if set(actual) != {item.material_id for item in requested}:
            raise ValueError("order_quantity_mismatch")
    except ValueError as exc:
        raise ApprovalValidationError(str(exc)) from exc

    expected_total = Decimal("0.00")
    for item in order.items:
        relationship = session.scalar(
            select(SupplierMaterial).where(
                SupplierMaterial.supplier_id == order.supplier_id,
                SupplierMaterial.material_id == item.material_id,
            )
        )
        if relationship is None:
            raise ApprovalValidationError("supplier_material_not_found")
        if not relationship.supplier.active:
            raise ApprovalValidationError("supplier_inactive")
        if item.quantity <= 0:
            raise ApprovalValidationError("quantity_must_be_positive")
        if item.quantity < relationship.moq:
            raise ApprovalValidationError("quantity_below_moq")
        if Decimal(relationship.package_multiple) <= 0:
            raise ApprovalValidationError("package_multiple_must_be_positive")
        if item.quantity % Decimal(relationship.package_multiple) != 0:
            raise ApprovalValidationError("quantity_not_package_multiple")
        if item.quantity > relationship.capacity:
            raise ApprovalValidationError("capacity_below_quantity")

        current_price = Decimal(relationship.unit_price).quantize(Decimal("0.01"))
        stored_price = Decimal(item.unit_price).quantize(Decimal("0.01"))
        if current_price != stored_price:
            raise ApprovalValidationError("quote_changed")
        expected_line = (stored_price * item.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if expected_line != Decimal(item.line_amount).quantize(Decimal("0.01")):
            raise ApprovalValidationError("line_amount_mismatch")
        expected_total += expected_line

    expected_total = expected_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if expected_total != Decimal(order.total_amount).quantize(Decimal("0.01")):
        raise ApprovalValidationError("total_amount_mismatch")
    if order.total_budget is not None and expected_total > order.total_budget:
        raise ApprovalValidationError("order_budget_exceeded")


def _locked_order(session: Session, order_id: int) -> PurchaseOrder:
    order = session.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == order_id)
        .options(selectinload(PurchaseOrder.items), selectinload(PurchaseOrder.supplier))
        .with_for_update()
    )
    if order is None:
        raise ApprovalConflict("order_not_found")
    return order


def _order(session: Session, order_id: int) -> PurchaseOrder:
    order = session.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == order_id)
        .options(selectinload(PurchaseOrder.items), selectinload(PurchaseOrder.supplier))
    )
    if order is None:
        raise ApprovalConflict("order_not_found")
    return order


def _add_audit_log(
    session: Session,
    *,
    order_id: int,
    auth: AuthContext,
    action: str,
    details: dict,
) -> None:
    session.add(
        AuditLog(
            order_id=order_id,
            actor_user_id=auth.user_id,
            actor_role=auth.role,
            action=action,
            details_json=json.dumps(details, ensure_ascii=False, sort_keys=True),
        )
    )
