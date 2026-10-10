from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine

from backend.app.db.session import create_session_factory
from backend.app.models import PurchaseOrder
from backend.app.services.agent_provider import LLMProvider
from backend.app.services.agent_tools import build_agent_tools, execute_agent_tool


@dataclass(frozen=True)
class AgentRunResult:
    status: str
    tool_calls: list[str]
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
        session_factory = create_session_factory(self.engine)
        with session_factory() as session:
            for _ in range(self.max_tool_calls):
                call = self.provider.next_tool_call(prompt, observations)
                if call is None:
                    return AgentRunResult(
                        status="completed",
                        tool_calls=tool_calls,
                        real_function_calling=bool(getattr(self.provider, "real_function_calling", False)),
                    )
                if call.name not in self.allowed_tools:
                    return AgentRunResult(
                        status="tool_not_allowed",
                        tool_calls=tool_calls,
                        error=f"tool_not_allowed:{call.name}",
                        real_function_calling=bool(getattr(self.provider, "real_function_calling", False)),
                    )
                tool_calls.append(call.name)
                output = execute_agent_tool(session, call.name, call.arguments)
                if isinstance(output, PurchaseOrder):
                    session.commit()
                    return AgentRunResult(
                        status="draft_created",
                        tool_calls=tool_calls,
                        purchase_order_id=output.id,
                        total_amount=Decimal(output.total_amount),
                        real_function_calling=bool(getattr(self.provider, "real_function_calling", False)),
                    )
                observations.append({"tool": call.name, "output": _serializable_observation(output)})
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
