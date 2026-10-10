from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


@dataclass(frozen=True)
class RegressionMetrics:
    sample_count: int
    positive_actual_count: int
    zero_actual_count: int
    mape_coverage_percent: Decimal
    mape_percent: Decimal | None
    mae: Decimal
    wape_percent: Decimal | None


def evaluate_regression(actual: Iterable[Decimal], predicted: Iterable[Decimal]) -> RegressionMetrics:
    actual_values = list(actual)
    predicted_values = list(predicted)
    if len(actual_values) != len(predicted_values):
        raise ValueError("actual and predicted must have same length")
    if not actual_values:
        raise ValueError("at least one sample is required")

    errors = [abs(a - p) for a, p in zip(actual_values, predicted_values, strict=True)]
    positive_pairs = [
        (a, p)
        for a, p in zip(actual_values, predicted_values, strict=True)
        if a > 0
    ]
    mape = None
    if positive_pairs:
        mape = (
            sum(abs(a - p) / abs(a) for a, p in positive_pairs)
            / Decimal(len(positive_pairs))
            * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_actual = sum(abs(value) for value in actual_values)
    wape = None
    if total_actual > 0:
        wape = (sum(errors) / total_actual * Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    mae = (sum(errors) / Decimal(len(errors))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return RegressionMetrics(
        sample_count=len(actual_values),
        positive_actual_count=len(positive_pairs),
        zero_actual_count=len(actual_values) - len(positive_pairs),
        mape_coverage_percent=(Decimal(len(positive_pairs)) / Decimal(len(actual_values)) * Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        ),
        mape_percent=mape,
        mae=mae,
        wape_percent=wape,
    )
