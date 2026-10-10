from decimal import Decimal

from backend.app.algorithms.recommendation import (
    RecommendationRequest,
    SupplierCandidate,
    recommend_suppliers,
)


def _candidate(
    supplier_id,
    name,
    price,
    lead_time_days,
    capacity,
    moq,
    on_time_rate,
    quality_rate,
    complaint_rate,
    active=True,
):
    return SupplierCandidate(
        supplier_id=supplier_id,
        supplier_name=name,
        active=active,
        material_id=1,
        unit_price=Decimal(price),
        lead_time_days=lead_time_days,
        capacity=Decimal(capacity),
        moq=Decimal(moq),
        on_time_rate=Decimal(on_time_rate),
        quality_rate=Decimal(quality_rate),
        complaint_rate=Decimal(complaint_rate),
    )


def test_recommendation_filters_constraints_and_scores_four_metrics():
    candidates = [
        _candidate(1, "Cheap Slow", "8.00", 30, "500", "10", "0.70", "0.92", "0.06"),
        _candidate(2, "Balanced", "9.20", 12, "500", "10", "0.96", "0.98", "0.01"),
        _candidate(3, "Premium", "10.00", 8, "500", "10", "0.98", "0.99", "0.00"),
        _candidate(4, "Too Small", "7.50", 7, "50", "10", "0.99", "0.99", "0.00"),
        _candidate(5, "Inactive", "7.20", 7, "500", "10", "0.99", "0.99", "0.00", active=False),
    ]

    result = recommend_suppliers(
        RecommendationRequest(
            material_id=1,
            quantity=Decimal("120"),
            required_in_days=14,
            budget=Decimal("1300.00"),
        ),
        candidates,
    )

    assert [item.supplier_name for item in result.recommendations] == ["Premium", "Balanced"]
    assert result.recommendations[0].evidence["score_components"]["quality"]["raw"] == Decimal("0.99")
    assert {item.supplier_name: item.reasons for item in result.excluded} == {
        "Cheap Slow": ["lead_time_exceeds_required"],
        "Too Small": ["capacity_below_quantity"],
        "Inactive": ["supplier_inactive"],
    }


def test_recommendation_returns_budget_exclusion_without_relaxing_constraints():
    candidates = [
        _candidate(1, "Good But Expensive", "20.00", 5, "500", "10", "0.99", "0.99", "0.00"),
    ]

    result = recommend_suppliers(
        RecommendationRequest(
            material_id=1,
            quantity=Decimal("100"),
            required_in_days=10,
            budget=Decimal("1500.00"),
        ),
        candidates,
    )

    assert result.recommendations == []
    assert result.excluded[0].supplier_name == "Good But Expensive"
    assert result.excluded[0].reasons == ["budget_exceeded"]
