from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models import Material
from backend.app.services.inventory import get_inventory_snapshot, list_materials
from backend.app.services.purchase_drafts import DraftItemInput, PurchaseDraftInput, create_purchase_draft
from backend.app.services.recommendations import recommend_for_material
from backend.app.services.forecasting import get_demand_forecast


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    write_mode: str = "read_only"


def build_agent_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="list_materials",
            description="List available procurement materials.",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        AgentTool(
            name="resolve_material",
            description="Resolve a material code or name fragment. Returns ambiguous when multiple materials match.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
        AgentTool(
            name="get_inventory",
            description="Read inventory for one material.",
            parameters={
                "type": "object",
                "properties": {"material_id": {"type": "integer"}},
                "required": ["material_id"],
            },
        ),
        AgentTool(
            name="get_demand_forecast",
            description="Forecast demand and shortage for one material over a horizon. Returns a server evidence reference.",
            parameters={
                "type": "object",
                "properties": {
                    "material_id": {"type": "integer"},
                    "horizon_days": {"type": "integer"},
                },
                "required": ["material_id", "horizon_days"],
            },
        ),
        AgentTool(
            name="recommend_suppliers",
            description="Read supplier recommendations for a material and quantity.",
            parameters={
                "type": "object",
                "properties": {
                    "material_id": {"type": "integer"},
                    "quantity": {"type": "string"},
                    "required_in_days": {"type": "integer"},
                    "budget": {"type": "string"},
                },
                "required": ["material_id", "quantity", "required_in_days"],
            },
        ),
        AgentTool(
            name="create_purchase_draft",
            description="Create a backend-validated purchase draft. This does not approve or issue an order.",
            parameters={
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "integer"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "material_id": {"type": "integer"},
                                "quantity": {"type": "string"},
                            },
                            "required": ["material_id", "quantity"],
                        },
                    },
                    "idempotency_key": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["supplier_id", "items", "idempotency_key", "evidence_refs"],
            },
            write_mode="create_draft",
        ),
    ]


def execute_agent_tool(
    session: Session,
    name: str,
    arguments: dict[str, Any],
    evidence_registry: dict[str, dict[str, Any]] | None = None,
) -> Any:
    if name == "list_materials":
        return [item.__dict__ for item in list_materials(session)]
    if name == "resolve_material":
        query = str(arguments["query"]).lower()
        matches = [
            {"id": material.id, "code": material.code, "name": material.name}
            for material in session.query(Material).order_by(Material.id)
            if query in material.code.lower() or query in material.name.lower()
        ]
        if not matches:
            return {"status": "material_not_found", "matches": []}
        if len(matches) > 1:
            return {"status": "material_ambiguous", "matches": matches[:10]}
        return {"status": "resolved", "material": matches[0]}
    if name == "get_inventory":
        snapshot = get_inventory_snapshot(session, int(arguments["material_id"]))
        return snapshot.__dict__
    if name == "get_demand_forecast":
        forecast = get_demand_forecast(
            session,
            material_id=int(arguments["material_id"]),
            horizon_days=int(arguments["horizon_days"]),
        )
        if evidence_registry is not None:
            evidence_registry[forecast["evidence_ref"]] = forecast
        return forecast
    if name == "recommend_suppliers":
        result = recommend_for_material(
            session=session,
            material_id=int(arguments["material_id"]),
            quantity=Decimal(str(arguments["quantity"])),
            required_in_days=int(arguments["required_in_days"]),
            budget=None if arguments.get("budget") is None else Decimal(str(arguments["budget"])),
        )
        return {
            "recommendations": result.recommendations,
            "excluded": result.excluded,
        }
    if name == "create_purchase_draft":
        _validate_forecast_evidence(arguments, evidence_registry or {})
        order = create_purchase_draft(
            session,
            PurchaseDraftInput(
                supplier_id=int(arguments["supplier_id"]),
                items=[
                    DraftItemInput(material_id=int(item["material_id"]), quantity=Decimal(str(item["quantity"])))
                    for item in arguments["items"]
                ],
                idempotency_key=str(arguments["idempotency_key"]),
                evidence_refs=[str(item) for item in arguments["evidence_refs"]],
            ),
        )
        return order
    raise ValueError(f"tool_not_allowed:{name}")


def _validate_forecast_evidence(arguments: dict[str, Any], evidence_registry: dict[str, dict[str, Any]]) -> None:
    refs = [str(item) for item in arguments.get("evidence_refs", [])]
    if "use_latest_forecast" in refs and evidence_registry:
        refs = [next(reversed(evidence_registry))]
    forecasts = [evidence_registry[ref] for ref in refs if ref in evidence_registry and ref.startswith("forecast:")]
    if not forecasts:
        raise ValueError("forecast_evidence_required")
    by_material = {int(item["material_id"]): item for item in forecasts}
    for item in arguments["items"]:
        material_id = int(item["material_id"])
        forecast = by_material.get(material_id)
        if forecast is None:
            raise ValueError("forecast_evidence_required")
        quantity = Decimal(str(item["quantity"]))
        if quantity > Decimal(forecast["shortage_quantity"]):
            raise ValueError("quantity_exceeds_forecast_shortage")
