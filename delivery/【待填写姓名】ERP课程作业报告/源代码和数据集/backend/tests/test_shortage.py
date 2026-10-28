from decimal import Decimal

from backend.app.algorithms.shortage import calculate_available_supply, calculate_shortage


def test_shortage_uses_forecast_demand_safety_stock_and_available_supply():
    available = calculate_available_supply(
        on_hand=Decimal("120"),
        reserved=Decimal("15"),
        inbound_confirmed=Decimal("0"),
    )

    shortage = calculate_shortage(
        forecast_demand=Decimal("140"),
        safety_stock=Decimal("30"),
        available_supply=available,
    )

    assert available == Decimal("105")
    assert shortage == Decimal("65")


def test_shortage_never_goes_below_zero():
    shortage = calculate_shortage(
        forecast_demand=Decimal("20"),
        safety_stock=Decimal("10"),
        available_supply=Decimal("100"),
    )

    assert shortage == Decimal("0")


def test_available_supply_rejects_negative_quantities():
    try:
        calculate_available_supply(
            on_hand=Decimal("10"),
            reserved=Decimal("-1"),
            inbound_confirmed=Decimal("0"),
        )
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("negative reserved quantity should fail")
