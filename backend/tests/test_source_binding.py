"""Wrong model arguments run through the actual loop/tools, never parser-only probes."""
from decimal import Decimal
import json

import pytest
from sqlalchemy import select

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import PurchaseOrder
from backend.app.services.seed import seed_demo_data
from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import MockLLMProvider, ToolCall


SOURCE = '标准轴承买120件，铝合金外壳买80件，20天内到货，两样合计最多5000元，生成一张草稿等人工审批。'


@pytest.fixture
def engine():
    e = create_sqlite_engine('sqlite+pysqlite:///:memory:')
    with session_scope(e) as s:
        seed_demo_data(s)
    return e


def calls_for(items, days=20):
    calls = [ToolCall('capture_request', {'items': [{'query': name, 'quantity': q} for _, name, q in items],
        'purchase_requested': True, 'stated_budget': '5000', 'required_in_days': days})]
    for mid, _, q in items:
        calls.extend([ToolCall('get_demand_forecast', {'material_id': mid, 'horizon_days': 30}),
            ToolCall('recommend_suppliers', {'material_id': mid, 'quantity': q, 'required_in_days': days, 'budget': '5000'})])
    calls.append(ToolCall('create_purchase_draft', {'supplier_id': 1,
        'items': [{'material_id': mid, 'quantity': q} for mid, _, q in items],
        'idempotency_key': 'source-binding-regression', 'evidence_refs': ['use_latest_forecast', 'use_latest_recommendation']}))
    return calls


def run(engine, prompt, items, days=20):
    provider = MockLLMProvider(calls_for(items, days))
    provider.real_function_calling = True  # simulated wrong arguments, production source checks
    return AgentLoop(engine=engine, provider=provider).run(prompt, total_budget=Decimal('5000'))


@pytest.mark.parametrize('prompt,items', [
    (SOURCE, [(1,'标准轴承','80'),(2,'铝合金外壳','120')]),
    (SOURCE, [(1,'标准轴承','120')]),
    (SOURCE, [(1,'标准轴承','120'),(2,'铝合金外壳','80'),(3,'工业传感器','120')]),
    (SOURCE, [(1,'标准轴承','120'),(3,'工业传感器','80')]),
    ('请分析采购120件标准轴承的方案，20天内到货，总预算5000元。现在只分析，不要生成采购单。', [(1,'标准轴承','120')]),
])
def test_injected_wrong_model_cannot_create(engine, prompt, items):
    result = run(engine, prompt, items)
    assert result.status == 'needs_information', result
    assert result.purchase_order_id is None
    with session_scope(engine) as s:
        assert not s.scalars(select(PurchaseOrder)).all()


def test_correct_two_materials_create(engine):
    result = run(engine, SOURCE, [(1,'标准轴承','120'),(2,'铝合金外壳','80')])
    assert result.status == 'draft_created', result
    assert result.total_amount == Decimal('1628')


@pytest.mark.parametrize('phrase,days', [('20天内交付',20),('两周内到货',14),('二十天内送达',20),('20天内送到',20)])
def test_delivery_chain(engine, phrase, days):
    result = run(engine, f'请买120件标准轴承，{phrase}，总预算5000元，生成草稿等人工审批。', [(1,'标准轴承','120')], days)
    assert result.status == 'draft_created', result


@pytest.mark.parametrize('amount,allowed', [('5,000',True),('50,00',False),('5,00,0',False),('5,000.0.0',False)])
def test_budget_token_chain(engine, amount, allowed):
    result = run(engine, f'请买120件标准轴承，20天内到货，预算为{amount}元，生成草稿等人工审批。', [(1,'标准轴承','120')])
    assert (result.status == 'draft_created') == allowed, result
    if not allowed:
        assert '金额格式' in result.business_message


def test_explicit_confirmation_bound_to_run_and_source(engine):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    prompt = '请买标准轴承和铝合金外壳，分别要120件与80件，20天内到货，总预算5000元，先做草稿。'
    items = [(1,'标准轴承','120'),(2,'铝合金外壳','80')]
    def provider():
        p = MockLLMProvider(calls_for(items)); p.real_function_calling = True
        return p
    client = TestClient(create_app(engine, auth_secret='binding', agent_provider_factory=provider))
    token = client.post('/auth/login', json={'username':'buyer','password':'buyer-pass'}).json()['access_token']
    h = {'Authorization': f'Bearer {token}'}
    first = client.post('/agent/runs',headers=h,json={'prompt':prompt,'total_budget':'5000'}).json()
    assert first['status'] == 'awaiting_confirmation', first
    assert not first['purchase_order_id']
    assert all(w in first['business_message'] for w in ['标准轴承','120','铝合金外壳','80','5000','20天'])
    body = {'prompt':prompt,'total_budget':'5000','confirmation_fingerprint':first['confirmation_fingerprint']}
    changed = client.post(f"/agent/runs/{first['run_id']}/confirm",headers=h,json={**body,'prompt':prompt.replace('120','80')})
    assert changed.status_code == 409
    confirmed = client.post(f"/agent/runs/{first['run_id']}/confirm",headers=h,json=body)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()['status'] == 'draft_created', confirmed.text
    again = client.post(f"/agent/runs/{first['run_id']}/confirm",headers=h,json=body)
    assert again.status_code == 409


