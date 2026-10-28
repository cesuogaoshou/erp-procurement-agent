from fastapi.testclient import TestClient

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.main import create_app
from backend.app.services.seed import seed_demo_data


def test_api_exposes_inventory_forecast_and_recommendations():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)

    app = create_app(engine)
    client = TestClient(app)

    materials = client.get("/materials").json()
    material_id = materials[0]["id"]

    inventory = client.get(f"/inventory/{material_id}")
    forecast = client.post("/forecasts", json={"material_id": material_id, "horizon_days": 30})
    recommendations = client.post(
        "/recommendations",
        json={
            "material_id": material_id,
            "quantity": "120",
            "required_in_days": 20,
            "budget": "5000.00",
        },
    )
    draft = client.post(
        "/purchase-drafts",
        json={
            "supplier_id": 1,
            "items": [{"material_id": material_id, "quantity": "120"}],
            "idempotency_key": "api-draft-key-001",
            "evidence_refs": [forecast.json()["evidence_ref"], recommendations.json()["evidence_ref"]],
        },
    )

    assert inventory.status_code == 200
    assert forecast.status_code == 200
    assert recommendations.status_code == 200
    assert draft.status_code == 200
    assert DecimalString(forecast.json()["shortage_quantity"]) >= DecimalString("0")
    assert len(recommendations.json()["recommendations"]) >= 1
    assert "score_components" in recommendations.json()["recommendations"][0]["evidence"]
    assert draft.json()["status"] == "draft"
    assert draft.json()["total_amount"] == "972.00"


def test_api_approval_uses_auth_headers_not_body_actor_claims():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)

    app = create_app(engine, auth_secret="test-secret", allow_header_auth=True)
    client = TestClient(app)
    forecast = client.post("/forecasts", json={"material_id": 1, "horizon_days": 30})
    recommendations = client.post(
        "/recommendations",
        json={"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000.00"},
    )

    draft = client.post(
        "/purchase-drafts",
        json={
            "supplier_id": 1,
            "items": [{"material_id": 1, "quantity": "120"}],
            "idempotency_key": "api-approval-draft-001",
            "evidence_refs": [forecast.json()["evidence_ref"], recommendations.json()["evidence_ref"]],
        },
    ).json()
    pending = client.post(
        f"/purchase-orders/{draft['id']}/submit",
        headers={"X-User-Id": "buyer-1", "X-User-Role": "buyer"},
    )

    unauthorized = client.post(
        f"/purchase-orders/{draft['id']}/approve",
        headers={"X-User-Id": "buyer-1", "X-User-Role": "buyer"},
        json={
            "expected_order_version": pending.json()["version"],
            "idempotency_key": "api-approval-body-ignored",
            "actor_user_id": "approver-1",
            "actor_role": "approver",
        },
    )
    approved = client.post(
        f"/purchase-orders/{draft['id']}/approve",
        headers={"X-User-Id": "approver-1", "X-User-Role": "approver"},
        json={
            "expected_order_version": pending.json()["version"],
            "idempotency_key": "api-approval-success",
        },
    )

    assert pending.status_code == 200
    assert pending.json()["status"] == "pending_approval"
    assert unauthorized.status_code == 403
    assert unauthorized.json()["detail"] == "approver_role_required"
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["formal_order_number"] == f"PO-{draft['id']:06d}"


class DecimalString:
    def __init__(self, value):
        self.value = float(value)

    def __ge__(self, other):
        return self.value >= other.value
