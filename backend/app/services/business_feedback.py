"""Chinese business feedback generated from server facts, never model claims."""
import json
import re
from decimal import Decimal

from sqlalchemy import select

from backend.app.models import Material, SupplierMaterial
from backend.app.services.material_search import search_materials, source_mentions_material


class ClarificationRequired(ValueError):
    pass


def unit_name(unit):
    return {"pcs": "件", "set": "套"}.get(unit, unit)


_NUMBER = r"负?-?[0-9零〇一二两三四五六七八九十百千万亿点.]+"


def chinese_number(value):
    value = value.replace("两", "二").replace("〇", "零")
    sign = -1 if value.startswith(("负", "-")) else 1
    value = value.lstrip("负-")
    try:
        return sign * Decimal(value)
    except ArithmeticError:
        pass
    digits = dict(zip("零一二三四五六七八九", range(10)))
    total = section = number = 0
    for char in value:
        if char in digits:
            number = digits[char]
        elif char in "十百千":
            section += (number or 1) * {"十":10,"百":100,"千":1000}[char]
            number = 0
        elif char in "万亿":
            total = (total + section + number) * {"万":10000,"亿":100000000}[char]
            section = number = 0
        else:
            raise ClarificationRequired("数字表达无法确认，请使用明确的数量和金额后重新运行。")
    return Decimal(sign * (total + section + number))


def capture_request(session, arguments, total_budget, source=None):
    items = arguments["items"]
    purchase = arguments["purchase_requested"]
    if not items:
        raise ClarificationRequired("您需要购买或了解哪种物料？请补充物料名称。")
    resolved = []
    for item in items:
        query = item["query"].strip()
        quantity = item["quantity"]
        if quantity is not None and quantity <= 0:
            description = "负数" if quantity < 0 else "零"
            raise ClarificationRequired(f"采购数量为{description}（{quantity}），采购数量必须大于零，请修改数量。")
        candidates = search_materials(session, query, limit=5)
        if not candidates:
            raise ClarificationRequired(f"未找到“{query}”，本次不会替换为其他物料。请核对名称后重新运行。")
        strong = [candidate for candidate in candidates if candidate["score"] >= 0.9]
        if len(strong) > 1:
            raise ClarificationRequired(
                f"“{query}”匹配多个物料，请选择并填写完整名称："
                + "、".join(f"{item['name']}（{item['code']}）" for item in strong)
            )
        top = candidates[0]
        if top["score"] < 0.9:
            raise ClarificationRequired(
                f"未找到明确匹配“{query}”，可能指以下物料，但无法唯一确认："
                + "、".join(f"{item['name']}（{item['code']}）" for item in candidates)
                + "。请确认完整名称或补充更具体的描述。"
            )
        material = session.get(Material, top["material_id"])
        if material is None:
            raise ClarificationRequired(f"未找到“{query}”，本次不会替换为其他物料。请核对名称后重新运行。")
        if source and not source_mentions_material(session, material, source):
            raise ClarificationRequired(f"无法从原文确认您指的是“{material.name}”，请填写完整物料名称或使用数据库中的别名；系统不会擅自替换。")
        quantity = item["quantity"]
        if purchase and quantity is None:
            raise ClarificationRequired(f"您需要购买多少{unit_name(material.unit)}{material.name}？请补充数量。")
        resolved.append({
            "material_id": material.id,
            "name": material.name,
            "unit": unit_name(material.unit),
            "quantity": None if quantity is None else str(quantity),
            "match_type": top["match_type"],
            "match_score": top["score"],
            "matched_alias": top["matched_alias"],
        })
    if len({i["material_id"] for i in resolved}) != len(resolved):
        raise ClarificationRequired("同一物料出现多个数量，请明确最终采购数量后重新运行。")
    if purchase and total_budget is None:
        raise ClarificationRequired("尚未确认整单预算，请在预算栏补填金额并确认后重新运行。")
    stated = arguments["stated_budget"]
    if purchase and stated is not None and stated != total_budget:
        raise ClarificationRequired(f"文字预算{stated}元与预算栏{total_budget}元不一致，请修改预算栏和需求，重新确认整单预算。")
    if purchase and arguments["required_in_days"] is None:
        raise ClarificationRequired("请补充希望几天内到货；未确认交期前不生成订单。")
    result = {"items": resolved, "purchase_requested": purchase, "required_in_days": arguments["required_in_days"],
            "confirmed_total_budget": None if total_budget is None else str(total_budget),
            "stated_budget": None if stated is None else str(stated)}
    if source:
        from backend.app.services.source_conditions import bind_source
        result = bind_source(session, result, source, total_budget)
    return result


