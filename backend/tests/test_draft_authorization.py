import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.main import create_app
from backend.app.models import AuditLog, PurchaseOrder
from backend.app.services.auth import DEMO_ACCOUNTS, issue_token
from backend.app.services.agent_provider import MockLLMProvider, ToolCall
from backend.app.services.seed import seed_demo_data


def _headers(user_id="buyer-1", role="buyer"):
    username = {"buyer-1": "buyer", "approver-1": "approver"}.get(user_id, user_id)
    token = issue_token(username=username, user_id=user_id, role=role, secret="test-secret")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def draft_api(monkeypatch):
    monkeypatch.setitem(DEMO_ACCOUNTS, "buyer-2", {
        "password": "test-only", "user_id": "buyer-2", "role": "buyer",
    })
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    app = create_app(engine, auth_secret="test-secret")
    with TestClient(app) as client:
        forecast = client.post("/forecasts", json={"material_id": 1, "horizon_days": 30}).json()
        recommendation = client.post("/recommendations", json={
            "material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000.00",
        }).json()
        payload = {
            "total_budget": "5000", "total_budget": "5000", "supplier_id": 1, "items": [{"material_id": 1, "quantity": "120"}],
            "idempotency_key": "owned-draft",
            "evidence_refs": [forecast["evidence_ref"], recommendation["evidence_ref"]],
        }
        yield client, engine, payload
    engine.dispose()


@pytest.mark.parametrize("headers,status", [
    ({}, 401),
    ({"X-User-Id": "buyer-1", "X-User-Role": "buyer"}, 401),
    ({"Authorization": "Bearer invalid"}, 401),
    (_headers("approver-1", "approver"), 403),
])
def test_draft_creation_requires_authenticated_buyer(draft_api, headers, status):
    client, engine, payload = draft_api
    response = client.post("/purchase-drafts", json=payload, headers=headers)
    assert response.status_code == status
    with session_scope(engine) as session:
        assert session.scalars(select(PurchaseOrder)).all() == []
        assert session.scalars(select(AuditLog)).all() == []


def test_buyer_can_query_submit_and_retry_without_duplicate_creation_audit(draft_api):
    client, engine, payload = draft_api
    created = client.post("/purchase-drafts", json=payload, headers=_headers())
    assert created.status_code == 200
    order_id = created.json()["id"]
    orders = client.get("/purchase-orders", headers=_headers())
    assert [order["id"] for order in orders.json()] == [order_id]
    duplicate = client.post("/purchase-drafts", json=payload, headers=_headers())
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == order_id
    pending = client.post(f"/purchase-orders/{order_id}/submit", headers=_headers())
    assert pending.status_code == 200
    assert pending.json()["status"] == "pending_approval"
    assert client.post(f"/purchase-orders/{order_id}/submit", headers=_headers()).status_code == 200
    duplicate_pending = client.post("/purchase-drafts", json=payload, headers=_headers())
    assert duplicate_pending.status_code == 200
    assert duplicate_pending.json()["id"] == order_id
    with session_scope(engine) as session:
        assert len(session.scalars(select(PurchaseOrder)).all()) == 1
        audits = session.scalars(select(AuditLog).order_by(AuditLog.id)).all()
        assert [audit.action for audit in audits] == ["created_draft", "submitted_for_approval"]
        assert audits[0].actor_user_id == "buyer-1"
        assert audits[0].actor_role == "buyer"


@pytest.mark.parametrize("submitted", [False, True])
def test_other_buyer_cannot_read_submit_or_reuse_idempotency_key(draft_api, submitted):
    client, engine, payload = draft_api
    created = client.post("/purchase-drafts", json=payload, headers=_headers())
    assert created.status_code == 200
    order_id = created.json()["id"]
    if submitted:
        assert client.post(f"/purchase-orders/{order_id}/submit", headers=_headers()).status_code == 200
    other = _headers("buyer-2")
    assert client.get("/purchase-orders", headers=other).json() == []
    replay = client.post("/purchase-drafts", json=payload, headers=other)
    assert replay.status_code == 403
    assert "id" not in replay.json()
    assert client.post(f"/purchase-orders/{order_id}/submit", headers=other).status_code == 403
    with session_scope(engine) as session:
        assert len(session.scalars(select(PurchaseOrder)).all()) == 1
        order = session.get(PurchaseOrder, order_id)
        assert order.status == ("pending_approval" if submitted else "draft")
        assert order.version == (2 if submitted else 1)
        audits = session.scalars(select(AuditLog).where(AuditLog.action == "created_draft")).all()
        assert len(audits) == 1
        assert audits[0].actor_user_id == "buyer-1"


