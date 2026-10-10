from decimal import Decimal

from backend.evaluation.metrics import evaluate_regression


def test_regression_metrics_report_mape_only_on_positive_actuals():
    metrics = evaluate_regression(
        actual=[Decimal("0"), Decimal("10"), Decimal("20")],
        predicted=[Decimal("5"), Decimal("12"), Decimal("18")],
    )

    assert metrics.sample_count == 3
    assert metrics.positive_actual_count == 2
    assert metrics.zero_actual_count == 1
    assert metrics.mape_percent == Decimal("15.00")
    assert metrics.mae == Decimal("3.00")
    assert metrics.wape_percent == Decimal("30.00")
