import json
from decimal import Decimal

from sqlalchemy import select

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import AgentRun, Material, MaterialAlias
from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import MockLLMProvider, ToolCall
from backend.app.services.agent_tools import execute_agent_tool
from backend.app.services.material_search import search_materials, source_mentions_material
from backend.app.services.seed import seed_demo_data


def _engine():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
    return engine


def test_alias_search_and_standalone_source_support():
    engine = _engine()
    with session_scope(engine) as session:
        bearing = session.get(Material, 1)
        candidates = search_materials(session, "轴承")
        assert candidates[0]["material_id"] == 1
        assert candidates[0]["match_type"] == "alias_exact"
        assert candidates[0]["matched_alias"] == "轴承"
        assert source_mentions_material(session, bearing, "买点轴承120件")
        assert not source_mentions_material(session, bearing, "火星牌超导轴承")
    engine.dispose()


def test_capture_resolves_short_alias_but_rejects_longer_unknown_product():
    engine = _engine()
    with session_scope(engine) as session:
        assert session.scalar(select(MaterialAlias).where(MaterialAlias.alias == "轴承")) is not None

    provider = MockLLMProvider([
        ToolCall("capture_request", {
            "items": [{"query": "轴承", "quantity": "120"}],
            "purchase_requested": True,
            "stated_budget": "5000",
            "required_in_days": 20,
        })
    ])
    provider.real_function_calling = True
    result = AgentLoop(engine=engine, provider=provider).run("买点轴承120件，20天内到货，预算5000元", total_budget=Decimal("5000"))
    assert result.status == "completed"
    with session_scope(engine) as session:
        state = json.loads(session.get(AgentRun, result.run_id).state_json)
        assert state["user_request"]["items"][0]["material_id"] == 1
        assert state["user_request"]["verification"] == "source_verified"

    provider = MockLLMProvider([
        ToolCall("capture_request", {
            "items": [{"query": "轴承", "quantity": "120"}],
            "purchase_requested": True,
            "stated_budget": "5000",
            "required_in_days": 20,
        })
    ])
    provider.real_function_calling = True
    rejected = AgentLoop(engine=engine, provider=provider).run(
        "买120件火星牌超导轴承，20天内到货，预算5000元", total_budget=Decimal("5000")
    )
    assert rejected.status == "needs_information"
    assert rejected.purchase_order_id is None
    engine.dispose()


def test_search_and_resolve_tools_use_database_aliases():
    engine = _engine()
    with session_scope(engine) as session:
        found = execute_agent_tool(session, "search_materials", {"query": "电机", "limit": 5})
        assert found["candidates"][0]["material_id"] == 4
        resolved = execute_agent_tool(session, "resolve_material", {"query": "标准件"})
        assert resolved["status"] == "resolved"
        assert resolved["material"]["id"] == 1
    engine.dispose()
