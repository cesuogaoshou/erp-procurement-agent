from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session
from pydantic import ValidationError
from backend.app.schemas.tool_parameters import TOOL_PARAMETER_MODELS

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
    descriptions = {
        "list_materials": "List materials with stable IDs/codes. Reuse this mapping throughout the run.",
        "resolve_material": "Resolve a material code or name fragment; avoid this when the ID is already known.",
        "get_inventory": "Inventory only. Usually unnecessary: get_demand_forecast already includes current inventory and available supply.",
        "get_demand_forecast": "Forecast demand AND inventory, available supply, shortage, and evidence for one material (1-180 days). Call once per material/horizon; reuse current-run evidence.",
        "recommend_suppliers": "Recommend suppliers for positive finite quantity. Use forecast shortage or user's smaller quantity. Budget is a per-line filter, never the whole-order budget decision. Evidence must cover final MOQ/package rounded quantity.",
        "create_purchase_draft": "Create one draft for one supplier and multiple materials; backend aggregates duplicate lines, rounds once and enforces the confirmed whole-order budget. No approval. Use all relevant current-run evidence; use_latest_forecast/use_latest_recommendation expand to all relevant materials. Budget is injected by server; do not supply or change it.",
    }
    return [AgentTool(name, description, TOOL_PARAMETER_MODELS[name].model_json_schema(),
                      "create_draft" if name == "create_purchase_draft" else "read_only")
            for name, description in descriptions.items()]


def execute_agent_tool(
    session: Session,
    name: str,
    arguments: dict[str, Any],
    evidence_registry: dict[str, dict[str, Any]] | None = None,
    *, total_budget: Decimal | None = None,
) -> Any:
    model = TOOL_PARAMETER_MODELS.get(name)
    if model is None:
        raise ValueError(f"tool_not_allowed:{name}")
    try:
        arguments = model.model_validate(arguments).model_dump()
    except ValidationError as exc:
        errors = [{"loc": list(error["loc"]), "type": error["type"]} for error in exc.errors()]
        raise ValueError(f"tool_parameter_error:{name}:{errors}") from exc
    if name == "recommend_suppliers" and total_budget is not None:
        if arguments.get("budget") is not None and arguments["budget"] > total_budget:
            raise ValueError("tool_parameter_error:budget_exceeds_confirmed_total")
    if name == "list_materials":
        return [{"id": item.id, "code": item.code, "name": item.name,
                 "unit": item.unit, "safety_stock": str(item.safety_stock)} for item in list_materials(session)]
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
        return snapshot
    if name == "get_demand_forecast":
        for ref, cached in (evidence_registry or {}).items():
            if ref.startswith("forecast:") and cached.get("material_id") == arguments["material_id"] and cached.get("horizon_days") == arguments["horizon_days"]:
                evidence_registry.pop(ref)
                evidence_registry[ref] = cached
                return cached
        forecast = get_demand_forecast(
            session,
            material_id=int(arguments["material_id"]),
            horizon_days=int(arguments["horizon_days"]),
        )
        if evidence_registry is not None:
            evidence_registry.pop(forecast["evidence_ref"], None)
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
        evidence_ref = _recommendation_ref(
            material_id=int(arguments["material_id"]),
            supplier_id=result.recommendations[0].supplier_id if result.recommendations else None,
            quantity=Decimal(str(arguments["quantity"])),
            required_in_days=int(arguments["required_in_days"]),
            budget=None if arguments.get("budget") is None else Decimal(str(arguments["budget"])),
        )
        output = {
            "evidence_ref": evidence_ref,
            "recommendations": result.recommendations,
            "excluded": result.excluded,
        }
        if evidence_registry is not None and evidence_ref is not None:
            evidence_registry.pop(evidence_ref, None)
            evidence_registry[evidence_ref] = output
        return output
    if name == "create_purchase_draft":
        resolved_refs, forecast_evidence = _validate_forecast_evidence(arguments, evidence_registry or {})
        resolved_refs = _resolve_recommendation_evidence_refs(resolved_refs, evidence_registry or {})
        order = create_purchase_draft(
            session,
            PurchaseDraftInput(
                supplier_id=int(arguments["supplier_id"]),
                items=[
                    DraftItemInput(material_id=int(item["material_id"]), quantity=Decimal(str(item["quantity"])))
                    for item in arguments["items"]
                ],
                idempotency_key=str(arguments["idempotency_key"]),
                evidence_refs=resolved_refs,
                evidence_payloads=forecast_evidence,
                total_budget=total_budget,
            ),
        )
        return order
    raise ValueError(f"tool_not_allowed:{name}")


def _validate_forecast_evidence(
    arguments: dict[str, Any],
    evidence_registry: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    refs = [str(item) for item in arguments.get("evidence_refs", [])]
    if "use_latest_forecast" in refs and evidence_registry:
        forecast_refs = _latest_refs_per_material(evidence_registry, "forecast:")
        if forecast_refs:
            refs = [r for ref in refs for r in (forecast_refs if ref == "use_latest_forecast" else [ref])]
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
    return refs, [forecast["forecast_evidence"] for forecast in forecasts]


def _resolve_recommendation_evidence_refs(
    refs: list[str],
    evidence_registry: dict[str, dict[str, Any]],
) -> list[str]:
    if "use_latest_recommendation" in refs and evidence_registry:
        recommendation_refs = _latest_refs_per_material(evidence_registry, "recommendation:")
        if recommendation_refs:
            refs = [r for ref in refs for r in (recommendation_refs if ref == "use_latest_recommendation" else [ref])]
    return refs


def _latest_refs_per_material(registry: dict[str, dict[str, Any]], prefix: str) -> list[str]:
    latest: dict[str, str] = {}
    for ref in registry:
        if ref.startswith(prefix):
            latest[ref.split(":")[1]] = ref
    return list(latest.values())


def _recommendation_ref(
    *,
    material_id: int,
    supplier_id: int | None,
    quantity: Decimal,
    required_in_days: int,
    budget: Decimal | None,
) -> str | None:
    if supplier_id is None:
        return None
    budget_part = "none" if budget is None else str(budget)
    return f"recommendation:{material_id}:{supplier_id}:{quantity}:{required_in_days}:{budget_part}"
