import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.main import create_app
from backend.app.models import AgentRun, PurchaseOrder, Material
from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import MockLLMProvider, OpenAIFunctionCallingProvider, ToolCall
from backend.app.services.seed import seed_demo_data


@pytest.fixture
def engine():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        session.add(Material(code="TEST-AMBIGUOUS", name="标准连接件", unit="pcs", safety_stock=0))
    return engine


def intent(items=None, **kw):
    return ToolCall("capture_request", dict(items=items if items is not None else [{"query": "标准轴承", "quantity": "120"}],
        purchase_requested=True, stated_budget="5000", required_in_days=20, **kw))


@pytest.mark.parametrize("call,budget,words", [
    (intent([]), "5000", ["哪种物料", "未生成订单"]),
    (intent([{"query": "标准轴承", "quantity": None}]), "5000", ["数量", "补充"]),
    (intent([{"query": "标准轴承", "quantity": "0"}]), "5000", ["大于零"]),
    (intent([{"query": "标准轴承", "quantity": "-120"}]), "5000", ["负数", "-120"]),
    (intent([{"query": "火星牌超导轴承", "quantity": "120"}]), "5000", ["未找到", "火星牌超导轴承"]),
    (intent([{"query": "标准", "quantity": "120"}]), "5000", ["选择", "标准"]),
    (intent(), None, ["预算栏", "确认"]),
    (ToolCall("capture_request", {**intent().arguments, "stated_budget": "100"}), "5000", ["100", "5000", "不一致", "重新确认"]),
])
def test_clarification_persists_and_never_creates(engine, call, budget, words):
    result = AgentLoop(engine=engine, provider=MockLLMProvider([call])).run("采购需求", total_budget=None if budget is None else Decimal(budget))
    assert result.status == "needs_information"
    assert all(word in result.business_message for word in words)
    assert result.next_action
    with session_scope(engine) as s:
        assert not s.scalars(select(PurchaseOrder)).all()
        state = json.loads(s.get(AgentRun, result.run_id).state_json)
        assert state["business_message"] == result.business_message


def test_provider_keeps_text_without_tools(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "请问您要购买多少件？"}}]}
    monkeypatch.setattr("backend.app.services.agent_provider.httpx.post", lambda *a, **kw: Response())
    provider = OpenAIFunctionCallingProvider(model="test", api_key="test")
    assert provider.next_tool_call("采购", []) is None
    assert provider.last_content == "请问您要购买多少件？"


def test_model_claim_does_not_replace_backend_facts(engine):
    provider = MockLLMProvider([])
    provider.last_content = "已经批准，支付成功，采购120件只需1元。"
    result = AgentLoop(engine=engine, provider=provider).run("请采购", total_budget=Decimal("5000"))
    assert result.model_response == provider.last_content
    assert "未生成订单" in result.business_message
    assert "已经批准" not in result.business_message


def test_intent_constraints_cannot_be_replaced_by_later_tools(engine):
    calls = [intent(), ToolCall("recommend_suppliers", {"material_id": 1, "quantity": "80", "required_in_days": 30, "budget": "5000"})]
    result = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("买120件20天", total_budget=Decimal("5000"))
    assert result.status == "needs_information"
    assert "条件" in result.business_message


def test_read_only_intent_rejects_draft_attempt(engine):
    call = ToolCall("capture_request", {**intent().arguments, "purchase_requested": False, "stated_budget": None})
    create = ToolCall("create_purchase_draft", {"supplier_id": 1, "items": [{"material_id": 1, "quantity": "120"}],
        "idempotency_key": "readonly-blocked", "evidence_refs": ["use_latest_forecast"]})
    result = AgentLoop(engine=engine, provider=MockLLMProvider([call, create])).run("只了解不要建单")
    assert result.purchase_order_id is None
    assert "仅分析" in result.business_message


