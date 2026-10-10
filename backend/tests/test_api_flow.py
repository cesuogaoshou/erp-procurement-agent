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
            "evidence_refs": ["recommendation:api-flow"],
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


class DecimalString:
    def __init__(self, value):
        self.value = float(value)

    def __ge__(self, other):
        return self.value >= other.value
