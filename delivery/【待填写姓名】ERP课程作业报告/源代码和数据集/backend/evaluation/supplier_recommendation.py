import csv
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import SupplierMaterial, SupplierPerformance
from backend.app.services.recommendations import recommend_for_material


LABEL_SOURCE = "scenario_thresholds_v1"
CHALLENGE_LABEL_SOURCE = "challenge_thresholds_v1"


@dataclass(frozen=True)
class RecommendationCase:
    case_id: str
    material_id: int
    quantity: Decimal
    required_in_days: int
    budget: Decimal | None
    scenario: str
    acceptable_supplier_ids: tuple[int, ...]
    label_source: str = LABEL_SOURCE


def build_independent_cases(session: Session, case_count: int = 60) -> list[RecommendationCase]:
    cases: list[RecommendationCase] = []
    scenarios = ["rush_quality", "budget_standard", "quality_stable"]
    quantities = [Decimal("60"), Decimal("120"), Decimal("180"), Decimal("240")]
    material_ids = list(session.scalars(select(SupplierMaterial.material_id).distinct().order_by(SupplierMaterial.material_id)))

    index = 1
    for material_id in material_ids:
        candidates = list(
            session.scalars(
                select(SupplierMaterial)
                .where(SupplierMaterial.material_id == material_id)
                .order_by(SupplierMaterial.supplier_id)
            )
        )
        for quantity in quantities:
            for scenario in scenarios:
                required_in_days = _required_days(scenario)
                budget = _budget_for_case(candidates, quantity, scenario)
                labels = _acceptable_labels(session, candidates, quantity, required_in_days, budget, scenario)
                if not labels:
                    continue
                cases.append(
                    RecommendationCase(
                        case_id=f"CASE-{index:03d}",
                        material_id=material_id,
                        quantity=quantity,
                        required_in_days=required_in_days,
                        budget=budget,
                        scenario=scenario,
                        acceptable_supplier_ids=tuple(labels),
                    )
                )
                index += 1
                if len(cases) >= case_count:
                    return cases
    return cases


def build_challenge_cases(session: Session, case_count: int = 60) -> list[RecommendationCase]:
    cases: list[RecommendationCase] = []
    scenarios = ["tight_budget", "urgent_resilience", "quality_first"]
    quantities = [Decimal("80"), Decimal("140"), Decimal("200"), Decimal("260")]
    material_ids = list(session.scalars(select(SupplierMaterial.material_id).distinct().order_by(SupplierMaterial.material_id)))

    index = 1
    for material_id in material_ids:
        candidates = list(
            session.scalars(
                select(SupplierMaterial)
                .where(SupplierMaterial.material_id == material_id)
                .order_by(SupplierMaterial.supplier_id)
            )
        )
        for quantity in quantities:
            for scenario in scenarios:
                required_in_days = _challenge_required_days(scenario)
                budget = _challenge_budget_for_case(candidates, quantity, scenario)
                labels = _challenge_labels(session, candidates, quantity, required_in_days, budget, scenario)
                if not labels:
                    continue
                cases.append(
                    RecommendationCase(
                        case_id=f"CHAL-{index:03d}",
                        material_id=material_id,
                        quantity=quantity,
                        required_in_days=required_in_days,
                        budget=budget,
                        scenario=scenario,
                        acceptable_supplier_ids=tuple(labels),
                        label_source=CHALLENGE_LABEL_SOURCE,
                    )
                )
                index += 1
                if len(cases) >= case_count:
                    return cases
    return cases


