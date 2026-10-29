"""Regressions from the preserved 2026-10-29 extreme acceptance."""
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.session import create_session_factory, create_sqlite_engine, session_scope
from backend.app.main import create_app
from backend.app.models import AgentRun, PurchaseOrder, SupplierMaterial, ToolTrace
from backend.app.services.agent_loop import AgentLoop, _latest_shortage_is_zero
from backend.app.services.agent_provider import MockLLMProvider, ToolCall
from backend.app.services.agent_tools import execute_agent_tool
from backend.app.services.approvals import AuthContext, ApprovalActionInput, approve_order, submit_for_approval
from backend.app.services.forecasting import get_demand_forecast
from backend.app.services.purchase_drafts import DraftItemInput, PurchaseDraftInput, create_purchase_draft
from backend.app.services.seed import seed_demo_data


@pytest.fixture
def engine():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    yield engine
    engine.dispose()


def refs(session, material=1, quantity="120", budget="5000"):
    return [get_demand_forecast(session, material_id=material, horizon_days=30)["evidence_ref"],
            f"recommendation:{material}:1:{quantity}:20:{budget}"]


def request(session, quantities, quantity="120", **kwargs):
    return PurchaseDraftInput(supplier_id=1,
        items=[DraftItemInput(1, Decimal(q)) for q in quantities],
        idempotency_key="extreme-regression", evidence_refs=refs(session, quantity=quantity), total_budget=Decimal("5000"), **kwargs)


def test_duplicate_lines_cannot_exceed_aggregate_shortage(engine):
    with session_scope(engine) as session:
        with pytest.raises(ValueError, match="quantity_exceeds_forecast_shortage"):
            create_purchase_draft(session, request(session, ["120"] * 4))


def test_duplicate_lines_round_once_and_require_aggregate_recommendation(engine):
    with session_scope(engine) as session:
        relation = session.scalar(select(SupplierMaterial).where(SupplierMaterial.supplier_id == 1, SupplierMaterial.material_id == 1))
        relation.moq, relation.package_multiple = Decimal("25"), Decimal("10")
        order = create_purchase_draft(session, request(session, ["11", "10"], quantity="30"))
        assert len(order.items) == 1
        assert order.items[0].quantity == Decimal("30")


def test_rounded_aggregate_cannot_exceed_capacity(engine):
    with session_scope(engine) as session:
        relation = session.scalar(select(SupplierMaterial).where(SupplierMaterial.supplier_id == 1, SupplierMaterial.material_id == 1))
        relation.capacity, relation.package_multiple = Decimal("245"), Decimal("100")
        with pytest.raises(ValueError, match="capacity_below_quantity"):
            create_purchase_draft(session, request(session, ["120", "120"], quantity="240"))


def test_approval_rechecks_aggregate_capacity(engine):
    with session_scope(engine) as session:
        order = create_purchase_draft(session, request(session, ["120"]))
        # Simulate a pre-fix persisted order with duplicated valid individual rows.
        from backend.app.models import PurchaseOrderItem
        for _ in range(3):
            order.items.append(PurchaseOrderItem(material_id=1, quantity=Decimal("120"), unit_price=Decimal("8.10"), line_amount=Decimal("972")))
        order.total_amount = Decimal("3888")
        submit_for_approval(session, order.id, AuthContext("buyer-1", "buyer"))
        with pytest.raises(ValueError, match="quantity_exceeds_forecast_shortage|capacity_below_quantity"):
            approve_order(session, order.id, AuthContext("approver-1", "approver"), ApprovalActionInput(2, "extreme-approve"))


def test_shared_budget_is_checked_against_whole_order(engine):
    client = TestClient(create_app(engine, allow_header_auth=True, auth_secret="test"))
    with session_scope(engine) as session:
        evidence = refs(session, 1, budget="1000") + refs(session, 2, budget="1000")
    payload = {"supplier_id": 1, "items": [{"material_id": m, "quantity": "120"} for m in [1, 2]],
               "evidence_refs": evidence, "idempotency_key": "extreme-budget", "total_budget": "1000"}
    response = client.post("/purchase-drafts", json=payload, headers={"X-User-Id": "buyer-1", "X-User-Role": "buyer"})
    assert response.status_code == 409
    assert response.json()["detail"] == "order_budget_exceeded"


