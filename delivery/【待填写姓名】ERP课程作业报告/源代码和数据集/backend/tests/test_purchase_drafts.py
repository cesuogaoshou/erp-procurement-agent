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
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.recommendations import recommend_for_material
from backend.app.services.seed import seed_demo_data


def _evidence_refs(session, *, material_id: int = 1, supplier_id: int = 1, quantity: Decimal = Decimal("120")) -> list[str]:
    forecast = get_demand_forecast(session, material_id=material_id, horizon_days=30)
    recommendations = recommend_for_material(
        session,
        material_id=material_id,
        quantity=quantity,
        required_in_days=20,
        budget=Decimal("5000.00"),
    )
    assert any(item.supplier_id == supplier_id for item in recommendations.recommendations)
    return [
        forecast["evidence_ref"],
        f"recommendation:{material_id}:{supplier_id}:{quantity}:20:5000.00",
    ]


def test_create_purchase_draft_calculates_amount_and_is_idempotent():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        request = PurchaseDraftInput(
            supplier_id=1,
            items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
            idempotency_key="draft-key-001",
            evidence_refs=_evidence_refs(session),
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


def test_create_purchase_draft_rounds_quantity_to_moq_and_package_multiple():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        from backend.app.models import SupplierMaterial

        relationship = session.scalar(
            select(SupplierMaterial).where(
                SupplierMaterial.supplier_id == 1,
                SupplierMaterial.material_id == 1,
            )
        )
        relationship.moq = Decimal("25")
        relationship.package_multiple = Decimal("10")
        request = PurchaseDraftInput(
            supplier_id=1,
            items=[DraftItemInput(material_id=1, quantity=Decimal("21"))],
            idempotency_key="draft-key-package-rounding",
            evidence_refs=_evidence_refs(session, quantity=Decimal("30")),
        )

        order = create_purchase_draft(session, request)

        assert order.items[0].quantity == Decimal("30")
        assert order.items[0].line_amount == Decimal("243.00")


def test_create_purchase_draft_rejects_supplier_without_material_relationship():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        request = PurchaseDraftInput(
            supplier_id=999,
            items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
            idempotency_key="draft-key-invalid-supplier",
            evidence_refs=_evidence_refs(session),
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
            evidence_refs=_evidence_refs(session),
        )

        with pytest.raises(ValueError, match="quantity_exceeds_forecast_shortage"):
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


def test_create_purchase_draft_rejects_forged_forecast_evidence_ref():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        request = PurchaseDraftInput(
            supplier_id=1,
            items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
            idempotency_key="draft-key-forged-forecast",
            evidence_refs=["forecast:1:30:inventory-v999:wrong:train-end-2026-01-01", "recommendation:1:1:120:20:5000.00"],
        )

        with pytest.raises(ValueError, match="forecast_evidence_invalid"):
            create_purchase_draft(session, request)


def test_create_purchase_draft_rejects_recommendation_for_wrong_supplier():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        forecast = get_demand_forecast(session, material_id=1, horizon_days=30)
        request = PurchaseDraftInput(
            supplier_id=1,
            items=[DraftItemInput(material_id=1, quantity=Decimal("120"))],
            idempotency_key="draft-key-wrong-recommendation",
            evidence_refs=[forecast["evidence_ref"], "recommendation:1:2:120:20:5000.00"],
        )

        with pytest.raises(ValueError, match="recommendation_evidence_invalid"):
            create_purchase_draft(session, request)
