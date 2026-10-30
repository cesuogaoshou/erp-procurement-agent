from datetime import date, timedelta
from decimal import Decimal
from random import Random

from sqlalchemy.orm import Session

from backend.app.models import (
    DemandHistory,
    Inventory,
    Material,
    MaterialAlias,
    Supplier,
    SupplierMaterial,
    SupplierPerformance,
)


DEMO_SEED = 20261010
DEMO_BASE_DATE = date(2026, 10, 10)
DEMO_HISTORY_DAYS = 540


def seed_demo_data(session: Session, seed: int = DEMO_SEED) -> None:
    rng = Random(seed)
    materials = [
        Material(code="MAT-001", name="标准轴承", unit="pcs", safety_stock=Decimal("80")),
        Material(code="MAT-002", name="铝合金外壳", unit="pcs", safety_stock=Decimal("45")),
        Material(code="MAT-003", name="工业传感器", unit="pcs", safety_stock=Decimal("30")),
        Material(code="MAT-004", name="伺服电机", unit="pcs", safety_stock=Decimal("25")),
        Material(code="MAT-005", name="控制面板", unit="pcs", safety_stock=Decimal("35")),
        Material(code="MAT-006", name="密封圈", unit="pcs", safety_stock=Decimal("120")),
        Material(code="MAT-007", name="电源模块", unit="pcs", safety_stock=Decimal("40")),
        Material(code="MAT-008", name="导轨组件", unit="pcs", safety_stock=Decimal("55")),
        Material(code="MAT-009", name="包装托盘", unit="pcs", safety_stock=Decimal("150")),
        Material(code="MAT-010", name="紧固件套包", unit="set", safety_stock=Decimal("200")),
    ]
    session.add_all(materials)
    session.flush()

    aliases_by_code = {
        "MAT-001": ("轴承", "标准件", "轴承件", "bearings"),
        "MAT-002": ("铝壳", "外壳", "铝合金件", "aluminum shell"),
        "MAT-003": ("传感器", "感应器", "sensor"),
        "MAT-004": ("伺服", "电机", "马达", "servo motor"),
        "MAT-005": ("面板", "控制屏", "control panel"),
        "MAT-006": ("密封圈", "O型圈", "胶圈", "seal ring"),
        "MAT-007": ("电源", "模块电源", "power module"),
        "MAT-008": ("导轨", "滑轨", "guide rail"),
        "MAT-009": ("托盘", "包装盘", "pallet"),
        "MAT-010": ("紧固件", "螺丝包", "五金包", "fastener kit"),
    }
    materials_by_code = {material.code: material for material in materials}
    for code, aliases in aliases_by_code.items():
        material = materials_by_code[code]
        for alias in aliases:
            session.add(MaterialAlias(material_id=material.id, alias=alias, locale="zh-CN", source="seed"))

    for material in materials:
        session.add(
            Inventory(
                material_id=material.id,
                on_hand=Decimal(rng.randint(90, 180)),
                reserved=Decimal(rng.randint(10, 35)),
            )
        )

    suppliers = [
        Supplier(name="华东精工", active=True),
        Supplier(name="北辰制造", active=True),
        Supplier(name="南方供应链", active=True),
        Supplier(name="远航物资", active=True),
        Supplier(name="西部智造", active=True),
        Supplier(name="恒信工业", active=True),
        Supplier(name="启明电子", active=True),
        Supplier(name="海川零件", active=True),
        Supplier(name="云岭材料", active=True),
        Supplier(name="停用供应商", active=False),
    ]
    session.add_all(suppliers)
    session.flush()

    base_date = DEMO_BASE_DATE
    for material in materials:
        for offset in range(DEMO_HISTORY_DAYS):
            weekly = 4 if offset % 7 in (1, 2, 3) else 0
            trend = offset // 120
            annual = 3 if (offset % 365) in range(70, 130) else 0
            intermittent = 0 if material.id not in (6, 9, 10) or offset % 9 != 0 else rng.randint(8, 16)
            noise = rng.randint(0, 4)
            quantity = Decimal(6 + material.id + weekly + trend + annual + intermittent + noise)
            session.add(
                DemandHistory(
                    material_id=material.id,
                    demand_date=base_date - timedelta(days=DEMO_HISTORY_DAYS - offset),
                    quantity=quantity,
                )
            )

    for material in materials:
        for index, supplier in enumerate(suppliers):
            session.add(
                SupplierMaterial(
                    supplier_id=supplier.id,
                    material_id=material.id,
                    unit_price=Decimal("8.00") + Decimal(index) * Decimal("0.80") + Decimal(material.id) / 10,
                    lead_time_days=7 + index * 3,
                    moq=Decimal("20"),
                    package_multiple=Decimal("10") if material.id in (9, 10) else Decimal("1"),
                    capacity=Decimal("300") - Decimal(index * 20),
                )
            )
            promised = 30
            on_time = 21 + rng.randint(0, 8) - index
            inspected = Decimal("1000")
            accepted = inspected - Decimal(rng.randint(10, 80) + index * 8)
            complaints = max(0, index + rng.randint(0, 2) - 1)
            session.add(
                SupplierPerformance(
                    supplier_id=supplier.id,
                    material_id=material.id,
                    observed_until=base_date,
                    avg_price=Decimal("8.00") + Decimal(index) * Decimal("0.75"),
                    promised_deliveries=promised,
                    on_time_deliveries=max(1, on_time),
                    inspected_quantity=inspected,
                    accepted_quantity=accepted,
                    complaint_count=complaints,
                )
            )
    session.flush()
