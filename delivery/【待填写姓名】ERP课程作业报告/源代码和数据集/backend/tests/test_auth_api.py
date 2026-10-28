from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.main import create_app
from backend.app.services.auth import issue_token
from backend.app.services.seed import seed_demo_data


def _client() -> TestClient:
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    return TestClient(create_app(engine, auth_secret="test-secret"))


def _draft(client: TestClient) -> dict:
    forecast = client.post("/forecasts", json={"material_id": 1, "horizon_days": 30})
    recommendations = client.post(
        "/recommendations",
        json={"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000.00"},
    )
    return client.post(
        "/purchase-drafts",
        json={
            "supplier_id": 1,
            "items": [{"material_id": 1, "quantity": "120"}],
            "idempotency_key": "auth-api-draft-001",
            "evidence_refs": [forecast.json()["evidence_ref"], recommendations.json()["evidence_ref"]],
        },
    ).json()


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_approval_requires_login_token_by_default_and_ignores_forged_role_headers():
    client = _client()
    draft = _draft(client)

    no_auth = client.post(f"/purchase-orders/{draft['id']}/submit")
    forged_header = client.post(
        f"/purchase-orders/{draft['id']}/submit",
        headers={"X-User-Id": "buyer-1", "X-User-Role": "buyer"},
    )
    token = _login(client, "buyer", "buyer-pass")
    authorized = client.post(
        f"/purchase-orders/{draft['id']}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert no_auth.status_code == 401
    assert no_auth.json()["detail"] == "authentication_required"
    assert forged_header.status_code == 401
    assert forged_header.json()["detail"] == "authentication_required"
    assert authorized.status_code == 200
    assert authorized.json()["status"] == "pending_approval"


def test_buyer_token_cannot_approve_even_with_forged_approver_headers():
    client = _client()
    draft = _draft(client)
    buyer_token = _login(client, "buyer", "buyer-pass")
    pending = client.post(
        f"/purchase-orders/{draft['id']}/submit",
        headers={"Authorization": f"Bearer {buyer_token}"},
    ).json()

    response = client.post(
        f"/purchase-orders/{draft['id']}/approve",
        headers={
            "Authorization": f"Bearer {buyer_token}",
            "X-User-Id": "approver-1",
            "X-User-Role": "approver",
        },
        json={"expected_order_version": pending["version"], "idempotency_key": "buyer-token-approve"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "approver_role_required"


def test_invalid_and_expired_tokens_are_rejected():
    client = _client()
    draft = _draft(client)
    expired = issue_token(
        username="buyer",
        user_id="buyer-1",
        role="buyer",
        secret="test-secret",
        now=datetime.now(UTC) - timedelta(hours=2),
        ttl_seconds=60,
    )

    invalid = client.post(
        f"/purchase-orders/{draft['id']}/submit",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    expired_response = client.post(
        f"/purchase-orders/{draft['id']}/submit",
        headers={"Authorization": f"Bearer {expired}"},
    )

    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "invalid_token"
    assert expired_response.status_code == 401
    assert expired_response.json()["detail"] == "token_expired"


def test_header_auth_is_available_only_when_test_mode_is_explicitly_enabled():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    client = TestClient(create_app(engine, auth_secret="test-secret", allow_header_auth=True))
    draft = _draft(client)

    response = client.post(
        f"/purchase-orders/{draft['id']}/submit",
        headers={"X-User-Id": "buyer-1", "X-User-Role": "buyer"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"