@pytest.mark.parametrize("registry,expected", [({}, False), ({"recommendation:1": {}}, False),
    ({"forecast:1": {"shortage_quantity": "0"}, "recommendation:1": {}}, True),
    ({"forecast:1": {"shortage_quantity": "12"}, "recommendation:1": {}}, False)])
def test_shortage_lookup_uses_evidence_type(registry, expected):
    assert _latest_shortage_is_zero(registry) is expected


def analysis_calls():
    return [ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 30}),
            ToolCall("recommend_suppliers", {"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000"})]


def test_read_only_analysis_completes_and_persists_trace(engine):
    result = AgentLoop(engine=engine, provider=MockLLMProvider(analysis_calls())).run("仅分析需求、缺口并推荐供应商，不创建草稿")
    assert result.status == "completed"
    with session_scope(engine) as session:
        assert not session.scalars(select(PurchaseOrder)).all()
        assert len(session.scalars(select(ToolTrace).where(ToolTrace.run_id == result.run_id)).all()) == 2


def test_unexpected_provider_exception_preserves_failed_run_and_trace(engine):
    class ExplodingProvider(MockLLMProvider):
        def next_tool_call(self, prompt, observations):
            if observations:
                raise RuntimeError("unexpected-provider-bug")
            return ToolCall("get_inventory", {"material_id": 1})
    result = AgentLoop(engine=engine, provider=ExplodingProvider([])).run("分析")
    assert result.status == "failed"
    with session_scope(engine) as session:
        assert session.get(AgentRun, result.run_id).status == "failed"
        assert len(session.scalars(select(ToolTrace).where(ToolTrace.run_id == result.run_id)).all()) == 1


def test_unexpected_loop_exception_is_controlled_and_keeps_trace(engine, monkeypatch):
    import backend.app.services.agent_loop as module
    def broken_status(*args):
        raise RuntimeError("unexpected-status-classifier")
    monkeypatch.setattr(module, "_special_tool_status", broken_status)
    result = AgentLoop(engine=engine, provider=MockLLMProvider([ToolCall("get_inventory", {"material_id": 1})])).run("分析")
    assert result.status == "failed"
    with session_scope(engine) as session:
        assert session.get(AgentRun, result.run_id).status == "failed"
        assert len(session.scalars(select(ToolTrace).where(ToolTrace.run_id == result.run_id)).all()) == 1


def test_tool_exception_rolls_back_partial_order_and_preserves_traces(engine, monkeypatch):
    import backend.app.services.agent_loop as module
    execute = module.execute_agent_tool
    def fail_after_insert(session, name, arguments, *args, **kwargs):
        if name == "get_inventory":
            session.add(PurchaseOrder(supplier_id=1, status="draft", idempotency_key="partial-business", total_amount=Decimal("1"), evidence_refs_json="[]"))
            session.flush()
            raise RuntimeError("forced-after-business-flush")
        return execute(session, name, arguments, *args, **kwargs)
    monkeypatch.setattr(module, "execute_agent_tool", fail_after_insert)
    result = AgentLoop(engine=engine, provider=MockLLMProvider([ToolCall("get_inventory", {"material_id": 1})])).run("分析")
    assert result.status == "tool_error"
    with session_scope(engine) as session:
        assert session.scalars(select(PurchaseOrder)).all() == []
        assert session.get(AgentRun, result.run_id).status == "tool_error"
        assert session.scalar(select(ToolTrace).where(ToolTrace.run_id == result.run_id)).status == "error"


@pytest.mark.parametrize("name,args", [
    ("get_demand_forecast", {"material_id": 1, "horizon_days": 181}),
    ("get_demand_forecast", {"material_id": 1, "horizon_days": True}),
    ("get_inventory", {"material_id": -1}), ("list_materials", {"extra": 1}),
    ("resolve_material", {"query": ""}), ("resolve_material", {"query": "x" * 121}),
    ("get_inventory", []), ("get_inventory", {"material_id": "abc"}),
    ("create_purchase_draft", {"supplier_id": 1, "items": {}, "idempotency_key": "abcdefgh", "evidence_refs": ["x"]}),
] + [("recommend_suppliers", {"material_id": 1, "quantity": q, "required_in_days": 20})
     for q in ["-120", "NaN", "Infinity", "-Infinity", {}, []]]
  + [("recommend_suppliers", {"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": b})
     for b in ["NaN", "Infinity", "0", "-1"]])
def test_tool_runtime_rejects_invalid_arguments(engine, name, args):
    with session_scope(engine) as session:
        with pytest.raises(ValueError, match="tool_parameter_error"):
            execute_agent_tool(session, name, args, {})