def check_request_conditions(session, name, arguments, request):
    """Preserve interpreted user conditions at every downstream write/filter boundary."""
    if name not in {"create_purchase_draft", "recommend_suppliers"}:
        return
    if request.get("verification") == "needs_confirmation":
        raise ClarificationRequired("需求尚未明确确认，不能推荐或生成草稿，请核对完整中文需求清单。")
    if name == "create_purchase_draft" and not request["purchase_requested"]:
        raise ClarificationRequired("本次仅分析，不生成采购订单。如需采购，请明确数量、交期和预算后重新运行。")
    if not request["purchase_requested"]:
        if name == 'recommend_suppliers':
            item = next((i for i in request['items'] if i['material_id'] == arguments['material_id']), None)
            if (item is None or (item['quantity'] is not None and Decimal(item['quantity']) != arguments['quantity'])
                or (request['required_in_days'] is not None and request['required_in_days'] != arguments['required_in_days'])):
                raise ClarificationRequired('供应商分析与原文明确的物料、数量或交期条件不一致，请重新核对。')
        return
    wanted = {i["material_id"]: Decimal(i["quantity"]) for i in request["items"]}
    if name == "recommend_suppliers":
        material_id = arguments["material_id"]
        if material_id not in wanted or Decimal(arguments["quantity"]) != wanted[material_id] or arguments["required_in_days"] != request["required_in_days"]:
            raise ClarificationRequired("供应商筛选与您确认的物料、数量或交期条件不一致，请核对需求后重新运行。")
        return
    actual = {}
    for item in arguments["items"]:
        mid = item["material_id"]
        actual[mid] = actual.get(mid, Decimal(0)) + Decimal(item["quantity"])
    if actual != wanted:
        raise ClarificationRequired("草稿物料或数量与您的采购条件不一致，本次暂停，请核对需求后重新运行。")
    for ref in arguments.get("evidence_refs", []):
        parts = ref.split(":")
        if parts[0] == "recommendation" and len(parts) >= 5 and int(parts[4]) != request["required_in_days"]:
            raise ClarificationRequired("草稿交期证据与您要求的条件不一致，请核对交期后重新运行。")
    # No implicit consent for MOQ/pack rounding. A new request must state the new quantity.
    from backend.app.services.purchase_drafts import _round_order_quantity
    for mid, quantity in actual.items():
        supply = session.scalar(select(SupplierMaterial).where(SupplierMaterial.supplier_id == arguments["supplier_id"], SupplierMaterial.material_id == mid))
        if supply and _round_order_quantity(requested=quantity, moq=Decimal(supply.moq), package_multiple=Decimal(supply.package_multiple)) != quantity:
            raise ClarificationRequired(f"供应商起订量或包装倍数要求多买，您要求{quantity}件。本次未加购；请确认可接受的新数量并修改需求后重新运行。")