def test_post_capture_changes_and_approval_tampering_are_blocked(engine):
    from backend.app.services.agent_tools import execute_agent_tool
    from backend.app.services.business_feedback import ClarificationRequired
    from backend.app.services.approvals import AuthContext, ApprovalActionInput, ApprovalValidationError, submit_for_approval, approve_order
    items = [(1,'标准轴承','120'),(2,'铝合金外壳','80')]
    with session_scope(engine) as s:
        registry = {'request_source': {'prompt': SOURCE}}
        capture = calls_for(items)[0]
        execute_agent_tool(s, capture.name, capture.arguments, registry, total_budget=Decimal('5000'))
        bad = {'material_id':1,'quantity':'80','required_in_days':20,'budget':'5000'}
        with pytest.raises(ClarificationRequired):
            execute_agent_tool(s, 'recommend_suppliers', bad, registry, total_budget=Decimal('5000'))
        registry['request_source']['prompt'] = SOURCE.replace('120','100')
        with pytest.raises(ClarificationRequired, match='旧确认'):
            execute_agent_tool(s, 'recommend_suppliers', bad, registry, total_budget=Decimal('5000'))
    result = run(engine, SOURCE, items)
    with session_scope(engine) as s:
        order = s.get(PurchaseOrder, result.purchase_order_id)
        evidence = json.loads(order.evidence_refs_json)
        assert evidence['user_request']['verification'] == 'source_verified'
        # Both actual and requested items are changed together. Source evidence must
        # still reject this, even if numerical constraints would otherwise pass.
        order.items[0].quantity = Decimal('80')
        order.requested_items_json = json.dumps([{'material_id':1,'quantity':'80'},{'material_id':2,'quantity':'80'}])
        submit_for_approval(s, order.id, AuthContext('buyer-1','buyer'))
        with pytest.raises(ApprovalValidationError, match='采购条件'):
            approve_order(s, order.id, AuthContext('approver-1','approver'), ApprovalActionInput(order.version, 'tampered-source-approval'))


@pytest.mark.parametrize('phrase,days', [('明天到货',20),('后天送达',20),('两周内到货',30),('20天内交付或30天内到货',30)])
def test_model_cannot_extend_or_choose_ambiguous_delivery(engine, phrase, days):
    result = run(engine, f'请买120件标准轴承，{phrase}，预算5000元，生成草稿。', [(1,'标准轴承','120')], days)
    assert result.status == 'needs_information'
    assert result.purchase_order_id is None


@pytest.mark.parametrize('prompt,qty', [
    ('请采购120件标准轴承，20天内到货，预算5000元。不要生成采购单，如果方案合适我会另行确认。','120'),
    ('本次标准轴承买120件，标准轴承上次买80件，20天内到货，总预算5000元，生成草稿。','80'),
    ('请买120件标准轴承，20天内到货，参考单价8元且整单总预算100元，生成草稿等人工审批。','120'),
    ('请买120件标准轴承，另买80件火星配件，20天内到货，总预算5000元，生成草稿。','120'),
    ('请买120件标准轴承，20天内到货，总预算100 元，生成草稿。','120'),
    ('请买120套标准轴承，20天内到货，总预算5000元，生成草稿。','120'),
    ('请分析采购120件标准轴承的方案，20天内到货，预算5000元。先不生成采购单。','120'),
    ('请分析采购120件标准轴承的方案，20天内到货，预算5000元。不要下单。','120'),
    ('请分析采购120件标准轴承的方案，20天内到货，预算5000元。这次暂不创建草稿。','120'),
    ('请买120件标准轴承，20天内到货，总预算100，生成草稿。','120'),
    ('请买120件标准轴承，20天内到货，上次预算5000元但本次预算100元，生成草稿。','120'),
    ('请买120件标准轴承，20天内到货，预算栏5000元但实际整单预算100元，生成草稿。','120'),
])
def test_review_adversarial_source_guards(engine, prompt, qty):
    result = run(engine, prompt, [(1,'标准轴承',qty)])
    assert result.purchase_order_id is None, result
    assert result.status in {'needs_information','awaiting_confirmation'}, result


