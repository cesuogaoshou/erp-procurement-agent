from decimal import Decimal

import pytest
from sqlalchemy import select

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import ApprovalRecord, AuditLog, PurchaseOrder, SupplierMaterial
from backend.app.services.approvals import (
    AuthContext,
    ApprovalActionInput,
    ApprovalConflict,
    ApprovalPermissionError,
    ApprovalValidationError,
    approve_order,
    reject_order,
    submit_for_approval,
)
from backend.app.services.purchase_drafts import DraftItemInput, PurchaseDraftInput, create_purchase_draft
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.recommendations import recommend_for_material
from backend.app.services.seed import seed_demo_data


def _draft(session, key: str = "approval-draft-001") -> PurchaseOrder:
    forecast = get_demand_forecast(session, material_id=1, horizon_days=30)
    recommendations = recommend_for_material(
        session,
        material_id=1,
        quantity=Decimal("120"),
        required_in_days=20,
        budget=Decimal("5000.00"),
    )
    assert any(item.supplier_id == 1 for item in recommendations.recommendations)
    return create_purchase_draft(
        session,
        PurchaseDraftInput(
            supplier_id=1,
            items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
            idempotency_key=key,
            evidence_refs=[forecast["evidence_ref"], "recommendation:1:1:120:20:5000.00"],
        ),
    )


def test_buyer_submits_and_approver_approves_with_audit_and_formal_order_number():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        order = _draft(session)

        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))
        pending_status = pending.status
        pending_version = pending.version
        approved = approve_order(
            session,
            order.id,
            AuthContext(user_id="approver-1", role="approver"),
            ApprovalActionInput(expected_order_version=pending_version, idempotency_key="approve-key-001"),
        )

        records = list(session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == order.id)))
        audits = list(session.scalars(select(AuditLog).where(AuditLog.order_id == order.id)))

        assert pending_status == "pending_approval"
        assert approved.status == "approved"
        assert approved.formal_order_number == f"PO-{order.id:06d}"
        assert approved.version == 3
        assert [record.decision for record in records] == ["approved"]
        assert records[0].actor_user_id == "approver-1"
        assert [audit.action for audit in audits] == ["submitted_for_approval", "approved"]


def test_approver_rejects_pending_order_and_records_reason():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        order = _draft(session, "approval-draft-reject")
        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))

        rejected = reject_order(
            session,
            order.id,
            AuthContext(user_id="approver-1", role="approver"),
            ApprovalActionInput(
                expected_order_version=pending.version,
                idempotency_key="reject-key-001",
                reason="price too high",
            ),
        )

        record = session.scalar(select(ApprovalRecord).where(ApprovalRecord.order_id == order.id))
        assert rejected.status == "rejected"
        assert record.decision == "rejected"
        assert record.reason == "price too high"


def test_buyer_cannot_approve_even_if_body_claims_approver_role():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        order = _draft(session, "approval-draft-unauthorized")
        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))

        with pytest.raises(ApprovalPermissionError, match="approver_role_required"):
            approve_order(
                session,
                order.id,
                AuthContext(user_id="buyer-1", role="buyer"),
                ApprovalActionInput(
                    expected_order_version=pending.version,
                    idempotency_key="approve-key-unauthorized",
                    body_actor_user_id="approver-from-body",
                    body_actor_role="approver",
                ),
            )


def test_duplicate_approval_idempotency_returns_existing_record_without_new_audit():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        order = _draft(session, "approval-draft-duplicate")
        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))
        request = ApprovalActionInput(expected_order_version=pending.version, idempotency_key="approve-key-duplicate")

        first = approve_order(session, order.id, AuthContext(user_id="approver-1", role="approver"), request)
        second = approve_order(session, order.id, AuthContext(user_id="approver-1", role="approver"), request)

        records = list(session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == order.id)))
        audits = list(session.scalars(select(AuditLog).where(AuditLog.order_id == order.id)))
        assert first.id == second.id
        assert len(records) == 1
        assert [audit.action for audit in audits] == ["submitted_for_approval", "approved"]


def test_stale_version_blocks_concurrent_approval_attempt():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        order = _draft(session, "approval-draft-stale")
        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))
        approve_order(
            session,
            order.id,
            AuthContext(user_id="approver-1", role="approver"),
            ApprovalActionInput(expected_order_version=pending.version, idempotency_key="approve-key-stale-first"),
        )

        with pytest.raises(ApprovalConflict, match="order_not_pending_approval"):
            approve_order(
                session,
                order.id,
                AuthContext(user_id="approver-2", role="approver"),
                ApprovalActionInput(expected_order_version=pending.version, idempotency_key="approve-key-stale-second"),
            )


def test_supplier_quote_change_before_approval_is_rejected():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        order = _draft(session, "approval-draft-price-change")
        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))
        quote = session.scalar(
            select(SupplierMaterial).where(
                SupplierMaterial.supplier_id == order.supplier_id,
                SupplierMaterial.material_id == order.items[0].material_id,
            )
        )
        quote.unit_price = Decimal("9.99")

        with pytest.raises(ApprovalValidationError, match="quote_changed"):
            approve_order(
                session,
                order.id,
                AuthContext(user_id="approver-1", role="approver"),
                ApprovalActionInput(expected_order_version=pending.version, idempotency_key="approve-key-price-change"),
            )


def test_approval_rolls_back_order_record_and_audit_when_audit_insert_fails(monkeypatch):
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        order = _draft(session, "approval-draft-rollback")
        pending = submit_for_approval(session, order.id, AuthContext(user_id="buyer-1", role="buyer"))

    import backend.app.services.approvals as approvals

    original_audit = approvals._add_audit_log

    def fail_approval_audit(*args, **kwargs):
        if kwargs.get("action") == "approved":
            raise RuntimeError("forced_audit_failure")
        return original_audit(*args, **kwargs)

    monkeypatch.setattr(approvals, "_add_audit_log", fail_approval_audit)

    with pytest.raises(RuntimeError, match="forced_audit_failure"):
        with session_scope(engine) as session:
            approve_order(
                session,
                order.id,
                AuthContext(user_id="approver-1", role="approver"),
                ApprovalActionInput(expected_order_version=pending.version, idempotency_key="approve-key-rollback"),
            )

    with session_scope(engine) as session:
        stored = session.get(PurchaseOrder, order.id)
        records = list(session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == order.id)))
        audits = list(session.scalars(select(AuditLog).where(AuditLog.order_id == order.id)))
        assert stored.status == "pending_approval"
        assert stored.version == pending.version
        assert records == []
        assert [audit.action for audit in audits] == ["submitted_for_approval"]
