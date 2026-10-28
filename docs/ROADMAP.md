# Roadmap

## Latest Acceptance Override: 2026-10-28

Requested draft-security/MySQL remediation and page acceptance are **passed**; see `docs/REMEDIATION_ACCEPTANCE_20261028.md`. Phase 3 permission remediation is closed: authenticated buyer creation, transactional creator audit, owner-only submission/replay, and Agent replay audit deduplication are covered by regressions. Fresh backend suite: 82 passed/3 opt-in skipped; MySQL suite: 3 passed, including exactly one concurrent approval, one duplicate approval record, explicit wrong-version conflict, rollback to pending, and reconnect query. Browser approved PO-000055 and rejected #56 after backend restart; two runs and seven traces survived unchanged. The earlier failure report remains in `docs/LOCAL_ACCEPTANCE_20261028.md`. Personal report fields and package refresh remain outside this slice, and frozen forecasting limitations still apply.

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

Status: real DeepSeek/OpenAI-compatible Function Calling and real LangGraph package execution are accepted for the backend draft-creation path. Done: provider abstraction, mock provider, OpenAI adapter error handling, OpenAI-compatible tool schema dispatch, bounded Agent loop, read-only tools, shared forecast/recommendation evidence validation, `create_purchase_draft` tool, real `StateGraph` execution wrapper, persisted run/tool traces, controlled states for ambiguity, no shortage, no qualified supplier, tool errors, timeout, call limits, duplicate draft idempotency, and real model validation that creates a backend-validated draft while approval/rejection remain unavailable to the model. Latest real acceptance records config sources, code version, real tool traces, final state, and approval state without secrets. LangGraph uses an in-process `MemorySaver`; restart query and approval recovery are provided by database persistence, not by a cross-process LangGraph checkpoint store.

## Phase 3: 2026-10-21 to 2026-10-24

Goal: implement approval, permissions, transactions, idempotency, and minimal frontend.

Acceptance:
- Complete demo loop with buyer and approver roles.
- Duplicate approval and unauthorized approval tests pass.

Status: complete for backend approval and first minimal frontend. MySQL dual-session concurrency, duplicate approval idempotency, rollback, and persistence verification passed with the current `DATABASE_URL`. A real model business loop has been validated through draft creation, buyer submit, approver approval, formal order generation, blocked model approval, and duplicate-operation idempotency. Minimal object-level read access scopes buyer-created runs, traces, and orders, while approvers can read approval-needed/processed orders and associated evidence. The frontend now provides four minimal pages for intelligent procurement, data analysis, approval, and execution records, using signed demo tokens and backend-owned permissions.

## Phase 4: 2026-10-25 to 2026-10-27

Goal: freeze evaluation datasets and run prediction, recommendation, and Agent experiments.

Acceptance:
- Raw outputs, sample counts, charts, and failure cases are preserved.

Status: frozen for current course delivery. Current evidence preserves the original Prophet comparison baseline and hashes under `reports/generated/forecast_diagnostics/baseline_20261011/`, writes per-window diagnostics to `reports/generated/forecast_diagnostics/forecast_window_diagnostics.csv`, and writes diagnostic JSON plus representative curves under `reports/generated/forecast_diagnostics/`. The latest exploratory comparison keeps full 160-window moving-average results, reports long-history Prophet as 50/160 successful windows, adds same-window moving-average metrics for those 50 windows, adds dynamic seasonality with 140/160 successful windows, and reports a separate hybrid strategy with 20/160 moving-average fallbacks. Service prediction is now frozen as `forecast_strategy_v1_20261011`: dynamic Prophet is the main path, short-history failures fall back to 30-day moving average, and forecast evidence is returned and persisted through Agent traces and purchase draft evidence payloads. The declared holdout/test windows have already been inspected for diagnostics, so they cannot be described as fully untouched independent final test evidence. Shortage experiments reuse the static 2026-10-10 inventory snapshot and are fixed-inventory scenario tests, not true historical inventory backtests. Generated reports remain Git-ignored but reproducible; include `reports/generated/forecast_comparison.json`, `reports/generated/forecast_diagnostics/`, `reports/generated/baseline_eval.json`, supplier eval, MySQL report if rerun, and real model acceptance JSON in the course delivery package.

## Phase 5: 2026-10-28 to 2026-10-29

Goal: prepare report, screenshots, dependency lock, source code, and data package.

Acceptance:
- Reproducible delivery package and demo rehearsal complete.

Status: delivery preparation is complete locally for the current evidence set. Repeatable demo steps, package checklist, report outline/evidence index, npm audit remediation, acceptance review with remediation addendum, and screenshot evidence under `reports/generated/screenshots/` are present. The formal Word report and course delivery folder are generated by `scripts/build_course_delivery.py` under `delivery/【待填写姓名】ERP课程作业报告/`; the rendered Word report has 9 pages and includes architecture, source-aligned algorithm formulas, forecast/recommendation charts, current screenshots, inventory-evidence wording, limitations, and reproduction commands. The package includes the Word report plus `源代码和数据集`, copies source/data/evidence files, excludes `.env`, keys, virtual environments, `node_modules`, TypeScript build caches, Chrome profiles, and local database snapshots, and writes `PACKAGE_MANIFEST.md` plus `SENSITIVE_SCAN.md`. The real frontend loop was revalidated locally through Agent draft creation, buyer submit, approver approval, and formal order `PO-000002`; backend real-model acceptance was rerun after minimal remediation and produced the latest evidence recorded in `reports/generated/real_model_acceptance.json`. Do not reopen prediction tuning unless a new explicit change request does so.
