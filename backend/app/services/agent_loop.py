import json
import math
from dataclasses import dataclass, is_dataclass, asdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine

from backend.app.db.session import create_session_factory
from backend.app.models import AgentRun, PurchaseOrder, ToolTrace
from backend.app.services.agent_provider import LLMProvider, ProviderError
from backend.app.services.agent_tools import build_agent_tools, execute_agent_tool
from backend.app.services.business_feedback import ClarificationRequired, business_outcome


@dataclass(frozen=True)
class AgentRunResult:
    status: str
    tool_calls: list[str]
    run_id: int | None = None
    purchase_order_id: int | None = None
    total_amount: Decimal | None = None
    error: str | None = None
    real_function_calling: bool = False
    business_message: str = ""
    next_action: str = ""
    model_response: str = ""
    confirmation_fingerprint: str | None = None


class AgentRunLimitExceeded(RuntimeError):
    pass


class AgentLoop:
    def __init__(self, *, engine: Engine, provider: LLMProvider, max_tool_calls: int = 8,
                 timeout_seconds: float = 180) -> None:
        self.engine = engine
        self.provider = provider
        self.max_tool_calls = max_tool_calls
        self.timeout_seconds = timeout_seconds
        self.allowed_tools = {tool.name for tool in build_agent_tools()}

    def run(self, prompt: str, *, total_budget: Decimal | None = None,
            owner_user_id: str | None = None, confirmed_request: dict | None = None) -> AgentRunResult:
        from time import monotonic
        from sqlalchemy import select
        from backend.app.models import AuditLog
        observations: list[dict[str, Any]] = []
        tool_calls: list[str] = []
        evidence_registry: dict[str, dict[str, Any]] = {}
        if getattr(self.provider, "real_function_calling", False):
            evidence_registry["request_source"] = {"prompt": prompt}
        if confirmed_request:
            evidence_registry['request_source'] = {'prompt': prompt}
            evidence_registry['human_confirmation'] = confirmed_request
        session_factory = create_session_factory(self.engine)
        started = monotonic()
        with session_factory() as session:
            state = {"node": "start", "created_by_user_id": owner_user_id,
                     "confirmed_total_budget": None if total_budget is None else str(total_budget)}
            run = AgentRun(status="running", prompt=prompt, total_budget=total_budget,
                           state_json=json.dumps(state))
            session.add(run)
            session.commit()
            run_id = run.id
            if 'request_source' in evidence_registry:
                evidence_registry['request_source']['run_id'] = run_id

            def finish(status, error=None, order=None):
                message, next_action = business_outcome(status, error, observations, order, evidence_registry.get("user_request"))
                saved_request = evidence_registry.get('user_request')
                fingerprint = None
                if saved_request:
                    state['user_request'] = saved_request
                if status == 'awaiting_confirmation':
                    import hashlib
                    from backend.app.services.source_conditions import request_summary
                    fingerprint = hashlib.sha256(json.dumps(saved_request, sort_keys=True).encode()).hexdigest()
                    message = '原文中的物料与数量对应关系暂无法可靠自动核对，请逐项核对。' + request_summary(saved_request) + ' 本次未生成订单。'
                    next_action = '清单正确时点击“确认本次完整需求并准备草稿”；有误请修改原文重新分析，旧确认将失效。'
                state['confirmation_fingerprint'] = fingerprint
                model_response = getattr(self.provider, "last_content", "")
                state.update(business_message=message, next_action=next_action, model_response=model_response)
                run.status, run.error = status, error
                state["node"] = status
                run.state_json = json.dumps(state, ensure_ascii=False, sort_keys=True)
                run.updated_at = datetime.now(UTC)
                if order is not None:
                    run.purchase_order_id = order.id
                session.commit()
                return AgentRunResult(status=status, tool_calls=tool_calls, run_id=run_id,
                    purchase_order_id=None if order is None else order.id,
                    total_amount=None if order is None else Decimal(order.total_amount), error=error,
                    business_message=message, next_action=next_action, model_response=model_response,
                    confirmation_fingerprint=fingerprint,
                    real_function_calling=bool(getattr(self.provider, "real_function_calling", False)))

            # The confirmed context is server-owned, independent of model arguments.
            model_prompt = prompt + "\n服务端已确认整单预算: " + (str(total_budget) if total_budget is not None else "未知；创建草稿前需用户结构化确认")
            try:
                for _ in range(self.max_tool_calls):
                    if monotonic() - started >= self.timeout_seconds:
                        return finish("timeout", "agent_timeout")
                    try:
                        call = self.provider.next_tool_call(model_prompt, observations)
                    except ProviderError as exc:
                        return finish("provider_error", str(exc))
                    except Exception as exc:
                        session.rollback()
                        return finish("failed", f"unexpected_provider_error:{type(exc).__name__}")
                    if monotonic() - started >= self.timeout_seconds:
                        return finish("timeout", "agent_timeout")
                    if call is None:
                        try:
                            status = "no_shortage" if _latest_shortage_is_zero(evidence_registry) else "completed"
                            if not observations:
                                status = "needs_information"
                                return finish(status, "请补充物料名称、数量、预算和到货要求后重新运行。")
                            return finish(status)
                        except Exception as exc:
                            session.rollback()
                            return finish("failed", f"unexpected_completion_error:{type(exc).__name__}")
                    if call.name not in self.allowed_tools:
                        return finish("tool_not_allowed", f"tool_not_allowed:{call.name}")
                    if getattr(self.provider, "real_function_calling", False) and not evidence_registry.get("user_request") and call.name != "capture_request":
                        return finish("needs_information", "尚未核对采购需求，请重新运行并明确物料、数量、预算及到货要求。")
                    if call.name == "capture_request" and "user_request" in evidence_registry:
                        return finish("needs_information", "采购条件不能在本次执行中重新确认，请修改需求后重新运行。")
                    tool_calls.append(call.name)
                    try:
                        # All business writes for one tool are isolated. Failure rolls
                        # back that savepoint before ANY error trace is persisted.
                        with session.begin_nested():
                            output = execute_agent_tool(session, call.name, call.arguments, evidence_registry,
                                                        total_budget=total_budget)
                            if isinstance(output, PurchaseOrder) and owner_user_id is not None:
                                creator = session.scalar(select(AuditLog.actor_user_id).where(
                                    AuditLog.order_id == output.id, AuditLog.action == "created_draft").with_for_update())
                                if creator is not None and creator != owner_user_id:
                                    raise ValueError("order_owner_required")
                                if creator is None:
                                    session.add(AuditLog(order_id=output.id, actor_user_id=owner_user_id,
                                        actor_role="buyer", action="created_draft",
                                        details_json=json.dumps({"source": "agent", "run_id": run_id})))
                                    session.flush()
                        session.add(ToolTrace(run_id=run_id, step_index=len(tool_calls), tool_name=call.name,
                            arguments_json=json.dumps(_trace_output(call.arguments), ensure_ascii=False, sort_keys=True),
                            output_json=json.dumps(_trace_output(output), ensure_ascii=False, sort_keys=True), status="ok"))
                        if isinstance(output, PurchaseOrder):
                            return finish("draft_created", order=output)
                        if call.name == 'capture_request' and output.get('verification') == 'needs_confirmation':
                            return finish('awaiting_confirmation')
                        if call.name == 'capture_request':
                            state['user_request'] = output
                            run.state_json = json.dumps(state, ensure_ascii=False, sort_keys=True)
                        session.commit()
                    except Exception as exc:
                        session.rollback()
                        session.add(ToolTrace(run_id=run_id, step_index=len(tool_calls), tool_name=call.name,
                            arguments_json=json.dumps(_trace_output(call.arguments), ensure_ascii=False, sort_keys=True),
                            output_json="{}", status="error", error=str(exc)))
                        return finish("needs_information" if isinstance(exc, ClarificationRequired) else "tool_error", str(exc))
                    observations.append({"tool": call.name, "arguments": call.arguments,
                                         "output": _serializable_observation(output)})
                    special_status = _special_tool_status(call.name, output)
                    if special_status is not None:
                        return finish(special_status)
                finish("max_tool_calls_exceeded", "max_tool_calls_exceeded")
                raise AgentRunLimitExceeded("max_tool_calls_exceeded")
            except AgentRunLimitExceeded:
                raise
            except Exception as exc:
                session.rollback()
                return finish("failed", f"unexpected_agent_error:{type(exc).__name__}")


