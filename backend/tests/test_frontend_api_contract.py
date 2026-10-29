from fastapi.testclient import TestClient

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.main import create_app
from backend.app.services.agent_provider import MockLLMProvider, ToolCall
from backend.app.services.seed import seed_demo_data


def test_frontend_contract_runs_agent_traces_and_approval_loop():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)

    provider = MockLLMProvider(
        [
            ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 30}),
            ToolCall(
                "recommend_suppliers",
                {"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000.00"},
            ),
            ToolCall(
                "create_purchase_draft",
                {
                    "supplier_id": 1,
                    "items": [{"material_id": 1, "quantity": "120"}],
                    "idempotency_key": "frontend-agent-draft",
                    "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"],
                },
            ),
        ]
    )
    client = TestClient(create_app(engine, auth_secret="test-secret", agent_provider_factory=lambda: provider))
    buyer_token = client.post("/auth/login", json={"username": "buyer", "password": "buyer-pass"}).json()["access_token"]

    agent_run = client.post(
        "/agent/runs",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"total_budget": "5000", "prompt": "为 MAT-001 生成采购草稿"},
    )

    assert agent_run.status_code == 200
    assert agent_run.json()["status"] == "draft_created"
    order_id = agent_run.json()["purchase_order_id"]
    run_id = agent_run.json()["run_id"]

    traces = client.get(f"/agent/runs/{run_id}/traces", headers={"Authorization": f"Bearer {buyer_token}"})
    assert traces.status_code == 200
    assert [trace["tool_name"] for trace in traces.json()] == [
        "get_demand_forecast",
        "recommend_suppliers",
        "create_purchase_draft",
    ]
    assert traces.json()[0]["output"]["config_version"] == "forecast_strategy_v1_20261011"

    pending = client.post(
        f"/purchase-orders/{order_id}/submit",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert pending.status_code == 200
    assert pending.json()["status"] == "pending_approval"

    approver_token = client.post(
        "/auth/login", json={"username": "approver", "password": "approver-pass"}
    ).json()["access_token"]
    approved = client.post(
        f"/purchase-orders/{order_id}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"expected_order_version": pending.json()["version"], "idempotency_key": "frontend-approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["formal_order_number"] == f"PO-{order_id:06d}"

    orders = client.get("/purchase-orders", headers={"Authorization": f"Bearer {approver_token}"})
    assert orders.status_code == 200
    assert orders.json()[0]["status"] == "approved"
    assert orders.json()[0]["formal_order_number"] == f"PO-{order_id:06d}"
    assert orders.json()[0]["supplier_name"]


def test_frontend_contract_exposes_recent_demand_history_for_analysis_chart():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    client = TestClient(create_app(engine, auth_secret="test-secret"))
    token = client.post("/auth/login", json={"username": "buyer", "password": "buyer-pass"}).json()["access_token"]

    response = client.get("/demand-history/1?days=14", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    points = response.json()
    assert len(points) == 14
    assert set(points[0]) == {"date", "quantity"}


def test_read_apis_scope_runs_traces_and_orders_by_buyer_owner_and_approver_need():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)

    provider = MockLLMProvider(
        [
            ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 30}),
            ToolCall(
                "recommend_suppliers",
                {"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000.00"},
            ),
            ToolCall(
                "create_purchase_draft",
                {
                    "supplier_id": 1,
                    "items": [{"material_id": 1, "quantity": "120"}],
                    "idempotency_key": "buyer-owned-agent-draft",
                    "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"],
                },
            ),
        ]
    )
    client = TestClient(
        create_app(
            engine,
            auth_secret="test-secret",
            allow_header_auth=True,
            agent_provider_factory=lambda: provider,
        )
    )

    created = client.post(
        "/agent/runs",
        headers={"X-User-Id": "buyer-1", "X-User-Role": "buyer"},
        json={"total_budget": "5000", "prompt": "buyer 1 creates a draft"},
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    order_id = created.json()["purchase_order_id"]

    buyer_2_runs = client.get("/agent/runs", headers={"X-User-Id": "buyer-2", "X-User-Role": "buyer"})
    buyer_2_orders = client.get("/purchase-orders", headers={"X-User-Id": "buyer-2", "X-User-Role": "buyer"})
    buyer_2_run_detail = client.get(f"/agent/runs/{run_id}", headers={"X-User-Id": "buyer-2", "X-User-Role": "buyer"})
    buyer_2_traces = client.get(
        f"/agent/runs/{run_id}/traces",
        headers={"X-User-Id": "buyer-2", "X-User-Role": "buyer"},
    )

    assert buyer_2_runs.status_code == 200
    assert buyer_2_runs.json() == []
    assert buyer_2_orders.status_code == 200
    assert buyer_2_orders.json() == []
    assert buyer_2_run_detail.status_code == 404
    assert buyer_2_traces.status_code == 404

    pending = client.post(
        f"/purchase-orders/{order_id}/submit",
        headers={"X-User-Id": "buyer-1", "X-User-Role": "buyer"},
    )
    assert pending.status_code == 200

    approver_orders = client.get("/purchase-orders", headers={"X-User-Id": "approver-1", "X-User-Role": "approver"})
    approver_traces = client.get(
        f"/agent/runs/{run_id}/traces",
        headers={"X-User-Id": "approver-1", "X-User-Role": "approver"},
    )

    assert [order["id"] for order in approver_orders.json()] == [order_id]
    assert approver_traces.status_code == 200


def test_buyer_can_edit_draft_quantities_then_submit_and_approve():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)

    client = TestClient(create_app(engine, auth_secret="test-secret"))
    buyer = client.post("/auth/login", json={"username": "buyer", "password": "buyer-pass"})
    buyer_headers = {"Authorization": f"Bearer {buyer.json()['access_token']}"}

    forecast = client.post(
        "/forecasts",
        headers=buyer_headers,
        json={"material_id": 1, "horizon_days": 30},
    ).json()
    recommendation = client.post(
        "/recommendations",
        headers=buyer_headers,
        json={"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000.00"},
    ).json()
    draft = client.post(
        "/purchase-drafts",
        headers=buyer_headers,
        json={
            "supplier_id": 1,
            "items": [{"material_id": 1, "quantity": "120"}],
            "idempotency_key": "manual-edit-contract-001",
            "evidence_refs": [forecast["evidence_ref"], recommendation["evidence_ref"]],
            "total_budget": "5000.00",
        },
    )
    assert draft.status_code == 200, draft.text
    order_id = draft.json()["id"]
    listed = client.get("/purchase-orders", headers=buyer_headers).json()
    order = next(item for item in listed if item["id"] == order_id)
    assert order["items"][0]["material_name"] == "标准轴承"
    assert order["total_budget"] == "5000.00"

    edited = client.patch(
        f"/purchase-orders/{order['id']}/draft",
        headers=buyer_headers,
        json={
            "expected_order_version": order["version"],
            "items": [{"material_id": 1, "quantity": "130"}],
            "total_budget": "5000.00",
        },
    )
    assert edited.status_code == 200, edited.text
    updated = edited.json()
    assert updated["version"] == order["version"] + 1
    assert updated["items"][0]["quantity"] == "130.0"
    assert updated["items"][0]["material_name"] == "标准轴承"
    assert updated["total_amount"] == "1053.00"
    assert updated["total_budget"] == "5000.00"

    stale = client.patch(
        f"/purchase-orders/{order['id']}/draft",
        headers=buyer_headers,
        json={
            "expected_order_version": order["version"],
            "items": [{"material_id": 1, "quantity": "130"}],
            "total_budget": "5000.00",
        },
    )
    assert stale.status_code == 409

    pending = client.post(f"/purchase-orders/{order['id']}/submit", headers=buyer_headers)
    assert pending.status_code == 200
    approver = client.post("/auth/login", json={"username": "approver", "password": "approver-pass"})
    approver_headers = {"Authorization": f"Bearer {approver.json()['access_token']}"}
    approved = client.post(
        f"/purchase-orders/{order['id']}/approve",
        headers=approver_headers,
        json={"expected_order_version": pending.json()["version"], "idempotency_key": "manual-edit-approve-001"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
