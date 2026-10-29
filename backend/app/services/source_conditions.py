"""Independent, conservative binding of source text to server-owned conditions.

Unsupported bindings require an explicit human review; model membership in a bag
of source numbers is never evidence that a material/quantity pair is correct.
"""
import hashlib
import json
import re
from decimal import Decimal

from sqlalchemy import select
from backend.app.models import Material


NUMBER = r'负?-?[0-9零〇一二两三四五六七八九十百千万亿点.]+'


def source_digest(prompt, budget):
    return hashlib.sha256(json.dumps([prompt, None if budget is None else str(Decimal(budget).normalize())], ensure_ascii=False).encode()).hexdigest()


def analysis_only(prompt):
    if re.search(r'只(?:做)?分析|仅(?:做)?分析|只是了解|只了解', prompt):
        return True
    for match in re.finditer(r'(?:不(?:要|用|需)?|禁止)(?:(?:生成|创建|建)(?:采购)?(?:单|草稿|订单)|下单)', prompt):
        prefix = re.split(r'[。；;]', prompt[:match.start()])[-1]
        # A condition must precede THIS prohibition; a later "if" cannot cancel it.
        failure_condition = r'(?:如果)?(?:买不到|无法满足|预算不足|预算不够|没有[^，。；]{0,20}供应商)(?:就|则|也)?(?:[，,]?请告诉我原因[，,]?)?请?$'
        if not re.search(failure_condition, prefix):
            return True
    return False


def current_amounts(prompt):
    from backend.app.services.business_feedback import chinese_number, ClarificationRequired
    # Consume the ENTIRE numeric token, including malformed grouping/decimals.
    token = r'负?-?[0-9零〇一二两三四五六七八九十百千万亿点.,，eE+/\s]+'
    result = []
    matches = [(m.start(), m.end(), m[1], '') for m in re.finditer(f'({token})(?:元|块钱|块)', prompt)]
    for m in re.finditer(f'(总预算|预算|合计|总共|一共|最多花|只能花)(?:为|是|：|:)?\\s*({token})', prompt):
        if not any(a <= m.start(2) < b for a,b,_,_ in matches):
            matches.append((m.start(),m.end(),m[2].rstrip('，, '),m[1]))
    for start, end, raw, label in matches:
        raw = raw.strip().lstrip('，,').strip()
        prefix = re.split(r'[，。；,;]', prompt[:start])[-1] + label
        prefix = re.split(r'但是|但|本次|这次|现在|实际|当前', prefix)[-1]
        unit_context = list(re.finditer(r'单价|每件|每个|每套|每样', prefix))
        order_context = list(re.finditer(r'整单|总预算|预算|总共|一共|合计|最多花|只能花|同意', prefix))
        if unit_context and (not order_context or unit_context[-1].start() > order_context[-1].start()):
            continue
        if re.search(r'上次|历史|以前|原来|原先|之前|预算栏', prefix):
            continue
        if re.match(r'是上次|是旧|历史金额', prompt[end:end+12]):
            continue
        # Only current whole-order amounts; quoted prices/history are not budgets.
        if not re.search(r'预算|总共|一共|合计|合起来|加起来|最多|花|只有|同意', prefix):
            continue
        if re.search(r'[0-9]', raw):
            if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:[,，]\d{3})+)(?:\.\d{1,2})?', raw):
                raise ClarificationRequired(f'金额格式“{raw}”无法确认，请使用5000或5,000.00这样的完整金额后重新运行。')
            value = Decimal(raw.replace(',', '').replace('，', ''))
        else:
            value = chinese_number(raw)
        result.append(value)
    return result


def source_days(prompt):
    from backend.app.services.business_feedback import chinese_number, ClarificationRequired
    verbs = r'(?:交付|交货|到货|送达|送到|到达)'
    found = [chinese_number(m[1]) * (7 if m[2] in ('周','星期') else 1)
             for m in re.finditer(f'({NUMBER})(天|周|星期)(?:之?内)?(?:全部)?{verbs}', prompt)]
    for word, value in [('明天',1),('明日',1),('后天',2)]:
        if re.search(f'{word}[^，。；]{{0,4}}{verbs}', prompt):
            found.append(Decimal(value))
    if len(set(found)) > 1:
        raise ClarificationRequired('原文有多个不同交期，请明确最终几天内到货；不会擅自延长交期。')
    return int(found[0]) if found and found[0] == int(found[0]) else None