def evaluate_supplier_recommendations(
    session: Session,
    cases: list[RecommendationCase],
    dataset_name: str = "supplier_recommendation_frozen",
    dataset_version: str = "frozen_v1",
) -> dict:
    price_hits = 0
    composite_hits = 0
    details = []
    label_widths = []
    candidate_counts = []
    for case in cases:
        labels = set(case.acceptable_supplier_ids)
        price_top3 = _price_top3(session, case)
        composite = recommend_for_material(
            session=session,
            material_id=case.material_id,
            quantity=case.quantity,
            required_in_days=case.required_in_days,
            budget=case.budget,
        )
        composite_top3 = [item.supplier_id for item in composite.recommendations[:3]]
        label_widths.append(len(labels))
        candidate_counts.append(len(composite.recommendations) + len(composite.excluded))
        price_hit = bool(labels.intersection(price_top3))
        composite_hit = bool(labels.intersection(composite_top3))
        price_hits += int(price_hit)
        composite_hits += int(composite_hit)
        details.append(
            {
                "case_id": case.case_id,
                "labels": sorted(labels),
                "acceptable_label_count": len(labels),
                "candidate_count": len(composite.recommendations) + len(composite.excluded),
                "price_top3": price_top3,
                "composite_top3": composite_top3,
                "price_hit": price_hit,
                "composite_hit": composite_hit,
                "hit_delta": _hit_delta(price_hit, composite_hit),
                "failure_reason": _failure_reason(labels, price_top3, composite_top3),
            }
        )

    case_count = len(cases)
    return {
        "dataset_name": dataset_name,
        "dataset_version": dataset_version,
        "case_count": case_count,
        "label_source": _label_source(cases),
        "label_definition": {
            "source": _label_source(cases),
            "generation_method": "scenario threshold rules over simulated supplier attributes and performance rows",
            "independence_boundary": "Labels do not call the tested weighted composite score, but they are not human or real-world labels.",
        },
        "parameters": {
            "top_k": 3,
            "case_count": case_count,
        },
        "top3_definition": "hit when at least one acceptable supplier label appears in the first 3 returned suppliers",
        "label_width": _summary(label_widths),
        "candidate_count": _summary(candidate_counts),
        "price_sort_top3_hit_rate_percent": _percent(price_hits, case_count),
        "composite_top3_hit_rate_percent": _percent(composite_hits, case_count),
        "reproduce_command": "python -m backend.evaluation.run_supplier_eval",
        "output_paths": {
            "frozen_cases": "data/raw/recommendation_cases.csv",
            "challenge_cases": "data/raw/recommendation_challenge_cases.csv",
            "result": "reports/generated/supplier_eval.json",
        },
        "details": details,
        "notes": [
            "Labels are generated by scenario threshold rules over simulated supplier outcomes.",
            "Labels do not use the tested weighted composite scoring formula.",
            "Top-3 hit rate is an any-acceptable-label metric, not exact best-supplier ranking.",
        ],
    }


def write_cases_csv(cases: list[RecommendationCase], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "material_id",
                "quantity",
                "required_in_days",
                "budget",
                "scenario",
                "acceptable_supplier_ids",
                "label_source",
            ],
        )
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "case_id": case.case_id,
                    "material_id": case.material_id,
                    "quantity": str(case.quantity),
                    "required_in_days": case.required_in_days,
                    "budget": "" if case.budget is None else str(case.budget),
                    "scenario": case.scenario,
                    "acceptable_supplier_ids": "|".join(str(item) for item in case.acceptable_supplier_ids),
                    "label_source": case.label_source,
                }
            )


