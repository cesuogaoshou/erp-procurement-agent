from decimal import Decimal


def _ensure_non_negative(name: str, value: Decimal) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def calculate_available_supply(
    on_hand: Decimal,
    reserved: Decimal,
    inbound_confirmed: Decimal = Decimal("0"),
) -> Decimal:
    _ensure_non_negative("on_hand", on_hand)
    _ensure_non_negative("reserved", reserved)
    _ensure_non_negative("inbound_confirmed", inbound_confirmed)
    return on_hand - reserved + inbound_confirmed


def calculate_shortage(
    forecast_demand: Decimal,
    safety_stock: Decimal,
    available_supply: Decimal,
) -> Decimal:
    _ensure_non_negative("forecast_demand", forecast_demand)
    _ensure_non_negative("safety_stock", safety_stock)
    _ensure_non_negative("available_supply", available_supply)
    shortage = forecast_demand + safety_stock - available_supply
    return max(Decimal("0"), shortage)
