# Roadmap

## Phase 1: 2026-10-10 to 2026-10-14

Goal: complete deterministic backend and algorithm foundation without LLM dependency.

Acceptance:
- Query inventory, forecast demand, compute shortage, recommend suppliers, and create purchase draft without LLM.
- Simulated data generator is reproducible and documents distributions.
- Baseline evaluation runs and reports raw metrics and risks.

Status: mostly complete. Done: deterministic backend flow, CSV export, expanded baseline backtest, independent supplier label set, purchase draft persistence, idempotency tests, and SQLite Alembic migration verification. Not passed: real MySQL migration/data initialization because credentials are unavailable.

## Phase 2: 2026-10-15 to 2026-10-20

Goal: add provider abstraction, Function Calling, Agent Loop, LangGraph-style state management, and Trace persistence.

Acceptance:
- Real model can run from natural language request to purchase draft when credentials are configured.
- Ambiguity, no candidates, and tool failures return controlled states.

Status: not started.

## Phase 3: 2026-10-21 to 2026-10-24

Goal: implement approval, permissions, transactions, idempotency, and minimal frontend.

Acceptance:
- Complete demo loop with buyer and approver roles.
- Duplicate approval and unauthorized approval tests pass.

Status: not started.

## Phase 4: 2026-10-25 to 2026-10-27

Goal: freeze evaluation datasets and run prediction, recommendation, and Agent experiments.

Acceptance:
- Raw outputs, sample counts, charts, and failure cases are preserved.

Status: not started.

## Phase 5: 2026-10-28 to 2026-10-29

Goal: prepare report, screenshots, dependency lock, source code, and data package.

Acceptance:
- Reproducible delivery package and demo rehearsal complete.

Status: not started.