def write_result_json(result: dict, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def _price_top3(session: Session, case: RecommendationCase) -> list[int]:
    rows = list(
        session.scalars(
            select(SupplierMaterial)
            .where(SupplierMaterial.material_id == case.material_id)
            .order_by(SupplierMaterial.unit_price, SupplierMaterial.supplier_id)
        )
    )
    eligible = []
    for row in rows:
        if not row.supplier.active:
            continue
        if row.moq > case.quantity or row.capacity < case.quantity:
            continue
        if row.lead_time_days > case.required_in_days:
            continue
        if case.budget is not None and row.unit_price * case.quantity > case.budget:
            continue
        eligible.append(row.supplier_id)
    return eligible[:3]


def _acceptable_labels(
    session: Session,
    candidates: list[SupplierMaterial],
    quantity: Decimal,
    required_in_days: int,
    budget: Decimal | None,
    scenario: str,
) -> list[int]:
    labels = []
    for row in candidates:
        if not row.supplier.active:
            continue
        if row.moq > quantity or row.capacity < quantity:
            continue
        if row.lead_time_days > required_in_days:
            continue
        if budget is not None and row.unit_price * quantity > budget:
            continue
        performance = _performance(session, row.supplier_id, row.material_id)
        if performance is None:
            continue
        on_time = Decimal(performance.on_time_deliveries) / Decimal(performance.promised_deliveries)
        quality = Decimal(performance.accepted_quantity) / Decimal(performance.inspected_quantity)
        complaint = Decimal(performance.complaint_count) / Decimal(performance.promised_deliveries)
        if scenario == "rush_quality" and row.lead_time_days <= required_in_days - 2 and on_time >= Decimal("0.78"):
            labels.append(row.supplier_id)
        elif scenario == "budget_standard" and row.unit_price * quantity <= budget and complaint <= Decimal("0.10"):
            labels.append(row.supplier_id)
        elif scenario == "quality_stable" and quality >= Decimal("0.94") and complaint <= Decimal("0.08"):
            labels.append(row.supplier_id)
    return sorted(labels)


def _challenge_labels(
    session: Session,
    candidates: list[SupplierMaterial],
    quantity: Decimal,
    required_in_days: int,
    budget: Decimal | None,
    scenario: str,
) -> list[int]:
    labels = []
    for row in candidates:
        if not row.supplier.active:
            continue
        if row.moq > quantity or row.capacity < quantity:
            continue
        if row.lead_time_days > required_in_days:
            continue
        if budget is not None and row.unit_price * quantity > budget:
            continue
        performance = _performance(session, row.supplier_id, row.material_id)
        if performance is None:
            continue
        on_time = Decimal(performance.on_time_deliveries) / Decimal(performance.promised_deliveries)
        quality = Decimal(performance.accepted_quantity) / Decimal(performance.inspected_quantity)
        complaint = Decimal(performance.complaint_count) / Decimal(performance.promised_deliveries)
        if scenario == "tight_budget" and complaint <= Decimal("0.08"):
            labels.append(row.supplier_id)
        elif scenario == "urgent_resilience" and row.lead_time_days <= required_in_days - 1 and on_time >= Decimal("0.75"):
            labels.append(row.supplier_id)
        elif scenario == "quality_first" and quality >= Decimal("0.95") and on_time >= Decimal("0.72"):
            labels.append(row.supplier_id)
    return sorted(labels[:5])


def _performance(session: Session, supplier_id: int, material_id: int):
    return session.scalar(
        select(SupplierPerformance)
        .where(
            SupplierPerformance.supplier_id == supplier_id,
            SupplierPerformance.material_id == material_id,
        )
        .limit(1)
    )


def _required_days(scenario: str) -> int:
    if scenario == "rush_quality":
        return 14
    if scenario == "budget_standard":
        return 24
    return 18


def _budget_for_case(candidates: list[SupplierMaterial], quantity: Decimal, scenario: str) -> Decimal | None:
    active_prices = sorted(row.unit_price for row in candidates if row.supplier.active)
    median_price = active_prices[len(active_prices) // 2]
    if scenario == "budget_standard":
        return (median_price * quantity * Decimal("1.05")).quantize(Decimal("0.01"))
    if scenario == "rush_quality":
        return (max(active_prices) * quantity).quantize(Decimal("0.01"))
    return None


def _challenge_required_days(scenario: str) -> int:
    if scenario == "urgent_resilience":
        return 16
    if scenario == "tight_budget":
        return 27
    return 21


def _challenge_budget_for_case(candidates: list[SupplierMaterial], quantity: Decimal, scenario: str) -> Decimal | None:
    active_prices = sorted(row.unit_price for row in candidates if row.supplier.active)
    if scenario == "tight_budget":
        low_price = active_prices[1]
        return (low_price * quantity * Decimal("1.02")).quantize(Decimal("0.01"))
    if scenario == "urgent_resilience":
        high_price = active_prices[-1]
        return (high_price * quantity * Decimal("0.95")).quantize(Decimal("0.01"))
    return None


def _label_source(cases: list[RecommendationCase]) -> str:
    sources = sorted({case.label_source for case in cases})
    return ",".join(sources)


def _summary(values: list[int]) -> dict:
    if not values:
        return {"min": 0, "max": 0, "avg": "0.00"}
    return {
        "min": min(values),
        "max": max(values),
        "avg": str((Decimal(sum(values)) / Decimal(len(values))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
    }


def _hit_delta(price_hit: bool, composite_hit: bool) -> str:
    if price_hit == composite_hit:
        return "same"
    if composite_hit:
        return "composite_only"
    return "price_only"


def _failure_reason(labels: set[int], price_top3: list[int], composite_top3: list[int]) -> str | None:
    price_hit = bool(labels.intersection(price_top3))
    composite_hit = bool(labels.intersection(composite_top3))
    if price_hit and composite_hit:
        return None
    if not price_hit and not composite_hit:
        return "neither_method_hit_acceptable_label"
    if not price_hit:
        return "price_sort_missed_acceptable_label"
    return "composite_missed_acceptable_label"


def _percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.00"
    return str((Decimal(numerator) / Decimal(denominator) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
