from typing import Any, TypedDict
from decimal import Decimal

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import Engine

from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import LLMProvider


class ProcurementGraphState(TypedDict, total=False):
    prompt: str
    status: str
    tool_calls: list[str]
    run_id: int | None
    purchase_order_id: int | None
    error: str | None
    real_function_calling: bool
    langgraph_executed: bool
    total_amount: str | None
    business_message: str
    next_action: str
    model_response: str
    confirmation_fingerprint: str | None


def run_langgraph_procurement(
    *,
    engine: Engine,
    provider: LLMProvider,
    prompt: str,
    thread_id: str,
    max_tool_calls: int = 8,
    total_budget: Decimal | None = None,
    owner_user_id: str | None = None,
) -> ProcurementGraphState:
    graph = StateGraph(ProcurementGraphState)

    def run_agent(state: ProcurementGraphState) -> ProcurementGraphState:
        result = AgentLoop(engine=engine, provider=provider, max_tool_calls=max_tool_calls).run(
            state["prompt"], total_budget=total_budget, owner_user_id=owner_user_id)
        return {
            "prompt": state["prompt"],
            "status": result.status,
            "tool_calls": result.tool_calls,
            "run_id": result.run_id,
            "purchase_order_id": result.purchase_order_id,
            "error": result.error,
            "total_amount": None if result.total_amount is None else str(result.total_amount),
            "business_message": result.business_message,
            "next_action": result.next_action,
            "model_response": result.model_response,
            "confirmation_fingerprint": result.confirmation_fingerprint,
            "real_function_calling": result.real_function_calling,
            "langgraph_executed": True,
        }

    graph.add_node("agent_loop", run_agent)
    graph.set_entry_point("agent_loop")
    graph.add_edge("agent_loop", END)
    app = graph.compile(checkpointer=MemorySaver())
    return app.invoke({"prompt": prompt}, config={"configurable": {"thread_id": thread_id}})