def _serializable_observation(value: Any) -> Any:
    if isinstance(value, list):
        return [_serializable_observation(item) for item in value]
    if hasattr(value, "__dict__"):
        return {key: _serializable_observation(item) for key, item in value.__dict__.items() if not key.startswith("_")}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _serializable_observation(item) for key, item in value.items()}
    return value


def _trace_output(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, PurchaseOrder):
        return {
            "id": value.id,
            "supplier_id": value.supplier_id,
            "status": value.status,
            "total_amount": str(value.total_amount),
            "idempotency_key": value.idempotency_key,
        }
    if isinstance(value, list):
        return [_trace_output(item) for item in value]
    if is_dataclass(value):
        return _trace_output(asdict(value))
    if isinstance(value, dict):
        return {str(key): _trace_output(item) for key, item in value.items()}
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "model_dump"):
        return _trace_output(value.model_dump())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _latest_shortage_is_zero(evidence_registry: dict[str, dict[str, Any]]) -> bool:
    if not evidence_registry:
        return False
    forecasts = [value for ref, value in evidence_registry.items() if ref.startswith("forecast:")]
    if not forecasts:
        return False
    latest_by_material = {}
    for forecast in forecasts:
        latest_by_material[forecast.get("material_id", "unknown")] = forecast
    return all(Decimal(str(value["shortage_quantity"])) == 0 for value in latest_by_material.values())


def _special_tool_status(tool_name: str, output: Any) -> str | None:
    if tool_name == "resolve_material" and isinstance(output, dict):
        if output.get("status") == "material_ambiguous":
            return "material_ambiguous"
        if output.get("status") == "material_not_found":
            return "material_not_found"
    if tool_name == "recommend_suppliers" and isinstance(output, dict) and not output.get("recommendations"):
        return "no_qualified_suppliers"
    return None