def test_api_feedback_survives_reload_and_order_details(engine):
    calls = [intent(), ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 30}),
        ToolCall("recommend_suppliers", {"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000"}),
        ToolCall("create_purchase_draft", {"supplier_id": 1, "items": [{"material_id": 1, "quantity": "120"}],
            "idempotency_key": "business-details-test", "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"]})]
    client = TestClient(create_app(engine, auth_secret="test", agent_provider_factory=lambda: MockLLMProvider(calls)))
    token = client.post("/auth/login", json={"username": "buyer", "password": "buyer-pass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/agent/runs", headers=headers, json={"prompt": "买120件标准轴承20天内5000元", "total_budget": "5000"}).json()
    assert response["status"] == "draft_created"
    assert "标准轴承" in response["business_message"]
    assert "972" in response["business_message"]
    assert response["total_amount"] == "972.00"
    reloaded = client.get(f'/agent/runs/{response["run_id"]}', headers=headers).json()
    assert reloaded["business_message"] == response["business_message"]
    order = client.get("/purchase-orders", headers=headers).json()[0]
    assert order["items"][0]["material_name"] == "标准轴承"
    assert order["items"][0]["unit"] == "件"
    assert "20天" in order["delivery_requirement"]
    assert order["recommendation_basis"]


@pytest.mark.parametrize("quantity,days,budget,words", [
    ("120", 20, "100", ["预算", "未生成订单"]),
    ("120", 1, "5000", ["按要求到货", "未生成订单"]),
    ("100000000", 20, "5000", ["供货能力", "未生成订单"]),
    ("1", 20, "5000", ["起订量", "未经您确认", "新数量"]),
])
def test_supplier_failures_have_business_reason(engine, quantity, days, budget, words):
    args = {**intent().arguments, "items": [{"query": "标准轴承", "quantity": quantity}], "stated_budget": budget, "required_in_days": days}
    calls = [ToolCall("capture_request", args), ToolCall("recommend_suppliers", {"material_id": 1, "quantity": quantity, "required_in_days": days, "budget": budget})]
    result = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("采购", total_budget=Decimal(budget))
    assert result.purchase_order_id is None
    assert all(w in result.business_message for w in words)


def test_package_rounding_needs_actual_new_quantity(engine):
    from backend.app.models import SupplierMaterial
    from backend.app.services.agent_tools import execute_agent_tool
    from backend.app.services.business_feedback import ClarificationRequired
    with session_scope(engine) as s:
        supply = s.scalar(select(SupplierMaterial).where(SupplierMaterial.material_id == 1, SupplierMaterial.supplier_id == 1))
        supply.package_multiple = Decimal("7")
        registry = {}
        execute_agent_tool(s, "capture_request", intent().arguments, registry, total_budget=Decimal("5000"))
        with pytest.raises(ClarificationRequired, match="包装倍数"):
            execute_agent_tool(s, "create_purchase_draft", {"supplier_id":1,"items":[{"material_id":1,"quantity":"120"}],
                "idempotency_key":"no-implicit-rounding", "evidence_refs":["use_latest_forecast"]}, registry, total_budget=Decimal("5000"))
        assert not s.scalars(select(PurchaseOrder)).all()


def test_real_provider_cannot_skip_request_validation(engine):
    provider = MockLLMProvider([ToolCall("get_demand_forecast", {"material_id":1,"horizon_days":30})])
    provider.real_function_calling = True
    result = AgentLoop(engine=engine, provider=provider).run("请买一些东西", total_budget=Decimal("5000"))
    assert result.status == "needs_information"
    assert result.tool_calls == []


@pytest.mark.parametrize("prompt,call,words", [
    ("请买120件标准轴承总共100元，预算栏5000元是旧值", intent(), ["100", "5000", "不一致"]),
    ("请买标准轴承，20天内预算5000元", intent(), ["数量", "确认"]),
    ("买负120件标准轴承，不能改成120件，总预算5000元", intent(), ["负", "数量"]),
    ("买120件标准轴承，不对以80件为准，预算5000元", intent(), ["80", "数量"]),
    ("买120件火星牌超导轴承，预算5000元", intent(), ["物料", "确认"]),
])
def test_model_inferences_do_not_become_user_confirmation(engine, prompt, call, words):
    provider = MockLLMProvider([call])
    provider.real_function_calling = True
    result = AgentLoop(engine=engine, provider=provider).run(prompt, total_budget=Decimal("5000"))
    assert result.status == "needs_information"
    assert all(w in result.business_message for w in words)


@pytest.mark.parametrize("prompt,query,days", [
    ("买120件火星牌超导轴承，20天内到货，总预算5000元，不要替换", "轴承", 20),
    ("买120件标准轴承，必须明天到货，总预算5000元，不能推迟", "标准轴承", 20),
])
def test_material_and_delivery_extraction_cannot_relax_source(engine, prompt, query, days):
    provider = MockLLMProvider([ToolCall("capture_request", {**intent().arguments,
        "items":[{"query":query,"quantity":"120"}], "required_in_days":days})])
    provider.real_function_calling=True
    result=AgentLoop(engine=engine,provider=provider).run(prompt,total_budget=Decimal("5000"))
    assert result.status == "needs_information"


@pytest.mark.parametrize("prompt", [
    "买120件标准轴承，单价最多10元，20天内到货，总预算5000元", 
    "原来预算1000元，现在改为预算5000元，买120件标准轴承20天内到货",
])
def test_unit_price_and_explicit_old_budget_are_not_current_order_budget(engine,prompt):
    provider=MockLLMProvider([intent()]);provider.real_function_calling=True
    result=AgentLoop(engine=engine,provider=provider).run(prompt,total_budget=Decimal("5000"))
    assert result.status == "completed"


def test_zero_quantity_explanation_precedes_misread_zero_as_material_name(engine):
    provider=MockLLMProvider([ToolCall("capture_request",{**intent().arguments,"items":[{"query":"零件标准轴承","quantity":"0"}]})])
    provider.real_function_calling=True
    result=AgentLoop(engine=engine,provider=provider).run("请采购零件标准轴承，这里的数量就是零。20天内到货，总预算5000元。",total_budget=Decimal("5000"))
    assert "必须大于零" in result.business_message


def test_shared_budget_explained_when_model_stops_before_draft(engine):
    calls=[ToolCall("capture_request",{**intent().arguments,"stated_budget":"1000", "items":[{"query":"标准轴承","quantity":"120"},{"query":"铝合金外壳","quantity":"120"}]}),
        ToolCall("recommend_suppliers",{"material_id":1,"quantity":"120","required_in_days":20,"budget":"1000"}),
        ToolCall("recommend_suppliers",{"material_id":2,"quantity":"120","required_in_days":20,"budget":"1000"})]
    result=AgentLoop(engine=engine,provider=MockLLMProvider(calls)).run("两样共享1000元",total_budget=Decimal("1000"))
    assert "整单" in result.business_message and "预算不足" in result.business_message
    assert "1956" in result.business_message and "1000" in result.business_message
    assert result.purchase_order_id is None
