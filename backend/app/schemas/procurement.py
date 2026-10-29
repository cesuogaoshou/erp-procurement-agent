from decimal import Decimal
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field


PositiveId = Annotated[int, Field(strict=True, gt=0)]
Quantity = Annotated[Decimal, Field(gt=0, allow_inf_nan=False, max_digits=12, decimal_places=2)]
Money = Annotated[Decimal, Field(gt=0, allow_inf_nan=False, max_digits=14, decimal_places=2)]
EvidenceRef = Annotated[str, Field(min_length=1, max_length=500)]


class ParameterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    unit: str
    safety_stock: Decimal


class InventoryOut(BaseModel):
    material_id: int
    on_hand: Decimal
    reserved: Decimal
    available_supply: Decimal
    version: int


class ForecastRequest(ParameterModel):
    material_id: PositiveId
    horizon_days: int = Field(strict=True, ge=1, le=180)


class ForecastOut(BaseModel):
    material_id: int
    horizon_days: int
    model_name: str
    strategy_type: str
    selected_model_name: str
    config_version: str
    fallback_model_name: str
    fallback_reason: str | None = None
    training_range: dict[str, Any]
    forecast_range: dict[str, Any]
    config: dict[str, Any]
    evidence_ref: str
    forecast_evidence: dict[str, Any]
    forecast_demand: Decimal
    safety_stock: Decimal
    available_supply: Decimal
    shortage_quantity: Decimal
    notes: list[str]


class RecommendationIn(ParameterModel):
    material_id: PositiveId
    quantity: Quantity
    required_in_days: int = Field(strict=True, ge=1, le=365)
    budget: Money | None = None


class RecommendationItemOut(BaseModel):
    supplier_id: int
    supplier_name: str
    unit_price: Decimal
    total_amount: Decimal
    score: Decimal
    evidence: dict[str, Any]


class ExcludedSupplierOut(BaseModel):
    supplier_id: int
    supplier_name: str
    reasons: list[str]


class RecommendationOut(BaseModel):
    evidence_ref: str | None = None
    recommendations: list[RecommendationItemOut]
    excluded: list[ExcludedSupplierOut]


class PurchaseDraftItemIn(ParameterModel):
    material_id: PositiveId
    quantity: Quantity


class PurchaseDraftParameters(ParameterModel):
    supplier_id: PositiveId
    items: list[PurchaseDraftItemIn] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=120)
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=200)


class PurchaseDraftIn(PurchaseDraftParameters):
    total_budget: Money


class PurchaseDraftItemOut(BaseModel):
    material_id: int
    material_name: str = ""
    unit: str = ""
    quantity: Decimal
    unit_price: Decimal
    line_amount: Decimal


class PurchaseDraftOut(BaseModel):
    id: int
    supplier_id: int
    status: str
    total_amount: Decimal
    total_budget: Decimal | None = None
    idempotency_key: str
    version: int
    formal_order_number: str | None = None
    items: list[PurchaseDraftItemOut]


class ApprovalActionIn(BaseModel):
    expected_order_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=120)
    reason: str | None = Field(default=None, max_length=500)
    actor_user_id: str | None = Field(default=None, max_length=80)
    actor_role: str | None = Field(default=None, max_length=32)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=120)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    role: str


class AgentRunIn(ParameterModel):
    prompt: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, max_length=120)
    use_langgraph: bool = True
    total_budget: Money | None = None


class RequestConfirmationIn(ParameterModel):
    prompt: str = Field(min_length=1, max_length=2000)
    total_budget: Money
    confirmation_fingerprint: str = Field(min_length=64, max_length=64)


class AgentRunOut(BaseModel):
    confirmation_fingerprint: str | None = None
    run_id: int | None
    status: str
    tool_calls: list[str]
    purchase_order_id: int | None = None
    total_amount: Decimal | None = None
    error: str | None = None
    real_function_calling: bool = False
    langgraph_executed: bool = False
    business_message: str = ""
    next_action: str = ""
    model_response: str = ""


class AgentRunSummaryOut(BaseModel):
    confirmation_fingerprint: str | None = None
    id: int
    status: str
    prompt: str
    total_budget: Decimal | None = None
    error: str | None = None
    purchase_order_id: int | None = None
    created_at: str
    updated_at: str
    business_message: str = ""
    next_action: str = ""
    model_response: str = ""


class ToolTraceOut(BaseModel):
    id: int
    run_id: int
    step_index: int
    tool_name: str
    arguments: dict[str, Any]
    output: dict[str, Any] | list[Any]
    status: str
    error: str | None = None
    created_at: str


class PurchaseOrderSummaryOut(BaseModel):
    id: int
    supplier_id: int
    supplier_name: str
    status: str
    total_amount: Decimal
    total_budget: Decimal | None = None
    idempotency_key: str
    version: int
    formal_order_number: str | None = None
    evidence_refs: dict[str, Any] | list[Any]
    items: list[PurchaseDraftItemOut]
    created_at: str
    updated_at: str
    delivery_requirement: str = "交付要求无法确认"
    recommendation_basis: str = "推荐依据无法确认"


class DemandHistoryPointOut(BaseModel):
    date: str
    quantity: Decimal
