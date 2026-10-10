# ERP Procurement Agent Project Rules

## Read Order

For new sessions, read these files first:

1. `AGENTS.md`
2. `docs/PROJECT_INDEX.md`
3. `agent/HANDOFF.md`
4. `agent/TASK.md`

Then read deeper docs, the original outline, and code only as needed for the current task.

## Source Of Truth

- The original outline `ERP智能采购Agent_开发实施大纲 .md` is the scope and acceptance reference.
- Project-specific rules in this file override general workflow preferences.
- Do not fabricate experiment results, screenshots, model calls, or completion status.
- Missing external credentials must not block work that can be completed offline.

## Development Boundaries

- Build an ERP intelligent procurement decision system for course topic 3.2.
- Keep LLM responsibilities limited to intent understanding and tool orchestration.
- Backend services must own SQL access, numerical calculations, scoring, permissions, approvals, transactions, and idempotency.
- Do not expand into a full ERP, RAG, MCP service platform, multi-agent system, LSTM project, real supplier integration, payment, email sending, or external purchase execution.
- Mock providers are only for offline testing and must be clearly labeled.

## Environment

- Primary backend stack: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest.
- Unit tests may use SQLite.
- MySQL is the target integration database; local discovery found MySQL 8.4 available on this machine.
- Python 3.13 and Docker are available in the current environment.

## Verification Commands

Use the smallest command that verifies the change, then run broader checks before claiming phase completion.

```powershell
python -m pytest backend/tests -q
python -m backend.evaluation.run_baseline
python -m backend.app.main --help
```

## Git Rules

- Check Git status before modifying existing work.
- Protect user changes; do not revert unrelated edits.
- This directory was not a Git repository at project initialization.
- Keep `agent/` ignored by default while still maintaining it locally.

## Documentation Maintenance

- Append meaningful work to `agent/MEMORY.md`.
- Record durable technical decisions in `agent/DECISIONS.md`.
- After a phase or sub-phase, refresh `docs/PROJECT_INDEX.md`, `docs/ROADMAP.md`, `agent/TASK.md`, and `agent/HANDOFF.md`.
