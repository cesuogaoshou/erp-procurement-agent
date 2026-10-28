import json
import os
from pathlib import Path

import httpx
from sqlalchemy import create_engine, func, select

from backend.app.config import load_project_env
from backend.app.db.session import create_session_factory
from backend.app.models import AuditLog, PurchaseOrder

load_project_env()
root = Path(__file__).parent
snapshot = json.loads((root / "final_state.json").read_text(encoding="utf-8"))
order = snapshot["orders"][0]
payload = {"supplier_id": 1, "items": [{"material_id": 1, "quantity": "120"}],
           "idempotency_key": order["idempotency_key"], "evidence_refs": order["evidence"]["refs"]}
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

def counts():
    with create_session_factory(engine)() as session:
        return {"orders": session.scalar(select(func.count()).select_from(PurchaseOrder)),
                "creation_audits": session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.order_id == 55, AuditLog.action == "created_draft"))}

before = counts()
results = {}
with httpx.Client(base_url="http://127.0.0.1:8000") as client:
    for name, headers, expected in [
        ("anonymous_create", {}, 401),
        ("forged_headers_create", {"X-User-Id": "buyer-1", "X-User-Role": "buyer"}, 401),
    ]:
        response = client.post("/purchase-drafts", json=payload, headers=headers)
        assert response.status_code == expected
        results[name] = {"status_code": response.status_code, "detail": response.json()["detail"]}
    for role in ["buyer", "approver"]:
        login = client.post("/auth/login", json={"username": role, "password": role + "-pass"})
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        response = client.post("/purchase-drafts", json=payload, headers=headers)
        assert response.status_code == (200 if role == "buyer" else 403)
        results[role + "_replay"] = {"status_code": response.status_code}
        if role == "buyer":
            assert response.json()["id"] == 55
            results[role + "_replay"]["order_id"] = response.json()["id"]
        else:
            results[role + "_replay"]["detail"] = response.json()["detail"]
after = counts()
assert before == after
assert after["creation_audits"] == 1
engine.dispose()
report = {"checks": results, "before": before, "after": after, "no_new_order_or_creation_audit": True}
(root / "live_auth_checks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
