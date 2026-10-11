import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import ApprovalRecord, AuditLog, PurchaseOrder, SupplierMaterial


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
    if not order.items:
        raise ApprovalValidationError("items_required")
    if not order.supplier.active:
        raise ApprovalValidationError("supplier_inactive")

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