def test_creation_and_creator_audit_roll_back_together(draft_api):
    client, engine, payload = draft_api

    def fail_audit(mapper, connection, target):
        if target.action == "created_draft":
            raise RuntimeError("forced_creator_audit_failure")

    event.listen(AuditLog, "before_insert", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="forced_creator_audit_failure"):
            client.post("/purchase-drafts", json=payload, headers=_headers())
    finally:
        event.remove(AuditLog, "before_insert", fail_audit)
    with session_scope(engine) as session:
        assert session.scalars(select(PurchaseOrder)).all() == []
        assert session.scalars(select(AuditLog)).all() == []


def test_agent_replay_cannot_reassign_owner_or_duplicate_creator_audit(draft_api):
    client, engine, payload = draft_api
    created = client.post("/purchase-drafts", json=payload, headers=_headers())
    assert created.status_code == 200
    order_id = created.json()["id"]

    def provider():
        return MockLLMProvider([
            ToolCall("get_demand_forecast", {"material_id": 1, "horizon_days": 30}),
            ToolCall("recommend_suppliers", {
                "material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000.00",
            }),
            ToolCall("create_purchase_draft", {k: v for k, v in payload.items() if k != "total_budget"} | {
                "evidence_refs": ["use_latest_forecast", "use_latest_recommendation"],
            }),
        ])

    agent_client = TestClient(create_app(engine, auth_secret="test-secret", agent_provider_factory=provider))
    replay = agent_client.post("/agent/runs", headers=_headers(), json={"total_budget": "5000", "prompt": "repeat owned draft"})
    assert replay.status_code == 200
    assert replay.json()["purchase_order_id"] == order_id
    with session_scope(engine) as session:
        assert len(session.scalars(select(AuditLog).where(AuditLog.action == "created_draft")).all()) == 1
    other = agent_client.post("/agent/runs", headers=_headers("buyer-2"), json={"total_budget": "5000", "prompt": "reuse other buyer key"})
    assert other.status_code == 403
    assert agent_client.get("/purchase-orders", headers=_headers("buyer-2")).json() == []
    with session_scope(engine) as session:
        creators = session.scalars(select(AuditLog).where(AuditLog.action == "created_draft")).all()
        assert len(creators) == 1
        assert creators[0].actor_user_id == "buyer-1"


@pytest.mark.parametrize("outer_buyer,status", [("buyer-1", 200), ("buyer-2", 403)])
def test_draft_rechecks_owner_if_key_is_committed_between_lookups(draft_api, monkeypatch, outer_buyer, status):
    import backend.app.main as main

    client, engine, payload = draft_api
    create = main.create_purchase_draft
    interleaved = False
    inner_order_id = None

    def create_after_other_request(*args, **kwargs):
        nonlocal interleaved, inner_order_id
        if not interleaved:
            interleaved = True
            response = client.post("/purchase-drafts", json=payload, headers=_headers())
            assert response.status_code == 200
            inner_order_id = response.json()["id"]
        return create(*args, **kwargs)

    monkeypatch.setattr(main, "create_purchase_draft", create_after_other_request)
    response = client.post("/purchase-drafts", json=payload, headers=_headers(outer_buyer))
    assert response.status_code == status
    if status == 200:
        assert response.json()["id"] == inner_order_id
    else:
        assert "id" not in response.json()
    with session_scope(engine) as session:
        assert len(session.scalars(select(PurchaseOrder)).all()) == 1
        creators = session.scalars(select(AuditLog).where(AuditLog.action == "created_draft")).all()
        assert len(creators) == 1
        assert creators[0].actor_user_id == "buyer-1"
