# Roadmap

## Phase 1: 2026-10-10 to 2026-10-14

Goal: complete deterministic backend and algorithm foundation without LLM dependency.

Acceptance:
- Query inventory, forecast demand, compute shortage, recommend suppliers, and create purchase draft without LLM.
- Simulated data generator is reproducible and documents distributions.
- Baseline evaluation runs and reports raw metrics and risks.

Status: complete for deterministic backend and MySQL integration. Done: deterministic backend flow, CSV export, expanded baseline backtest, real Prophet-vs-moving-average comparison on identical windows, Prophet diagnostic reporting with insufficient-history failures, frozen and challenge supplier label sets, purchase draft persistence, MOQ/package-multiple order rounding, server-signed demo token auth, approval status transitions, role checks, approval idempotency, audit logs, transaction rollback tests, SQLite Alembic migration verification, and MySQL migration/data/concurrency/rollback/persistence verification with the current `DATABASE_URL`.

## Phase 2: 2026-10-15 to 2026-10-20

Goal: add provider abstraction, Function Calling, Agent Loop, LangGraph execution, and Trace persistence.

Acceptance:
- Real model can run from natural language request to purchase draft when credentials are configured.
- Ambiguity, no candidates, and tool failures return controlled states.

Status: real DeepSeek/OpenAI-compatible Function Calling and real LangGraph package execution are accepted for the backend draft-creation path. Done: provider abstraction, mock provider, OpenAI adapter error handling, OpenAI-compatible tool schema dispatch, bounded Agent loop, read-only tools, forecast evidence validation, `create_purchase_draft` tool, real `StateGraph` execution wrapper, persisted run/tool traces, controlled states for ambiguity, no shortage, no qualified supplier, tool errors, timeout, call limits, duplicate draft idempotency, and real model validation that creates a backend-validated draft while approval/rejection remain unavailable to the model. LangGraph uses an in-process `MemorySaver`; restart query and approval recovery are provided by database persistence, not by a cross-process LangGraph checkpoint store.

## Phase 3: 2026-10-21 to 2026-10-24

Goal: implement approval, permissions, transactions, idempotency, and minimal frontend.

Acceptance:
- Complete demo loop with buyer and approver roles.
- Duplicate approval and unauthorized approval tests pass.

Status: backend approval slice complete without frontend. MySQL dual-session concurrency, duplicate approval idempotency, rollback, and persistence verification passed with the current `DATABASE_URL`. A real model business loop has been validated through draft creation, buyer submit, approver approval, formal order generation, blocked model approval, and duplicate-operation idempotency. Remaining Phase 3 work is minimal frontend if still required by the course/demo package.

## Phase 4: 2026-10-25 to 2026-10-27

Goal: freeze evaluation datasets and run prediction, recommendation, and Agent experiments.

Acceptance:
- Raw outputs, sample counts, charts, and failure cases are preserved.

Status: in progress for forecasting diagnostics. Current evidence preserves the original Prophet comparison baseline and hashes under `reports/generated/forecast_diagnostics/baseline_20261011/`, writes per-window diagnostics to `reports/generated/forecast_diagnostics/forecast_window_diagnostics.csv`, and writes diagnostic JSON plus representative curves under `reports/generated/forecast_diagnostics/`. The declared holdout/test windows have already been inspected for diagnostics, so they cannot be described as fully untouched independent final test evidence.

## Phase 5: 2026-10-28 to 2026-10-29

Goal: prepare report, screenshots, dependency lock, source code, and data package.

Acceptance:
- Reproducible delivery package and demo rehearsal complete.

Status: not started.
