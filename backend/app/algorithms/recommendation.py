from dataclasses import dataclass, field
from decimal import Decimal


DEFAULT_WEIGHTS = {
    "price": Decimal("0.35"),
    "delivery": Decimal("0.30"),
    "quality": Decimal("0.25"),
    "complaint": Decimal("0.10"),
}


@dataclass(frozen=True)
class RecommendationRequest:
    material_id: int
    quantity: Decimal
    required_in_days: int
    budget: Decimal | None = None


@dataclass(frozen=True)
class SupplierCandidate:
    supplier_id: int
    supplier_name: str
    active: bool
    material_id: int
    unit_price: Decimal
    lead_time_days: int
    capacity: Decimal
    moq: Decimal
    on_time_rate: Decimal
    quality_rate: Decimal
    complaint_rate: Decimal


@dataclass(frozen=True)
class ExcludedSupplier:
    supplier_id: int
    supplier_name: str
    reasons: list[str]


@dataclass(frozen=True)
class SupplierRecommendation:
    supplier_id: int
    supplier_name: str
    unit_price: Decimal
    total_amount: Decimal
    score: Decimal
    evidence: dict


@dataclass(frozen=True)
class RecommendationResult:
    recommendations: list[SupplierRecommendation] = field(default_factory=list)
    excluded: list[ExcludedSupplier] = field(default_factory=list)


def recommend_suppliers(
    request: RecommendationRequest,
    candidates: list[SupplierCandidate],
    weights: dict[str, Decimal] | None = None,
    top_n: int = 3,
) -> RecommendationResult:
    active_weights = weights or DEFAULT_WEIGHTS
    eligible: list[SupplierCandidate] = []
    excluded: list[ExcludedSupplier] = []

    for candidate in candidates:
        reasons = _exclusion_reasons(request, candidate)
        if reasons:
            excluded.append(
                ExcludedSupplier(
                    supplier_id=candidate.supplier_id,
                    supplier_name=candidate.supplier_name,
                    reasons=reasons,
                )
            )
        else:
            eligible.append(candidate)

    normalized = _normalize_candidates(eligible)
    recommendations = [
        _score_candidate(candidate, request.quantity, normalized[candidate.supplier_id], active_weights)
        for candidate in eligible
    ]
    recommendations.sort(key=lambda item: (-item.score, item.unit_price, item.supplier_id))
    return RecommendationResult(recommendations=recommendations[:top_n], excluded=excluded)


def _exclusion_reasons(request: RecommendationRequest, candidate: SupplierCandidate) -> list[str]:
    reasons: list[str] = []
    if not candidate.active:
        reasons.append("supplier_inactive")
    if candidate.material_id != request.material_id:
        reasons.append("material_not_supplied")
    if request.quantity < candidate.moq:
        reasons.append("quantity_below_moq")
    if candidate.lead_time_days > request.required_in_days:
        reasons.append("lead_time_exceeds_required")
    if candidate.capacity < request.quantity:
        reasons.append("capacity_below_quantity")
    if request.budget is not None and candidate.unit_price * request.quantity > request.budget:
        reasons.append("budget_exceeded")
    return reasons


def _normalize_candidates(candidates: list[SupplierCandidate]) -> dict[int, dict[str, Decimal]]:
    if not candidates:
        return {}

    prices = [candidate.unit_price for candidate in candidates]
    deliveries = [candidate.on_time_rate for candidate in candidates]
    qualities = [candidate.quality_rate for candidate in candidates]
    complaints = [candidate.complaint_rate for candidate in candidates]

    return {
        candidate.supplier_id: {
            "price": _cost_score(candidate.unit_price, prices),
            "delivery": _benefit_score(candidate.on_time_rate, deliveries),
            "quality": _benefit_score(candidate.quality_rate, qualities),
            "complaint": _cost_score(candidate.complaint_rate, complaints),
        }
        for candidate in candidates
    }


def _benefit_score(value: Decimal, values: list[Decimal]) -> Decimal:
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return Decimal("1")
    return (value - minimum) / (maximum - minimum)


def _cost_score(value: Decimal, values: list[Decimal]) -> Decimal:
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return Decimal("1")
    return (maximum - value) / (maximum - minimum)


def _score_candidate(
    candidate: SupplierCandidate,
    quantity: Decimal,
    normalized: dict[str, Decimal],
    weights: dict[str, Decimal],
) -> SupplierRecommendation:
    score = sum(normalized[name] * weights[name] for name in DEFAULT_WEIGHTS)
    return SupplierRecommendation(
        supplier_id=candidate.supplier_id,
        supplier_name=candidate.supplier_name,
        unit_price=candidate.unit_price,
        total_amount=candidate.unit_price * quantity,
        score=score.quantize(Decimal("0.0001")),
        evidence={
            "weights": weights,
            "score_components": {
                "price": {"raw": candidate.unit_price, "normalized": normalized["price"]},
                "delivery": {"raw": candidate.on_time_rate, "normalized": normalized["delivery"]},
                "quality": {"raw": candidate.quality_rate, "normalized": normalized["quality"]},
                "complaint": {"raw": candidate.complaint_rate, "normalized": normalized["complaint"]},
            },
        },
    )
