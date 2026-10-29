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
        "capture_request": "First extract the user's request: material queries exactly as stated (never substitute), final corrected quantity per material (null if missing, zero/negative preserved), purchase_requested false ONLY for analysis-only tasks, stated_budget user's CURRENT whole-order budget (null if absent), required_in_days (null if absent). Backend resolves names and returns IDs; reuse them. Do not infer missing values or consent. Do not repeat this tool.",
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
    if name == "capture_request":
        from backend.app.services.business_feedback import capture_request
        registry = evidence_registry if evidence_registry is not None else {}
        if "user_request" in registry:
            raise ValueError("request_already_captured")
        result = capture_request(session, arguments, total_budget, registry.get("request_source", {}).get("prompt"))
        if registry.get('request_source', {}).get('run_id') is not None:
            result['source_run_id'] = registry['request_source']['run_id']
        confirmed = registry.get("human_confirmation")
        if confirmed:
            from backend.app.services.source_conditions import validate_saved_request
            confirmed = validate_saved_request(session, confirmed, registry["request_source"]["prompt"], total_budget)
            if any(result[k] != confirmed[k] for k in ("items", "purchase_requested", "required_in_days", "confirmed_total_budget")):
                from backend.app.services.business_feedback import ClarificationRequired
                raise ClarificationRequired("模型提取与本次人工确认需求不一致，请重新核对，不会修改已确认条件。")
            result = confirmed
        if evidence_registry is not None:
            evidence_registry["user_request"] = result
        return result
    from backend.app.services.business_feedback import check_request_conditions
    if evidence_registry and "request_source" in evidence_registry and name in {"recommend_suppliers", "create_purchase_draft"}:
        from backend.app.services.source_conditions import validate_saved_request
        if "user_request" not in evidence_registry:
            from backend.app.services.business_feedback import ClarificationRequired
            raise ClarificationRequired("尚未核对原文需求，不允许推荐或生成草稿。")
        evidence_registry["user_request"] = validate_saved_request(session, evidence_registry["user_request"], evidence_registry["request_source"]["prompt"], total_budget)
    if evidence_registry and "user_request" in evidence_registry:
        check_request_conditions(session, name, arguments, evidence_registry["user_request"])
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
        source_run_id = (evidence_registry or {}).get('request_source', {}).get('run_id')
        if source_run_id is not None:
            # The model cannot select a historical order or collide two different
            # business executions by inventing/reusing an idempotency key. Retries
            # inside this server-owned run still resolve to exactly one draft.
            arguments['idempotency_key'] = f'agent-run-{source_run_id}'
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
                user_request=((evidence_registry or {}).get("user_request") if (evidence_registry or {}).get("request_source") else None),
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
