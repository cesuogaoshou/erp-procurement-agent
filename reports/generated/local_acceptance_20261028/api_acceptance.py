"""Live local acceptance; appends acceptance orders, never resets existing data."""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import httpx
from sqlalchemy import create_engine, func, select
from backend.app.config import load_project_env
from backend.app.db.session import create_session_factory
from backend.app.models import ApprovalRecord, AuditLog, PurchaseOrder
from backend.app.services.approvals import AuthContext, ApprovalActionInput, approve_order

OUT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8000"
report = {"checks": [], "orders": {}, "generated_at": "2026-10-28"}
run_key = f"local-acceptance-{time.time_ns()}"

def record(name, passed, **details):
    report["checks"].append({"name": name, "passed": bool(passed), **details})
    (OUT / "api_acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["checks"][-1], ensure_ascii=False, default=str), flush=True)

def request(method, path, token=None, body=None, headers=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    h.update(headers or {})
    return httpx.request(method, BASE + path, headers=h, json=body, timeout=90)

def ok(response):
    response.raise_for_status()
    return response.json()

try:
    load_project_env()
    buyer = ok(request("POST", "/auth/login", body={"username": "buyer", "password": "buyer-pass"}))["access_token"]
    approver = ok(request("POST", "/auth/login", body={"username": "approver", "password": "approver-pass"}))["access_token"]
    record("login_and_health", ok(request("GET", "/health"))["status"] == "ok")
    unauth = request("GET", "/purchase-orders")
    record("unauthenticated_order_list_denied", unauth.status_code == 401, http_status=unauth.status_code)
    bad_login = request("POST", "/auth/login", body={"username": "buyer", "password": "wrong-acceptance-password"})
    record("incorrect_password_denied", bad_login.status_code == 401, http_status=bad_login.status_code)
    inventory = ok(request("GET", "/inventory/1", buyer))
    forecast = ok(request("POST", "/forecasts", buyer, {"material_id": 1, "horizon_days": 30}))
    computed = max(Decimal("0"), Decimal(forecast["forecast_demand"]) + Decimal(forecast["safety_stock"]) - Decimal(inventory["available_supply"]))
    record("forecast_shortage_formula", computed == Decimal(forecast["shortage_quantity"]), inventory=inventory, forecast=forecast)
    history = ok(request("GET", "/demand-history/1?days=120", buyer))
    record("demand_history_loaded", len(history) > 0, point_count=len(history))
    rec = ok(request("POST", "/recommendations", buyer, {"material_id": 1, "quantity": "120", "required_in_days": 20, "budget": "5000"}))
    record("supplier_recommendations", bool(rec["recommendations"]) and bool(rec["evidence_ref"]), result=rec)
    supplier = rec["recommendations"][0]["supplier_id"]
    payload = {"supplier_id": supplier, "items": [{"material_id": 1, "quantity": "120"}], "evidence_refs": [forecast["evidence_ref"], rec["evidence_ref"]]}
    def draft(suffix):
        return ok(request("POST", "/purchase-drafts", buyer, payload | {"idempotency_key": run_key + suffix}))
    anonymous = request("POST", "/purchase-drafts", body=payload | {"idempotency_key": run_key + "-anonymous"})
    record("anonymous_draft_creation_denied", anonymous.status_code in (401, 403), http_status=anonymous.status_code, response=anonymous.json())
    if anonymous.status_code == 200:
        report["orders"]["anonymous_creation_reproduction"] = anonymous.json()["id"]
    order = draft("-approved")
    report["orders"]["approved"] = order["id"]
    duplicate = draft("-approved")
    record("draft_idempotency_and_amount", duplicate["id"] == order["id"] and all(Decimal(i["quantity"]) * Decimal(i["unit_price"]) == Decimal(i["line_amount"]) for i in order["items"]) and sum(Decimal(i["line_amount"]) for i in order["items"]) == Decimal(order["total_amount"]), order=order)
    invalid = request("POST", "/purchase-drafts", buyer, payload | {"idempotency_key": run_key + "-invalid-evidence", "evidence_refs": ["forecast:1:30:invalid", rec["evidence_ref"]]})
    record("forged_forecast_evidence_denied", invalid.status_code == 409, http_status=invalid.status_code, response=invalid.json())
    pending = ok(request("POST", f"/purchase-orders/{order['id']}/submit", buyer))
    action = {"expected_order_version": pending["version"], "idempotency_key": run_key + "-approve"}
    anonymous_approve = request("POST", f"/purchase-orders/{order['id']}/approve", body=action)
    record("anonymous_approval_denied", anonymous_approve.status_code == 401, http_status=anonymous_approve.status_code)
    forbidden = request("POST", f"/purchase-orders/{order['id']}/approve", buyer, action | {"actor_user_id": "approver-1", "actor_role": "approver"}, {"X-User-Role": "approver"})
    record("buyer_forged_role_approval_denied", forbidden.status_code == 403, http_status=forbidden.status_code, response=forbidden.json())
    approved = ok(request("POST", f"/purchase-orders/{order['id']}/approve", approver, action))
    approved_again = ok(request("POST", f"/purchase-orders/{order['id']}/approve", approver, action))
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    factory = create_session_factory(engine)
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(ApprovalRecord).where(ApprovalRecord.order_id == order["id"]))
    record("approval_and_duplicate_idempotency", approved["status"] == "approved" and approved_again == approved and count == 1 and bool(approved["formal_order_number"]), order=approved, approval_record_count=count)
    rejected = draft("-rejected")
    report["orders"]["rejected"] = rejected["id"]
    pending_reject = ok(request("POST", f"/purchase-orders/{rejected['id']}/submit", buyer))
    rejection = ok(request("POST", f"/purchase-orders/{rejected['id']}/reject", approver, {"expected_order_version": pending_reject["version"], "idempotency_key": run_key + "-reject", "reason": "本机验收：验证驳回流程"}))
    record("human_rejection", rejection["status"] == "rejected" and rejection["formal_order_number"] is None, order=rejection)
    concurrent = draft("-concurrent")
    report["orders"]["concurrent"] = concurrent["id"]
    concurrent_pending = ok(request("POST", f"/purchase-orders/{concurrent['id']}/submit", buyer))
    def approve_concurrent(suffix):
        r = request("POST", f"/purchase-orders/{concurrent['id']}/approve", approver, {"expected_order_version": concurrent_pending["version"], "idempotency_key": run_key + "-concurrent-" + suffix})
        return {"http_status": r.status_code, "response": r.json()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(approve_concurrent, ["a", "b"]))
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(ApprovalRecord).where(ApprovalRecord.order_id == concurrent["id"]))
    record("mysql_live_concurrent_approval", sorted(x["http_status"] for x in outcomes) == [200, 409] and count == 1, outcomes=outcomes, approval_record_count=count)
    rollback = draft("-rollback")
    report["orders"]["rollback_pending"] = rollback["id"]
    rollback_pending = ok(request("POST", f"/purchase-orders/{rollback['id']}/submit", buyer))
    with factory() as session:
        try:
            approve_order(session, rollback["id"], AuthContext("approver-1", "approver"), ApprovalActionInput(rollback_pending["version"], run_key + "-rollback"))
            raise RuntimeError("local acceptance rollback after flush")
        except RuntimeError:
            session.rollback()
    with factory() as session:
        stored = session.get(PurchaseOrder, rollback["id"])
        count = session.scalar(select(func.count()).select_from(ApprovalRecord).where(ApprovalRecord.order_id == rollback["id"]))
        actions = list(session.scalars(select(AuditLog.action).where(AuditLog.order_id == rollback["id"])))
        record("mysql_transaction_rollback", stored.status == "pending_approval" and stored.version == rollback_pending["version"] and stored.formal_order_number is None and count == 0 and "approved" not in actions, order_id=stored.id, status=stored.status, version=stored.version, approval_record_count=count, audit_actions=actions)
    engine.dispose()
    report["status"] = "passed" if all(x["passed"] for x in report["checks"]) else "partial_failed"
except Exception as exc:
    report["status"] = "error"
    report["error"] = f"{type(exc).__name__}: {exc}"
finally:
    (OUT / "api_acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status": report.get("status"), "passed": sum(x["passed"] for x in report["checks"]), "failed": [x["name"] for x in report["checks"] if not x["passed"]], "error": report.get("error"), "orders": report["orders"]}, ensure_ascii=False), flush=True)
