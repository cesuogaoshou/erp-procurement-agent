from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(20))
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    inventory: Mapped["Inventory"] = relationship(back_populates="material", uselist=False)


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), unique=True)
    on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reserved: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    material: Mapped[Material] = relationship(back_populates="inventory")


class DemandHistory(Base):
    __tablename__ = "demand_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    demand_date: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SupplierMaterial(Base):
    __tablename__ = "supplier_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    lead_time_days: Mapped[int] = mapped_column(Integer)
    moq: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    capacity: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    supplier: Mapped[Supplier] = relationship()
    material: Mapped[Material] = relationship()


class SupplierPerformance(Base):
    __tablename__ = "supplier_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    observed_until: Mapped[date] = mapped_column(Date)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    promised_deliveries: Mapped[int] = mapped_column(Integer)
    on_time_deliveries: Mapped[int] = mapped_column(Integer)
    inspected_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    accepted_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    complaint_count: Mapped[int] = mapped_column(Integer)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    evidence_refs_json: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    supplier: Mapped[Supplier] = relationship()
    items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    material: Mapped[Material] = relationship()