@pytest.mark.parametrize('remove_anchor',[False, True])
def test_approval_fetches_original_run_instead_of_self_comparing_order_evidence(engine, remove_anchor):
    from backend.app.services.source_conditions import source_digest
    from backend.app.services.approvals import AuthContext, ApprovalActionInput, ApprovalValidationError, submit_for_approval, approve_order
    prompt = '请买120件标准轴承，20天内到货，总预算5000元，生成草稿。'
    result = run(engine, prompt, [(1,'标准轴承','120')])
    with session_scope(engine) as s:
        order = s.get(PurchaseOrder,result.purchase_order_id)
        evidence = json.loads(order.evidence_refs_json)
        saved = evidence['user_request']
        saved['items'][0]['quantity'] = '80'
        saved['source_prompt'] = prompt.replace('120','80')
        saved['source_digest'] = source_digest(saved['source_prompt'],Decimal('5000'))
        if remove_anchor:
            saved.pop('source_run_id')
        evidence['refs'] = [r.replace(':120:',':80:').replace(':120.0:',':80:') for r in evidence['refs']]
        order.evidence_refs_json = json.dumps(evidence)
        order.requested_items_json = json.dumps([{'material_id':1,'quantity':'80'}])
        order.items[0].quantity = Decimal('80')
        order.items[0].line_amount = order.total_amount = Decimal('648')
        submit_for_approval(s, order.id, AuthContext('buyer-1','buyer'))
        with pytest.raises(ApprovalValidationError, match='原始执行记录'):
            approve_order(s, order.id, AuthContext('approver-1','approver'), ApprovalActionInput(order.version, 'source-evidence-tamper'))


def test_quote_condition_does_not_cancel_no_order(engine):
    prompt = '请分析采购120件标准轴承的方案，20天内到货，总预算5000元，如果方案合适请先列出报价，不要生成采购单。'
    result = run(engine,prompt,[(1,'标准轴承','120')])
    assert result.purchase_order_id is None, result


@pytest.mark.parametrize('capture_qty,rec_qty,days',[('80','80',20),('120','80',20),('120','120',30)])
def test_explicit_analysis_conditions_bind_capture_and_recommendation(engine,capture_qty,rec_qty,days):
    prompt = '请只分析采购120件标准轴承的方案，20天内到货，总预算5000元，不要生成采购单。'
    calls = calls_for([(1,'标准轴承',capture_qty)])[:1]
    calls.append(ToolCall('recommend_suppliers',{'material_id':1,'quantity':rec_qty,'required_in_days':days,'budget':'5000'}))
    provider=MockLLMProvider(calls);provider.real_function_calling=True
    result=AgentLoop(engine=engine,provider=provider).run(prompt,total_budget=Decimal('5000'))
    assert result.status=='needs_information',result


def test_model_key_cannot_select_legacy_order_or_break_approval(engine):
    from backend.app.services.approvals import AuthContext, ApprovalActionInput, submit_for_approval, approve_order
    items=[(1,'标准轴承','120')]
    old=AgentLoop(engine=engine,provider=MockLLMProvider(calls_for(items))).run('offline legacy fixture',total_budget=Decimal('5000'))
    replay=run(engine,'请买120件标准轴承，20天内到货，总预算5000元，生成草稿。',items)
    assert replay.purchase_order_id!=old.purchase_order_id
    with session_scope(engine) as s:
        order=submit_for_approval(s,replay.purchase_order_id,AuthContext('buyer-1','buyer'))
        approved=approve_order(s,order.id,AuthContext('approver-1','approver'),ApprovalActionInput(order.version,'legacy-replay-approval'))
        assert approved.status=='approved'


def test_server_run_idempotency_survives_model_key_changes(engine):
    from backend.app.models import AgentRun
    from backend.app.services.agent_tools import execute_agent_tool
    prompt='请买120件标准轴承，20天内到货，总预算5000元，生成草稿。'
    result=run(engine,prompt,[(1,'标准轴承','120')])
    with session_scope(engine) as s:
        saved=json.loads(s.get(AgentRun,result.run_id).state_json)['user_request']
        registry={'request_source':{'prompt':prompt,'run_id':result.run_id},'user_request':saved}
        execute_agent_tool(s,'get_demand_forecast',{'material_id':1,'horizon_days':30},registry,total_budget=Decimal('5000'))
        execute_agent_tool(s,'recommend_suppliers',{'material_id':1,'quantity':'120','required_in_days':20,'budget':'5000'},registry,total_budget=Decimal('5000'))
        draft=calls_for([(1,'标准轴承','120')])[-1].arguments
        draft['idempotency_key']='model-changed-the-key'
        repeated=execute_agent_tool(s,'create_purchase_draft',draft,registry,total_budget=Decimal('5000'))
        assert repeated.id==result.purchase_order_id
        assert repeated.idempotency_key==f'agent-run-{result.run_id}'
        assert len(s.scalars(select(PurchaseOrder)).all())==1


