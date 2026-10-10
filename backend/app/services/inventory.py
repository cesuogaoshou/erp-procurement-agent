from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.algorithms.shortage import calculate_available_supply
from backend.app.models import Inventory, Material


def list_materials(session: Session) -> list[Material]:
    return list(session.scalars(select(Material).order_by(Material.code)))


def get_inventory_snapshot(session: Session, material_id: int) -> dict:
    inventory = session.scalar(select(Inventory).where(Inventory.material_id == material_id))
    if inventory is None:
        raise LookupError(f"inventory not found for material_id={material_id}")
    available = calculate_available_supply(
        on_hand=Decimal(inventory.on_hand),
        reserved=Decimal(inventory.reserved),
        inbound_confirmed=Decimal("0"),
    )
    return {
        "material_id": inventory.material_id,
        "on_hand": inventory.on_hand,
        "reserved": inventory.reserved,
        "available_supply": available,
        "version": inventory.version,
    }
