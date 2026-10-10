from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class ForecastRequest(BaseModel):
    material_id: int
    horizon_days: int = Field(ge=1, le=180)


class ForecastOut(BaseModel):
    material_id: int
    horizon_days: int
    model_name: str
    forecast_demand: Decimal
    safety_stock: Decimal
    available_supply: Decimal
    shortage_quantity: Decimal
    notes: list[str]


class RecommendationIn(BaseModel):
    material_id: int
    quantity: Decimal = Field(gt=0)
    required_in_days: int = Field(ge=1, le=365)
    budget: Decimal | None = Field(default=None, gt=0)


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
    recommendations: list[RecommendationItemOut]
    excluded: list[ExcludedSupplierOut]
