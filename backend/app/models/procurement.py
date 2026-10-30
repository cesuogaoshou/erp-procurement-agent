from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
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


class MaterialAlias(Base):
    __tablename__ = "material_aliases"
    __table_args__ = (UniqueConstraint("material_id", "alias", name="uq_material_alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    alias: Mapped[str] = mapped_column(String(120), index=True)
    locale: Mapped[str] = mapped_column(String(20), default="zh-CN")
    source: Mapped[str] = mapped_column(String(32), default="seed")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    material: Mapped[Material] = relationship()


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
    package_multiple: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("1"))
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
    total_budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_items_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs_json: Mapped[str] = mapped_column(Text)
    formal_order_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

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


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    actor_user_id: Mapped[str] = mapped_column(String(80), index=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    order_version_before: Mapped[int] = mapped_column(Integer)
    order_version_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    order: Mapped[PurchaseOrder] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    actor_user_id: Mapped[str] = mapped_column(String(80), index=True)
    actor_role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64), index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    order: Mapped[PurchaseOrder] = relationship()


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    total_budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    state_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    purchase_order: Mapped[PurchaseOrder | None] = relationship()


class ToolTrace(Base):
    __tablename__ = "tool_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(80), index=True)
    arguments_json: Mapped[str] = mapped_column(Text)
    output_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    run: Mapped[AgentRun] = relationship()
