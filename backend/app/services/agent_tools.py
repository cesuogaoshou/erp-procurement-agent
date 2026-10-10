from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.app.services.inventory import get_inventory_snapshot, list_materials
from backend.app.services.purchase_drafts import DraftItemInput, PurchaseDraftInput, create_purchase_draft
from backend.app.services.recommendations import recommend_for_material


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
            name="get_inventory",
            description="Read inventory for one material.",
            parameters={
                "type": "object",
                "properties": {"material_id": {"type": "integer"}},
                "required": ["material_id"],
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


def execute_agent_tool(session: Session, name: str, arguments: dict[str, Any]) -> Any:
    if name == "list_materials":
        return [item.__dict__ for item in list_materials(session)]
    if name == "get_inventory":
        snapshot = get_inventory_snapshot(session, int(arguments["material_id"]))
        return snapshot.__dict__
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