def bind_source(session, request, prompt, budget):
    from backend.app.services.business_feedback import chinese_number, ClarificationRequired
    request = {**request, 'source_prompt': prompt, 'source_digest': source_digest(prompt, budget)}
    if analysis_only(prompt):
        request['purchase_requested'] = False
    amounts = current_amounts(prompt)
    conflicts = [v for v in amounts if budget is not None and v != budget]
    if conflicts:
        raise ClarificationRequired(f'文字金额{conflicts[0]}元与预算栏{budget}元不一致，请修改需求和预算栏，重新确认。')
    if re.search(r'数量[^，。；]{0,6}(?:就是|为|是)零', prompt):
        raise ClarificationRequired('您明确说明采购数量为零，采购数量必须大于零，请修改数量。')
    materials = list(session.scalars(select(Material).order_by(Material.id)))
    mentioned = {m.id: m for m in materials if m.name in prompt or m.code.lower() in prompt.lower()}
    wanted = {i['material_id']: i for i in request['items']}
    if set(mentioned) != set(wanted):
        raise ClarificationRequired('原文物料与提取清单不一致（遗漏、增加或替换物料），请填写完整物料名称和各自数量后重新确认。')
    bound = {}
    unresolved = False
    for clause in re.split(r'[，。；,;]', prompt):
        names = [m for m in mentioned.values() if m.name in clause or m.code.lower() in clause.lower()]
        quantities = list(re.finditer(f'({NUMBER})(件|个|套)', clause))
        if re.search(r'上次|历史|以前|原来|原先|之前', clause) and not re.search(r'本次|现在|这次|当前', clause):
            continue
        if quantities and not names and not re.search(r'不能|不得|不对|以|改成|数量|起订|多买|少买|减少|每样', clause):
            unresolved = True
        if not names or not quantities:
            continue
        for material in names:
            allowed_units = {'件','个'} if material.unit == 'pcs' else {'套'} if material.unit == 'set' else {material.unit}
            if any(q[2] not in allowed_units for q in quantities):
                raise ClarificationRequired(f'{material.name}原文数量单位与系统单位不同，请明确数量及单位换算后重新确认，不能擅自换算。')
        if len(names) > 1:
            if len(quantities) == 1 and re.search(r'各(?:买|采购|要|需)?', clause):
                for m in names:
                    bound[m.id] = chinese_number(quantities[0][1])
            continue
        m = names[0]
        # A single named material and a single quantity are unambiguous.
        if len(quantities) == 1:
            quantity = chinese_number(quantities[0][1])
            if m.id in bound and bound[m.id] != quantity:
                raise ClarificationRequired(f'{m.name}出现多个不同数量，请明确最终采购数量后重新确认。')
            bound[m.id] = quantity
    # Explicit correction applies only to the sole named material.
    if len(mentioned) == 1:
        final = re.search(f'以({NUMBER})(?:件|个|套)为准', prompt)
        if final:
            bound[next(iter(mentioned))] = chinese_number(final[1])
    for mid, qty in bound.items():
        if qty <= 0:
            raise ClarificationRequired(f'原文数量{qty}为零或负数，数量必须大于零，请修改数量。')
        if wanted[mid]['quantity'] is not None and Decimal(wanted[mid]['quantity']) != qty:
            raise ClarificationRequired(f'{mentioned[mid].name}原文数量为{qty}件，与提取数量不一致，请核对物料与数量条件后重新确认。')
        wanted[mid]['quantity'] = str(qty)
    if not request['purchase_requested']:
        # Analysis may omit quantity/deadline. Only independently supported
        # explicit conditions constrain recommendations; model guesses aren't
        # silently promoted to confirmed conditions in this read-only path.
        for item in request['items']:
            if item['material_id'] not in bound:
                item['quantity'] = None
        days = source_days(prompt)
        if days is not None and request['required_in_days'] is not None and request['required_in_days'] != days:
            raise ClarificationRequired(f'原文分析交期为{days}天，提取交期不一致，请核对条件。')
        request['required_in_days'] = days
        return {**request, 'verification': 'source_verified'}
    all_quantities = [chinese_number(q) for q in re.findall(f'({NUMBER})(?:件|个|套)', prompt)]
    if not all_quantities:
        raise ClarificationRequired('无法从原文确认采购数量，请填写明确数量后重新运行。')
    days = source_days(prompt)
    if days is None:
        raise ClarificationRequired('原文交期表达暂无法可靠核对，请明确几天内交付、到货或送达；不会擅自延长交期。')
    if request['required_in_days'] != days:
        raise ClarificationRequired(f'原文要求{days}天内到货，提取交期不一致，请重新确认；不会擅自延长交期。')
    # Unknown association can be reviewed, but known contradiction cannot.
    request['verification'] = 'source_verified' if set(bound) == set(wanted) and not unresolved else 'needs_confirmation'
    return request


def request_summary(request):
    lines = '；'.join(f"{i['name']}：{i['quantity']}{i['unit']}" for i in request['items'])
    return f"完整需求清单：{lines}；{request['required_in_days']}天内到货；整单共享预算{request['confirmed_total_budget']}元；仅生成草稿，等待人工审批。"


def validate_saved_request(session, request, prompt, budget):
    from backend.app.services.business_feedback import ClarificationRequired
    if request.get('source_run_id') is not None:
        from backend.app.models import AgentRun
        run = session.get(AgentRun, request['source_run_id'])
        state = json.loads(run.state_json) if run else {}
        saved = state.get('human_confirmation') if request.get('verification') == 'human_confirmed' else state.get('user_request')
        if run is None or run.prompt != prompt or run.total_budget != budget or saved != request:
            raise ClarificationRequired('需求证据与原始执行记录或本次人工确认不一致，请重新核对需求。')
    if request.get('source_digest') != source_digest(prompt, budget):
        raise ClarificationRequired('需求或预算已经修改，旧确认已失效，请重新核对本次完整需求清单。')
    if request.get('verification') == 'human_confirmed':
        if analysis_only(prompt):
            raise ClarificationRequired('本次仅分析，不能生成采购草稿。')
        return request
    return bind_source(session, request, prompt, budget)
