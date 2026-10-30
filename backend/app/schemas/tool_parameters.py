"""One local runtime model per tool; published schemas come from these models."""
from pydantic import Field
from decimal import Decimal

from backend.app.schemas.procurement import (
    ParameterModel, PositiveId, ForecastRequest, RecommendationIn, PurchaseDraftParameters,
)


class EmptyParameters(ParameterModel):
    pass


class ResolveMaterialParameters(ParameterModel):
    query: str = Field(min_length=1, max_length=120, pattern=r"\S")


class SearchMaterialsParameters(ParameterModel):
    query: str = Field(min_length=1, max_length=120, pattern=r"\S")
    limit: int = Field(default=5, ge=1, le=10)


class InventoryParameters(ParameterModel):
    material_id: PositiveId


class RequestItem(ParameterModel):
    query: str = Field(min_length=1, max_length=120)
    quantity: Decimal | None = Field(default=None, allow_inf_nan=False)


class CaptureRequestParameters(ParameterModel):
    items: list[RequestItem] = Field(default_factory=list, max_length=20)
    purchase_requested: bool = Field(strict=True)
    stated_budget: Decimal | None = Field(default=None, allow_inf_nan=False)
    required_in_days: int | None = Field(default=None, strict=True, ge=1, le=365)


TOOL_PARAMETER_MODELS = {
    "capture_request": CaptureRequestParameters,
    "list_materials": EmptyParameters,
    "search_materials": SearchMaterialsParameters,
    "resolve_material": ResolveMaterialParameters,
    "get_inventory": InventoryParameters,
    "get_demand_forecast": ForecastRequest,
    "recommend_suppliers": RecommendationIn,
    # Budget is injected from the confirmed run, never accepted from the model.
    "create_purchase_draft": PurchaseDraftParameters,
}
