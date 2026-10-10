import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine

from backend.app.db.session import create_session_factory
from backend.app.models import AgentRun, PurchaseOrder, ToolTrace
from backend.app.services.agent_provider import LLMProvider, ProviderError
from backend.app.services.agent_tools import build_agent_tools, execute_agent_tool


@dataclass(frozen=True)
class AgentRunResult:
    status: str
    tool_calls: list[str]
    run_id: int | None = None
    purchase_order_id: int | None = None
    total_amount: Decimal | None = None
    error: str | None = None
    real_function_calling: bool = False


class AgentRunLimitExceeded(RuntimeError):
    pass


class AgentLoop:
    def __init__(self, *, engine: Engine, provider: LLMProvider, max_tool_calls: int = 6) -> None:
        self.engine = engine
        self.provider = provider
        self.max_tool_calls = max_tool_calls
        self.allowed_tools = {tool.name for tool in build_agent_tools()}

    def run(self, prompt: str) -> AgentRunResult:
        observations: list[dict[str, Any]] = []
        tool_calls: list[str] = []
        evidence_registry: dict[str, dict[str, Any]] = {}
        session_factory = create_session_factory(self.engine)
        with session_factory() as session:
            run = AgentRun(status="running", prompt=prompt, state_json=json.dumps({"node": "start"}))
            session.add(run)
            session.flush()
            for _ in range(self.max_tool_calls):
                try:
                    call = self.provider.next_tool_call(prompt, observations)
                except ProviderError as exc:
                    run.status = "provider_error"
                    run.error = str(exc)
                    run.updated_at = datetime.now(UTC)
                    session.commit()
                    return AgentRunResult(
                        status="provider_error",
                        tool_calls=tool_calls,
                        run_id=run.id,
                        error=str(exc),
                        real_function_calling=bool(getattr(self.provider, "real_function_calling", False)),
                    )
                if call is None:
                    status = "no_shortage" if _latest_shortage_is_zero(evidence_registry) else "completed"
                    run.status = status
                    run.state_json = json.dumps({"node": status}, sort_keys=True)
                    run.updated_at = datetime.now(UTC)
                    session.commit()
                    return AgentRunResult(
                        status=status,
                        tool_calls=tool_calls,
                        run_id=run.id,
                        real_function_calling=bool(getattr(self.provider, "real_function_calling", False)),
                    )
                if call.name not in self.allowed_tools:
                    run.status = "tool_not_allowed"
                    run.error = f"tool_not_allowed:{call.name}"
                    run.updated_at = datetime.now(UTC)
                    session.commit()
                    return AgentRunResult(
                        status="tool_not_allowed",
                        tool_calls=tool_calls,
                        run_id=run.id,
                        error=f"tool_not_allowed:{call.name}",
                        real_function_calling=bool(getattr(self.provider, "real_function_calling", False)),
                    )
                tool_calls.append(call.name)
                try:
                    output = execute_agent_tool(session, call.name, call.arguments, evidence_registry)
                    session.add(
                        ToolTrace(
                            run_id=run.id,
                            step_index=len(tool_calls),
                            tool_name=call.name,
                            arguments_json=json.dumps(call.arguments, ensure_ascii=False, sort_keys=True),
                            output_json=json.dumps(_trace_output(output), ensure_ascii=False, sort_keys=True),
                            status="ok",
                        )
                    )
                except Exception as exc:
                    session.add(
                        ToolTrace(
                            run_id=run.id,
                            step_index=len(tool_calls),
                            tool_name=call.name,
                            arguments_json=json.dumps(call.arguments, ensure_ascii=False, sort_keys=True),
                            output_json="{}",
                            status="error",
                            error=str(exc),
                        )
                    )
                    run.status = "tool_error"
                    run.error = str(exc)
                    run.updated_at = datetime.now(UTC)
                    session.commit()
                    return AgentRunResult(
                        status="tool_error",
                        tool_calls=tool_calls,
                        run_id=run.id,
                        error=str(exc),
                        real_function_calling=bool(getattr(self.provider, "real_function_calling", False)),
                    )
                if isinstance(output, PurchaseOrder):
                    run.status = "draft_created"
                    run.purchase_order_id = output.id
                    run.state_json = json.dumps({"node": "draft_created", "purchase_order_id": output.id}, sort_keys=True)
                    run.updated_at = datetime.now(UTC)
                    session.commit()
                    return AgentRunResult(
                        status="draft_created",
                        tool_calls=tool_calls,
                        run_id=run.id,
                        purchase_order_id=output.id,
                        total_amount=Decimal(output.total_amount),
                        real_function_calling=bool(getattr(self.provider, "real_function_calling", False)),
                    )
                special_status = _special_tool_status(call.name, output)
                if special_status is not None:
                    run.status = special_status
                    run.state_json = json.dumps({"node": special_status, "last_tool": call.name}, sort_keys=True)
                    run.updated_at = datetime.now(UTC)
                    session.commit()
                    return AgentRunResult(
                        status=special_status,
                        tool_calls=tool_calls,
                        run_id=run.id,
                        real_function_calling=bool(getattr(self.provider, "real_function_calling", False)),
                    )
                observations.append({"tool": call.name, "output": _serializable_observation(output)})
                run.state_json = json.dumps({"node": "tool_completed", "last_tool": call.name}, sort_keys=True)
                run.updated_at = datetime.now(UTC)
            raise AgentRunLimitExceeded("max_tool_calls_exceeded")


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
    latest = next(reversed(evidence_registry.values()))
    return Decimal(latest["shortage_quantity"]) == 0


def _special_tool_status(tool_name: str, output: Any) -> str | None:
    if tool_name == "resolve_material" and isinstance(output, dict):
        if output.get("status") == "material_ambiguous":
            return "material_ambiguous"
        if output.get("status") == "material_not_found":
            return "material_not_found"
    if tool_name == "recommend_suppliers" and isinstance(output, dict) and not output.get("recommendations"):
        return "no_qualified_suppliers"
    return None
