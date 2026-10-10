from decimal import Decimal

import pytest
from sqlalchemy import select

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import PurchaseOrder
from backend.app.services.purchase_drafts import (
    DraftItemInput,
    PurchaseDraftInput,
    create_purchase_draft,
)
from backend.app.services.seed import seed_demo_data


def test_create_purchase_draft_calculates_amount_and_is_idempotent():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        request = PurchaseDraftInput(
            supplier_id=1,
            items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
            idempotency_key="draft-key-001",
            evidence_refs=["recommendation:test"],
        )

        first = create_purchase_draft(session, request)
        second = create_purchase_draft(session, request)

        assert first.id == second.id
        assert first.status == "draft"
        assert first.total_amount == Decimal("972.00")
        assert len(first.items) == 1
        assert first.items[0].unit_price == Decimal("8.10")
        assert first.items[0].line_amount == Decimal("972.00")
        assert session.scalar(select(PurchaseOrder).where(PurchaseOrder.idempotency_key == "draft-key-001")).id == first.id


def test_create_purchase_draft_rejects_supplier_without_material_relationship():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        request = PurchaseDraftInput(
            supplier_id=999,
            items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
            idempotency_key="draft-key-invalid-supplier",
            evidence_refs=["recommendation:test"],
        )

        with pytest.raises(ValueError, match="supplier_material_not_found"):
            create_purchase_draft(session, request)


def test_create_purchase_draft_rejects_capacity_conflict():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        request = PurchaseDraftInput(
            supplier_id=1,
            items=[DraftItemInput(material_id=1, quantity=Decimal("9999"))],
            idempotency_key="draft-key-capacity",
            evidence_refs=["recommendation:test"],
        )

        with pytest.raises(ValueError, match="capacity_below_quantity"):
            create_purchase_draft(session, request)


def test_create_purchase_draft_requires_evidence_refs():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        request = PurchaseDraftInput(
            supplier_id=1,
            items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
            idempotency_key="draft-key-no-evidence",
            evidence_refs=[],
        )

        with pytest.raises(ValueError, match="evidence_required"):
            create_purchase_draft(session, request)