def test_nonfinite_numeric_tool_input_keeps_http_trace_queryable(engine):
    provider = lambda: MockLLMProvider([ToolCall("recommend_suppliers", {
        "material_id": 1, "quantity": float("nan"), "required_in_days": 20})])
    client = TestClient(create_app(engine, allow_header_auth=True, auth_secret="test", agent_provider_factory=provider))
    headers = {"X-User-Id": "buyer-1", "X-User-Role": "buyer"}
    run = client.post("/agent/runs", headers=headers, json={"prompt": "invalid numeric input", "total_budget": "5000"})
    assert run.status_code == 200 and run.json()["status"] == "tool_error"
    trace = client.get(f'/agent/runs/{run.json()["run_id"]}/traces', headers=headers)
    assert trace.status_code == 200
    assert str(trace.json()[0]["arguments"]["quantity"]).lower() == "nan"


def test_approval_enforces_persisted_whole_order_budget(engine):
    with session_scope(engine) as session:
        order = create_purchase_draft(session, request(session, ["120"]))
        order.total_budget = Decimal("100")  # Legacy/corrupted draft snapshot probe.
        submit_for_approval(session, order.id, AuthContext("buyer-1", "buyer"))
        with pytest.raises(ValueError, match="order_budget_exceeded"):
            approve_order(session, order.id, AuthContext("approver-1", "approver"), ApprovalActionInput(2, "budget-approval"))
        assert order.status == "pending_approval"


def test_unknown_historical_budget_blocks_approval_without_fabricating_value(engine):
    with session_scope(engine) as session:
        order = create_purchase_draft(session, request(session, ["120"]))
        order.total_budget = None
        submit_for_approval(session, order.id, AuthContext("buyer-1", "buyer"))
        with pytest.raises(ValueError, match="budget_confirmation_required"):
            approve_order(session, order.id, AuthContext("approver-1", "approver"), ApprovalActionInput(2, "unknown-budget-approval"))
        assert order.total_budget is None and order.status == "pending_approval"


def test_model_cannot_replace_or_remove_confirmed_budget(engine):
    calls = analysis_calls() + [ToolCall("create_purchase_draft", {
        "supplier_id": 1, "items": [{"material_id": 1, "quantity": "120"}],
        "idempotency_key": "model-budget-overwrite", "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"],
        "total_budget": "999999"})]
    result = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("采购", total_budget=Decimal("5000"))
    assert result.status == "tool_error" and "tool_parameter_error" in result.error
    with session_scope(engine) as session:
        assert session.get(AgentRun, result.run_id).total_budget == Decimal("5000")
        assert session.scalars(select(PurchaseOrder)).all() == []


def test_new_draft_requires_structured_budget_confirmation(engine):
    client = TestClient(create_app(engine, allow_header_auth=True, auth_secret="test"))
    with session_scope(engine) as session:
        evidence = refs(session)
    response = client.post("/purchase-drafts", headers={"X-User-Id": "buyer-1", "X-User-Role": "buyer"}, json={
        "supplier_id": 1, "items": [{"material_id": 1, "quantity": "120"}],
        "idempotency_key": "missing-budget", "evidence_refs": evidence})
    assert response.status_code == 422


def test_agent_without_confirmed_budget_cannot_write(engine):
    calls = analysis_calls() + [ToolCall("create_purchase_draft", {
        "supplier_id": 1, "items": [{"material_id": 1, "quantity": "120"}],
        "idempotency_key": "no-confirmed-budget", "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"]})]
    result = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("预算5000，请采购")
    assert result.status == "tool_error" and result.error == "budget_confirmation_required"
    with session_scope(engine) as session:
        assert session.scalars(select(PurchaseOrder)).all() == []


def test_idempotency_normalizes_decimals_and_rejects_changed_content(engine):
    from dataclasses import replace
    with session_scope(engine) as session:
        initial = request(session, ["120.0"])
        order = create_purchase_draft(session, initial)
        equivalent = replace(initial, items=[DraftItemInput(1, Decimal("120.00"))], total_budget=Decimal("5000.00"),
                             evidence_refs=[initial.evidence_refs[0], "recommendation:1:1:120.00:20:5000.00"])
        assert create_purchase_draft(session, equivalent).id == order.id
        with pytest.raises(ValueError, match="idempotency_payload_conflict"):
            create_purchase_draft(session, replace(initial, items=[DraftItemInput(1, Decimal("100"))]))