def business_outcome(status, error, observations, order=None, request=None):
    next_action = "请修改需求或预算，确认后重新运行。"
    if order is not None:
        items = "、".join(f"{i.material.name}{i.quantity}{unit_name(i.material.unit)}" for i in order.items)
        return f"草稿已生成：{items}；供应商：{order.supplier.name}；整单金额{order.total_amount}元。尚未批准，仍需人工审批。", "采购员请到采购审批核对明细并提交，再由审批员批准或驳回。"
    if status == "needs_information":
        return f"{error} 本次未生成订单。", next_action
    if request and request["purchase_requested"] and request.get("confirmed_total_budget"):
        # A model may safely stop without calling draft creation. Explain the
        # shared-budget failure from server recommendation totals in that case.
        offers = {}
        for obs in observations:
            if obs["tool"] != "recommend_suppliers":
                continue
            for rec in obs["output"].get("recommendations", []):
                offers.setdefault(rec["supplier_id"], {})[obs["arguments"]["material_id"]] = Decimal(rec["total_amount"])
        wanted = {i["material_id"] for i in request["items"]}
        totals = [sum(lines.values(), Decimal(0)) for lines in offers.values() if set(lines) == wanted]
        budget = Decimal(request["confirmed_total_budget"])
        if totals and min(totals) > budget:
            return f"整单共享预算不足：已比较方案的最低参考合计{min(totals)}元，超过您确认的整单预算{budget}元。本次未生成订单，未减数量、加预算或拆单。", next_action
    explanations = []
    for obs in observations:
        output = obs.get("output", {})
        if obs["tool"] == "get_demand_forecast":
            mid = output.get("material_id")
            item = next((i for i in (request or {}).get("items", []) if i["material_id"] == mid), None)
            explanations.append(f"{item['name'] if item else '所查物料'}未来{output.get('horizon_days')}天缺口{output.get('shortage_quantity')}件。")
        if obs["tool"] == "recommend_suppliers":
            active_reasons = [set(row.get("reasons", [])) for row in output.get("excluded", []) if "supplier_inactive" not in row.get("reasons", [])]
            reasons = set.intersection(*active_reasons) if active_reasons else set()
            if not output.get("recommendations"):
                for reason, message in [("budget_exceeded", "当前预算无法满足采购要求。"),
                    ("lead_time_exceeds_required", "没有供应商能够按要求到货。"),
                    ("capacity_below_quantity", "采购数量超过供应商供货能力，不能按要求供货。"),
                    ("quantity_below_moq", "采购数量低于供应商起订量，需要多买。未经您确认不会增加数量；请确认可接受的新数量后修改需求。")]:
                    if reason in reasons:
                        explanations.append(message)
                if not reasons:
                    explanations.append("没有供应商能够同时满足本次数量、预算、交期和起订量条件，请调整可接受的条件。")
            else:
                recs = output["recommendations"]
                explanations.append("合适的供应商：" + "、".join(f"{r['supplier_name']}（单价{r['unit_price']}元，综合评分{r['score']}）" for r in recs) + "；依据价格、准时交付、质量及投诉表现比较。")
    if error == "order_budget_exceeded":
        explanations.append("两样合计超过整单共享预算，当前预算不足，不能按每种物料分别使用整单预算。")
    elif error == "quantity_exceeds_forecast_shortage":
        explanations.append("采购数量超过当前缺口，不能按此数量生成草稿，请核对实际需求。")
    elif error:
        explanations.append("本次处理未能完成，请核对需求；若仍失败，请联系管理员查看排查详情。")
    elif status == "material_not_found":
        explanations.append("未找到该物料，请核对名称；不会自动替换。")
    elif status == "material_ambiguous":
        names = [m["name"] for o in observations for m in o.get("output", {}).get("matches", [])] if observations else []
        explanations.append("存在多个匹配，请选择并填写完整名称：" + "、".join(names))
    if not explanations:
        explanations.append("需求信息不足或尚未形成可执行采购方案，请明确物料名称、数量、预算与到货要求。")
    return " ".join(explanations) + " 本次未生成订单。", "仅分析已完成，可调整数量、交期后重新分析；需要采购时请明确需求并确认预算。" if request and not request["purchase_requested"] else next_action


def order_business_details(order):
    evidence = json.loads(order.evidence_refs_json or "[]")
    refs = evidence if isinstance(evidence, list) else evidence.get("refs", [])
    days = set()
    for ref in refs:
        parts = ref.split(":")
        if parts[0] == "recommendation" and len(parts) >= 5 and parts[4].isdigit() and 1 <= int(parts[4]) <= 365:
            days.add(int(parts[4]))
    days = sorted(days)
    return {"delivery_requirement": "、".join(f"{d}天内到货" for d in days) if days else "交付要求无法确认，请核对原始需求",
        "recommendation_basis": ("已按报价、准时交付率、质量合格率、投诉率综合评分，并校验交期、供货能力及起订量。" + ("整单预算已校验。" if order.total_budget is not None else "整单预算无法确认（历史订单），请先核对预算。")) if days else "推荐依据无法确认，请核对历史证据",
        "items": [{"material_id": i.material_id, "material_name": i.material.name, "unit": unit_name(i.material.unit),
                   "quantity": i.quantity, "unit_price": i.unit_price, "line_amount": i.line_amount} for i in order.items]}
