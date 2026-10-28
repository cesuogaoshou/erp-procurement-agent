import json
import os
import sys
from pathlib import Path

import httpx
from sqlalchemy import create_engine, select

from backend.app.config import load_project_env
from backend.app.db.session import create_session_factory
from backend.app.models import AgentRun, ApprovalRecord, AuditLog, PurchaseOrder, ToolTrace

load_project_env()
root = Path(__file__).parent
stage = sys.argv[1]
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
report = {"orders": [], "runs": [], "traces": []}
with create_session_factory(engine)() as session:
    for order_id in [55, 56]:
        order = session.get(PurchaseOrder, order_id)
        audits = session.scalars(select(AuditLog).where(AuditLog.order_id == order_id).order_by(AuditLog.id)).all()
        approvals = session.scalars(select(ApprovalRecord).where(ApprovalRecord.order_id == order_id)).all()
        report["orders"].append({
            "id": order.id, "status": order.status, "version": order.version,
            "formal_order_number": order.formal_order_number, "total_amount": str(order.total_amount),
            "idempotency_key": order.idempotency_key, "evidence": json.loads(order.evidence_refs_json),
            "items": [{"material_id": i.material_id, "quantity": str(i.quantity)} for i in order.items],
            "audits": [{"id": a.id, "action": a.action, "actor": a.actor_user_id} for a in audits],
            "approvals": [{"id": a.id, "decision": a.decision, "reason": a.reason} for a in approvals],
        })
    for run_id in [66, 67]:
        run = session.get(AgentRun, run_id)
        report["runs"].append({"id": run.id, "status": run.status, "order_id": run.purchase_order_id,
                               "prompt": run.prompt, "state": json.loads(run.state_json)})
        for trace in session.scalars(select(ToolTrace).where(ToolTrace.run_id == run_id).order_by(ToolTrace.step_index)):
            report["traces"].append({"id": trace.id, "run_id": run_id, "tool": trace.tool_name,
                                      "status": trace.status, "arguments": json.loads(trace.arguments_json),
                                      "output": json.loads(trace.output_json)})
engine.dispose()
with httpx.Client(base_url="http://127.0.0.1:8000") as client:
    login = client.post("/auth/login", json={"username": "buyer", "password": "buyer-pass"})
    login.raise_for_status()
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    report["buyer_visible_orders"] = [o for o in client.get("/purchase-orders", headers=headers).json() if o["id"] in [55, 56]]
    report["buyer_visible_runs"] = [r for r in client.get("/agent/runs", headers=headers).json() if r["id"] in [66, 67]]
    report["api_traces"] = {str(i): client.get(f"/agent/runs/{i}/traces", headers=headers).json() for i in [66, 67]}
(root / f"{stage}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
if stage == "after_restart":
    before = json.loads((root / "before_restart.json").read_text(encoding="utf-8"))
    assert report == before, "restart snapshot changed"
    (root / "restart_comparison.json").write_text(json.dumps({"identical": True, "orders": [55, 56], "runs": [66, 67],
        "trace_count": len(report["traces"]), "pending_order": 56, "approved_order": 55}, indent=2), encoding="utf-8")
print(json.dumps({"stage": stage, "orders": [{"id": o["id"], "status": o["status"], "version": o["version"]} for o in report["orders"]], "traces": len(report["traces"])}))