def test_two_material_request_reuses_all_evidence_with_shared_budget(engine):
    calls = [ToolCall("list_materials", {})]
    for material in [1, 2]:
        calls += [ToolCall("get_demand_forecast", {"material_id": material, "horizon_days": 30}),
                  ToolCall("recommend_suppliers", {"material_id": material, "quantity": "120", "required_in_days": 20, "budget": "5000"})]
    calls += [ToolCall("create_purchase_draft", {"supplier_id": 1, "items": [{"material_id": m, "quantity": "120"} for m in [1, 2]],
              "idempotency_key": "two-materials-shared", "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"]})]
    result = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("标准轴承和工业皮带各120件，共享预算5000元", total_budget=Decimal("5000"))
    assert result.status == "draft_created" and len(result.tool_calls) == 6
    with session_scope(engine) as session:
        order = session.get(PurchaseOrder, result.purchase_order_id)
        assert order.total_amount == Decimal("1956") and order.total_budget == Decimal("5000")
        assert len(order.items) == 2


def test_only_order_idempotency_unique_violation_is_recoverable():
    from sqlalchemy.exc import IntegrityError
    from backend.app.services.purchase_drafts import is_idempotency_collision
    assert is_idempotency_collision(IntegrityError("", {}, Exception(1062, "Duplicate entry 'x' for key 'purchase_orders.idempotency_key'")))
    assert not is_idempotency_collision(IntegrityError("", {}, Exception(1062, "Duplicate entry 'x' for key 'purchase_orders.formal_order_number'")))
    assert not is_idempotency_collision(IntegrityError("", {}, Exception(1452, "Foreign key violation")))


def test_latest_alias_uses_latest_recommendation_for_each_material(engine):
    calls = analysis_calls() + [ToolCall("recommend_suppliers", {
        "material_id": 1, "quantity": "240", "required_in_days": 20, "budget": "5000"}),
        ToolCall("create_purchase_draft", {"supplier_id": 1, "items": [{"material_id": 1, "quantity": "240"}],
        "idempotency_key": "latest-ref-per-material", "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"]})]
    result = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("采购240件", total_budget=Decimal("5000"))
    assert result.status == "draft_created"


def test_latest_alias_uses_latest_forecast_for_each_material(engine):
    calls = [ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 10})] + analysis_calls() + [
        ToolCall("create_purchase_draft", {"supplier_id": 1, "items": [{"material_id": 1, "quantity": "120"}],
        "idempotency_key": "latest-forecast-material", "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"]})]
    result = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("采购120件", total_budget=Decimal("5000"))
    assert result.status == "draft_created"


def test_reused_forecast_becomes_latest_evidence(engine):
    calls = [ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": days}) for days in [30, 1, 30]]
    calls += analysis_calls()[1:] + [ToolCall("create_purchase_draft", {
        "supplier_id": 1, "items": [{"material_id": 1, "quantity": "120"}], "idempotency_key": "cached-latest-forecast",
        "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"]})]
    result = AgentLoop(engine=engine, provider=MockLLMProvider(calls)).run("30天采购", total_budget=Decimal("5000"))
    assert result.status == "draft_created"


@pytest.mark.parametrize("bad_ref", ["recommendation:1:1:NaN:20:5000", "recommendation:1:1:120:20:NaN",
                                    "recommendation:1:1:Infinity:20:5000", "recommendation:1:1:120:366:5000"])
def test_malformed_evidence_numeric_fields_are_controlled_value_errors(engine, bad_ref):
    from dataclasses import replace
    with session_scope(engine) as session:
        initial = request(session, ["120"])
        with pytest.raises(ValueError, match="recommendation_evidence_invalid"):
            create_purchase_draft(session, replace(initial, evidence_refs=[initial.evidence_refs[0], bad_ref]))


@pytest.mark.parametrize("bad_ref", ["recommendation:1:1:abc:20:5000", "recommendation:1:1:sNaN:20:5000", "recommendation:1:1:120:20:abc"])
def test_existing_key_malformed_evidence_is_controlled(engine, bad_ref):
    from dataclasses import replace
    with session_scope(engine) as session:
        initial = request(session, ["120"])
        create_purchase_draft(session, initial)
        with pytest.raises(ValueError, match="recommendation_evidence_invalid|idempotency_payload_conflict"):
            create_purchase_draft(session, replace(initial, evidence_refs=[initial.evidence_refs[0], bad_ref]))
