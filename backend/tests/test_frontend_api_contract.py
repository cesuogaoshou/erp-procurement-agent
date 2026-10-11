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
                    "evidence_refs": ["use_latest_forecast"],
                },
            ),
        ]
    )
    client = TestClient(create_app(engine, auth_secret="test-secret", agent_provider_factory=lambda: provider))
    buyer_token = client.post("/auth/login", json={"username": "buyer", "password": "buyer-pass"}).json()["access_token"]

    agent_run = client.post(
        "/agent/runs",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"prompt": "为 MAT-001 生成采购草稿"},
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
