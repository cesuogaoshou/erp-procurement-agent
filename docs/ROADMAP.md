# Roadmap

## Phase 1: 2026-10-10 to 2026-10-14

Goal: complete deterministic backend and algorithm foundation without LLM dependency.

Acceptance:
- Query inventory, forecast demand, compute shortage, recommend suppliers, and create purchase draft without LLM.
- Simulated data generator is reproducible and documents distributions.
- Baseline evaluation runs and reports raw metrics and risks.

Status: complete for deterministic backend and MySQL integration. Done: deterministic backend flow, CSV export, expanded baseline backtest, moving-average vs optional Prophet comparison harness, frozen and challenge supplier label sets, purchase draft persistence, server-signed demo token auth, approval status transitions, role checks, approval idempotency, audit logs, transaction rollback tests, SQLite Alembic migration verification, and MySQL migration/data/concurrency/rollback/persistence verification with the current `DATABASE_URL`.

## Phase 2: 2026-10-15 to 2026-10-20

Goal: add provider abstraction, Function Calling, Agent Loop, LangGraph-style state management, and Trace persistence.

Acceptance:
- Real model can run from natural language request to purchase draft when credentials are configured.
- Ambiguity, no candidates, and tool failures return controlled states.

Status: started offline with real-provider request contract coverage. Done: provider abstraction, mock provider, OpenAI adapter error handling, OpenAI-compatible tool schema dispatch, bounded Agent loop, read-only tools, forecast evidence validation, `create_purchase_draft` tool, persisted run/tool traces, and controlled states for ambiguity, no candidates, tool errors, timeout, call limits, and duplicate draft idempotency. Not passed: real external LLM Function Calling end-to-end; the latest real attempt reached the provider path but returned `provider_http_error:HTTPStatusError` because no compatible `OPENAI_BASE_URL` was configured for the selected OpenAI-compatible model. Real LangGraph package execution is not accepted because the dependency is unavailable; current state management is persisted and LangGraph-style.

## Phase 3: 2026-10-21 to 2026-10-24

Goal: implement approval, permissions, transactions, idempotency, and minimal frontend.

Acceptance:
- Complete demo loop with buyer and approver roles.
- Duplicate approval and unauthorized approval tests pass.

Status: backend approval slice complete without frontend. MySQL concurrency, rollback, and persistence verification passed with the current `DATABASE_URL`. Remaining Phase 3 work is minimal frontend if still required by the course/demo package.

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
