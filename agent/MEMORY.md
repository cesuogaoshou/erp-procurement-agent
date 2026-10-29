# Memory

## 2026-10-10

- Initialized standard project documentation from `ERP智能采购Agent_开发实施大纲 .md`.
- Environment inspection: directory was not a Git repository; no `AGENTS.md` existed; Python 3.13, Node 22, Docker, and MySQL 8.4 were available.
- Added `requirements.txt`, `.env.example`, `docker-compose.yml`, Alembic skeleton, SQLAlchemy model layer, service layer, algorithm layer, FastAPI routes, seed data, and baseline evaluation command.
- Tests added for shortage formula, supplier recommendation filtering/scoring, metrics zero handling, and API flow.
- Verification: `python -m pytest backend/tests -q` passed with 7 tests; `python -m backend.evaluation.run_baseline` wrote real baseline metrics; `python -m backend.app.main --check` printed `app ok`.
- Baseline result on simulated seed `20261010`: shortage MAPE 5.87%, shortage MAE 20.00, demand MAPE 5.04%, sample count 6. These are raw simulated baseline results, not a final course claim.
- Initialized local Git repository and committed baseline `8903dec chore: establish phase 1 foundation baseline`; configured only repo-local Git identity `Codex <codex@local>`.
- Docker MySQL verification blocked because Docker daemon was unavailable. Local MySQL service `MySQL84` is running, but `root` without password and `erp_user/change-me` both failed TCP auth, so real MySQL migration/init is not passed.
- Added Alembic revision `20261010_0002` for purchase draft tables; verified Alembic upgrade and deterministic data initialization on temporary SQLite.
- Expanded simulated data to 10 materials, 10 suppliers, 540 days per material, 100 supplier-material rows, and 100 performance rows; exported UTF-8 CSV files to `data/raw/`.
- Expanded baseline backtest to 160 samples and recorded train/holdout windows to guard against future leakage. Latest raw result: shortage MAPE 5.75%, shortage WAPE 5.59%, demand MAPE 5.18%.
- Added independent supplier recommendation cases from `scenario_thresholds_v1`, exported `data/raw/recommendation_cases.csv`, and evaluated price-sort vs composite Top-3 hit rates. Latest raw result: price-sort 93.33%, composite 100.00% on 60 simulated cases.
- Added purchase draft persistence with server-side supplier/material validation, evidence requirement, backend amount calculation, and idempotency; tests cover duplicate request, invalid supplier, capacity conflict, no evidence, and API flow.
- Added deterministic approval workflow: buyer submits draft to `pending_approval`; approver approves to `approved` with `formal_order_number` or rejects to `rejected`; service authorizes from `AuthContext` only and ignores body actor claims.
- Added `approval_records` and `audit_logs` plus Alembic revision `20261010_0003`; approval state changes, approval records, and audit logs are flushed in one transaction.
- Approval tests cover normal approve, reject, unauthorized buyer approval, duplicate idempotency key, stale/concurrent conflict, quote change rejection, and rollback when audit insertion fails.
- Added separate challenge recommendation cases under `data/raw/recommendation_challenge_cases.csv`; latest supplier eval output path is `reports/generated/supplier_eval.json`, with data version, parameters, label width, candidate count, output paths, and reproduce command.
- Latest supplier eval raw results: frozen set price-sort Top-3 93.33%, composite Top-3 100.00%; challenge set price-sort Top-3 95.00%, composite Top-3 100.00%.
- Current verification: `python -m pytest backend/tests -q` passed 24 tests; SQLite Alembic `upgrade head` passed through `20261010_0003`; SQLite init after migration inserted expected deterministic seed counts; `python -m backend.app.main --help` passed.
- MySQL remains blocked: no `.env` file and no `DATABASE_URL`/MySQL environment variable in this session; do not guess credentials or modify root. SQLite tests are not a substitute for MySQL concurrent approval validation.
- Corrected auth boundary: default approval auth now requires a server-signed bearer token from preset demo accounts `buyer` and `approver`; direct `X-User-Id`/`X-User-Role` headers are accepted only when `allow_header_auth=True` is explicitly enabled for tests.
- Added offline Agent layer with provider protocol, `MockLLMProvider`, tool schemas, and bounded `AgentLoop`; model tools are `list_materials`, `get_inventory`, `recommend_suppliers`, and `create_purchase_draft`; approval/rejection are not exposed as tools.
- Added auth and Agent tests. Latest focused auth/Agent/evaluation command passed 9 tests; latest full backend command passed 32 tests.
- Supplier eval details now report each case's candidate count, acceptable label count, price/composite hit delta, and failure reason. Frozen/challenge labels were not changed to manufacture algorithm advantage.
- Real external LLM Function Calling remains unaccepted because no LLM credentials are configured; MySQL migration/init/concurrency verification remains blocked by missing credentials.
- Added `backend/evaluation/run_forecast_comparison.py` for moving-average vs optional Prophet comparison on identical windows. Current environment lacks `prophet`, so Prophet is reported as failed rather than fabricated.
- Added `get_demand_forecast` Agent tool and server-side evidence registry. `create_purchase_draft` rejects missing forecast evidence and quantities above the server-calculated shortage.
- Added `agent_runs` and `tool_traces` tables in Alembic revision `20261010_0004`; AgentLoop persists status, state JSON, tool arguments/outputs, errors, and purchase draft IDs.
- Added OpenAI Function Calling provider adapter with missing credential, timeout, HTTP, and malformed response handling. Real calls are not accepted without `OPENAI_API_KEY` and `OPENAI_MODEL`.
- Added tests for tool parameter errors, no shortage, material ambiguity, no qualified supplier, model timeout, call limit, duplicate draft idempotency, and restart-style persistence through a new DB session.
- Latest full backend command passed 42 tests. Latest forecast comparison wrote `reports/generated/forecast_comparison.json`; moving average succeeded and Prophet failed due unavailable dependency.
- `langgraph` is not installed; current implementation is persisted LangGraph-style state management, not real LangGraph package execution.

## 2026-10-11

- Re-read `AGENTS.md`, `docs/PROJECT_INDEX.md`, `agent/HANDOFF.md`, and `agent/TASK.md`; Git worktree was clean on `master` before changes.
- Environment presence check showed `DATABASE_URL`, `ERP_AUTH_SECRET`, `OPENAI_API_KEY`, and `OPENAI_MODEL` configured in this process; values were not printed. `OPENAI_BASE_URL`, `OPENAI_MODEL_USER`, and `DEEPSEEK_API_KEY` were missing.
- Added OpenAI-compatible provider request-contract tests and implementation: real provider requests now send the full Agent `tools` schema with `tool_choice: auto`, keep approval/rejection out of model tools, and serialize prior observations as system context instead of invalid `role=tool` messages without `tool_call_id`.
- Added `cryptography` to `requirements.txt` so PyMySQL can support MySQL 8 `caching_sha2_password`; local environment already had `cryptography 50.0.2` installed while the pinned requirement now declares `46.0.2`.
- Added opt-in MySQL integration test `backend/tests/test_mysql_integration.py`; default backend pytest skips it unless `RUN_MYSQL_INTEGRATION=1`.
- Verified MySQL Alembic state with current `DATABASE_URL`: `python -m alembic current` reported `20261010_0004 (head)`.
- Verified MySQL deterministic seed counts before integration writes: materials 10, inventory 10, demand_history 5400, suppliers 10, supplier_materials 100, supplier_performance 100, purchase_orders 0.
- Ran real MySQL integration command: `$env:RUN_MYSQL_INTEGRATION='1'; $env:MYSQL_INTEGRATION_REPORT_PATH='reports/generated/mysql_integration.json'; python -m pytest backend/tests/test_mysql_integration.py -q` passed 1 test.
- MySQL integration report `reports/generated/mysql_integration.json` recorded: concurrent approval produced one approved outcome and one `order_not_pending_approval` conflict; rollback left a separate order in `pending_approval` with 0 approval records; Agent run/tool traces and a submitted pending draft were queryable after engine dispose/reconnect.
- Ran required verification: `python -m pytest backend/tests -q` passed 45 tests and skipped the opt-in MySQL integration test; `python -m backend.evaluation.run_baseline`, `python -m backend.evaluation.run_forecast_comparison`, `python -m backend.evaluation.run_supplier_eval`, and `python -m backend.app.main --help` all completed.
- Latest forecast comparison still reports Prophet as failed with `prophet_unavailable:ModuleNotFoundError`; do not claim real Prophet acceptance.
- Real LLM Function Calling attempt wrote `reports/generated/real_llm_function_calling.json`: credentials/model were configured and `real_function_calling` was true, but the run ended with `provider_error` / `provider_http_error:HTTPStatusError` and no tool calls because no compatible `OPENAI_BASE_URL` was configured. Do not claim real DeepSeek/OpenAI-compatible Function Calling acceptance yet.
- Configured non-secret DeepSeek/OpenAI-compatible env values in the user environment and current process: `OPENAI_BASE_URL=https://api.deepseek.com`, `OPENAI_MODEL_USER=deepseek-v4-flash`. API key value was not read or printed.
- Fixed provider URL normalization so a base root such as `https://api.deepseek.com` is sent to `/chat/completions`; complete `/chat/completions` endpoints are preserved.
- Real DeepSeek run initially selected `get_inventory` and exposed a local bug: Agent tool code assumed inventory snapshot had `__dict__`, but `get_inventory_snapshot()` returns a dict. Added regression coverage and fixed `execute_agent_tool(..., "get_inventory", ...)` to return the dict directly.
- Real DeepSeek/OpenAI-compatible Function Calling then passed end-to-end. Report path: `reports/generated/real_llm_function_calling.json`; status `draft_created`; tool calls were `list_materials`, `get_inventory`, `get_demand_forecast`, `recommend_suppliers`, `create_purchase_draft`; run id 6; purchase order id 7; `real_function_calling=true`. Approval/rejection tools were not exposed or called.
- Installed and pinned real Prophet/LangGraph dependencies: `prophet==1.5.0`, `cmdstanpy==1.3.0`, and `langgraph==1.2.14`.
- Added real LangGraph `StateGraph` runner around the bounded procurement Agent loop. Tests verify graph execution and SQL-backed run/tool/order queryability through a new DB session. LangGraph `MemorySaver` is in-process only; cross-process checkpoint recovery is not claimed.
- Added MOQ/package-multiple procurement rules. Draft creation rounds requested quantities up to satisfy supplier MOQ and package multiple; approval revalidates package multiple before formal order generation. Alembic revisions now include `20261011_0005` for the column and `20261011_0006` for demo package multiple values.
- Exported `data/raw/supplier_materials.csv` with `package_multiple`; material 9 and 10 supplier relationships use `10.00`. Frozen and challenge recommendation label files were not changed.
- Expanded opt-in MySQL integration coverage from one combined test to three tests. Latest command `$env:RUN_MYSQL_INTEGRATION='1'; $env:MYSQL_INTEGRATION_REPORT_PATH='reports/generated/mysql_integration.json'; python -m pytest backend/tests/test_mysql_integration.py -q` passed 3 tests covering dual-session concurrent approval, duplicate approval idempotency, stale-session conflict, rollback, and restart-style Agent persistence.
- Pre-diagnostic real Prophet comparison completed on the same 160 frozen windows and cutoffs as moving average. Superseded baseline `reports/generated/forecast_comparison.json`: moving average demand MAPE 5.18%, shortage MAPE 5.75%, runtime 5 ms; Prophet status ok, `failures: []`, demand MAPE 29.56%, shortage MAPE 34.31%, runtime 33793 ms. Prophet was real but worse on this dataset before adding the minimum-history guard.
- Added `backend/evaluation/run_real_model_acceptance.py` for full real-model business-loop acceptance. Latest `reports/generated/real_model_acceptance.json`: status ok, model `deepseek-v4-flash`, draft id 28, formal order `PO-000028`, duplicate draft reused the same order, model approval attempt did not approve, duplicate human approval reused existing approval, and boundary states were `material_ambiguous`, `no_shortage`, and `no_qualified_suppliers`.
- Hardened AgentLoop so `max_tool_calls_exceeded` persists failed run state and existing tool traces before raising; regression test added.
- Verified model config precedence: `OPENAI_MODEL_USER` is used before `OPENAI_MODEL`; `.env.example` documents `OPENAI_BASE_URL=https://api.deepseek.com` and `OPENAI_MODEL_USER=deepseek-v4-flash` without committing secrets.
- Latest verification: `python -m pytest backend/tests -q` passed 52 tests with 3 opt-in MySQL tests skipped by default; `python -m alembic current` reported `20261011_0006 (head)`; `python -m backend.app.main --help` passed; secret scan found no `sk-...` key in tracked non-agent/report files.
- Prophet diagnostic slice: saved baseline report and SHA-256 hashes under `reports/generated/forecast_diagnostics/baseline_20261011/` before code/config changes. Hashes cover the previous forecast report, raw demand/inventory/material/split/metadata files, and evaluation/seed source files.
- Added read-only audit plus main diagnostic evidence for Prophet error. No direct train/holdout leakage was found in `_build_windows`; dates are sorted, daily rows are continuous, 30-day holdout aggregation is correct, negative Prophet daily predictions are clipped before summing, and shortage uses `max(0, demand + safety_stock - available_supply)`.
- Diagnostic caveats: current backtests use the same static 2026-10-10 inventory snapshot for all historical shortage windows; this is symmetric between models but not a historical inventory series. The declared test period has already been inspected by diagnostics, and only 2026-09-25 through 2026-10-09 remains unused by the 30-day stride, so there is no untouched 30-day final holdout left in the current data.
- Root cause evidence: Prophet underperformance was concentrated in early short-history windows, especially 45-75 training samples, where yearly+weekly Prophet produced extreme 30-day totals. The simulated demand is locally stable with weekly effects, step trend, annual bump, small noise, and intermittent spikes for materials 6/9/10, which makes the last-30-day moving sum unusually strong.
- Added `ProphetForecastConfig` and a 365-sample minimum-history guard. Prophet now reports short-history windows as `insufficient_history` failures instead of counting unstable fits as successful predictions. Validation-grid diagnostics favored the current yearly+weekly config once enough history is present.
- Added `backend/evaluation/run_forecast_diagnostics.py`. Latest outputs: `reports/generated/forecast_diagnostics/forecast_diagnostics.json`, `reports/generated/forecast_diagnostics/forecast_window_diagnostics.csv`, and curves under `reports/generated/forecast_diagnostics/curves/`.
- Latest forecast comparison after the guard: moving average over all 160 windows has demand MAPE 5.18%, shortage MAPE 5.75%, runtime 3 ms. Prophet is `partial`: 50 evaluated windows, 110 `insufficient_history` failures, runtime 9731 ms, evaluated-window demand MAPE 3.04%, shortage MAPE 3.35%, zero actual shortage count 0. This is not a full 160-window Prophet pass and remains a course-metric risk.
- Continued prediction diagnostics after interrupted work. Preserved the existing forecast comparison direction, repaired tests to use a lightweight Prophet fake for structural coverage, and avoided rerunning incomplete output as evidence.
- `backend/evaluation/run_forecast_comparison.py` now reports full 160-window moving average, long-history yearly+weekly Prophet with 50/160 success and explicit 110 failures, moving average recomputed on those same 50 success windows, dynamic Prophet seasonality, and a separate hybrid dynamic-Prophet-or-moving-average strategy. Hybrid reuses dynamic Prophet predictions and falls back only for dynamic Prophet failures, avoiding duplicate Prophet fitting.
- Latest `python -m backend.evaluation.run_forecast_comparison`: full moving average demand MAPE 5.18%, shortage MAPE 5.75%; long-history Prophet successful-window demand MAPE 3.04%, shortage MAPE 3.35%, success 50/160; same-window moving average demand MAPE 6.95%, shortage MAPE 7.66%; dynamic Prophet demand MAPE 4.75%, shortage MAPE 5.34%, success 140/160; hybrid demand MAPE 5.09%, shortage MAPE 5.72%, fallback 20/160 or 12.50%.
- Dynamic Prophet uses weekly-only behavior before the 365-day yearly-seasonality guard and yearly+weekly after that guard. The 365-day threshold is documented as a project engineering strategy for the simulated dataset, not a universal Prophet hard requirement.
- Diagnostics now include `inventory_scope`: experiment type `fixed_inventory_scenario`, snapshot date 2026-10-10, 10 inventory rows, and `can_reconstruct_historical_inventory=false` because there is no dated inventory movement or historical snapshot table.
- Zero-shortage coverage now returns `status=not_applicable` and `coverage_percent=null` when there are no actual zero-shortage samples; tests cover this behavior.
- Latest verification in this slice: `python -m pytest backend/tests/test_forecast_comparison.py -q` passed 5 tests; `python -m pytest backend/tests -q` passed 55 tests with 3 opt-in MySQL tests skipped; `python -m backend.evaluation.run_forecast_comparison`, `python -m backend.evaluation.run_forecast_diagnostics`, `python -m backend.evaluation.run_baseline`, and `python -m backend.app.main --help` all completed. New forecast results are exploratory because the current test split has already been used for diagnostics.
- Forecast strategy was frozen for course delivery as `forecast_strategy_v1_20261011`; do not keep tuning Prophet thresholds, regenerate easier data, or modify frozen labels unless a later task explicitly reopens forecasting.
- Actual service prediction now uses `hybrid_dynamic_prophet_or_moving_average_30d`: dynamic Prophet main path, moving-average fallback for short history or Prophet failures, and explicit metadata for `model_name`, `strategy_type`, `selected_model_name`, `config_version`, `training_range`, `forecast_range`, and `fallback_reason`.
- `get_demand_forecast` now returns full forecast evidence payloads. Agent tool traces persist the full forecast tool output, and Agent-created purchase drafts persist resolved forecast evidence refs/payloads in `purchase_orders.evidence_refs_json`; direct/manual purchase drafts that only provide refs remain compatible with the legacy refs list.
- Added `backend/tests/test_forecast_service_strategy.py`: normal service forecast metadata, short-history fallback, and forecast evidence to purchase draft chain with material 9 package-multiple rounding. Latest focused command passed 3 tests.
- Latest full verification after service integration: `python -m pytest backend/tests -q` passed 58 tests with 3 opt-in MySQL tests skipped; `python -m backend.evaluation.run_forecast_comparison`, `python -m backend.evaluation.run_forecast_diagnostics`, `python -m backend.evaluation.run_baseline`, and `python -m backend.app.main --help` completed.
- Latest real model acceptance after service integration: `python -m backend.evaluation.run_real_model_acceptance` wrote `reports/generated/real_model_acceptance.json` with status ok, first happy-path draft created, human approval approved formal order `PO-000034`, model approval attempt still did not approve, and boundary states `material_ambiguous`, `no_shortage`, and `no_qualified_suppliers`.
- Final evidence packaging note: `reports/generated/` remains ignored by Git but should be reproduced with the documented commands and copied into the course delivery archive, including forecast comparison JSON, forecast diagnostics JSON/CSV/curves/baseline hashes, baseline eval, supplier eval, MySQL report if rerun, and real model acceptance JSON.
- Next task after this slice is minimal frontend development. Use existing signed-token buyer/approver APIs and preserve backend-owned approval, transaction, forecast evidence, and idempotency behavior.

## 2026-10-12

- Re-read `AGENTS.md`, `docs/PROJECT_INDEX.md`, `agent/HANDOFF.md`, and `agent/TASK.md`; Git worktree was clean on `master` before frontend/API changes.
- Added frontend-facing backend APIs without moving business rules to the client: `POST /agent/runs`, `GET /agent/runs`, `GET /agent/runs/{id}`, `GET /agent/runs/{id}/traces`, `GET /purchase-orders`, and `GET /demand-history/{material_id}`.
- Added `backend/tests/test_frontend_api_contract.py` covering Agent run/trace/order approval loop and demand-history chart data. Focused command passed 2 tests.
- Added Vue 3 + TypeScript + Element Plus + ECharts frontend under `frontend/`, with four minimal pages: intelligent procurement, data analysis, procurement approval, and execution records. The frontend uses `/api` proxy in development and bearer tokens from demo login.
- `npm install` created frontend lock/dependencies. `npm run build` passed TypeScript and Vite build; Vite reported a large chunk warning from Element Plus/ECharts. npm audit reported 1 moderate vulnerability; no force upgrade was applied.
- Local browser validation used the in-app Browser at `http://127.0.0.1:5173`. Initial run failed with `provider_http_error:HTTPStatusError` because `OPENAI_MODEL=deepseek-v4-flash` was being sent to the default OpenAI base URL while `OPENAI_BASE_URL` was missing in the server process. Restarting the local backend with `OPENAI_BASE_URL=https://api.deepseek.com` fixed the endpoint configuration.
- Browser validation details: a broad prompt truthfully produced `no_qualified_suppliers` because the model pursued the forecast shortage quantity beyond supplier capacity. An explicit prompt for MAT-001 quantity 120, lead time 20 days, budget 5000 created draft order #1 through real Function Calling; buyer submitted it; approver logged in and approved it; the UI displayed formal order `PO-000001`.
- Data analysis page was browser-checked for real inventory, forecast model/config version, fallback/model notes, chart data, and supplier scoring evidence. Execution records page was checked for both historical runs and tool trace output. Desktop and mobile screenshots showed no framework overlay or app console errors.
- Local `erp_dev.sqlite` was an old `create_all` database without Alembic version state; it lacked `supplier_materials.package_multiple` and newer purchase order columns. For browser demo only, the local SQLite file was patched non-destructively with missing columns and reseeded. This does not replace Alembic/MySQL verification.

## 2026-10-12 Delivery Prep

- Added root `.env` loading for backend app import, Alembic, and real-model acceptance. Existing process variables remain higher priority. Missing `OPENAI_BASE_URL` now returns an explicit non-secret configuration error instead of silently using the wrong provider root.
- FastAPI now honors `DATABASE_URL` for normal startup when no explicit test engine is injected. SQLite URLs still use local schema creation; non-SQLite URLs use SQLAlchemy with `pool_pre_ping`.
- Protected demo reset: `backend.app.db.init_demo_data` requires explicit `--database-url` and rejects database/file names that do not contain `demo`. SQLite demo reset can create schema directly; MySQL demo reset should run Alembic first.
- Resolved frontend `npm audit` moderate issue: direct `echarts@5.6.0` XSS advisory upgraded to `echarts@^6.1.0` without `--force`; final `npm audit --json` reports 0 vulnerabilities and `npm run build` passes.
- Added delivery docs: `docs/DEMO_GUIDE.md`, `docs/DELIVERY_CHECKLIST.md`, and `docs/REPORT_EVIDENCE_INDEX.md`.
- Browser validation on `http://127.0.0.1:5173`: buyer login, real Agent draft creation for material 1 / 120 units / 20 days / budget 5000, buyer submit, approver login, approval, and formal order `PO-000002`. Screenshots saved under `reports/generated/screenshots/`.

## 2026-10-12 Course Acceptance Review

- Per user instruction, performed review only: no business implementation, forecast parameter, frozen label, or delivery submission changes.
- Added `docs/COURSE_ACCEPTANCE_REVIEW.md` with overall conclusion, requirement-to-evidence matrix, issue list, minimal remediation plan, report claim boundaries, and verification log.
- Updated `docs/PROJECT_INDEX.md`, `agent/TASK.md`, and `agent/HANDOFF.md` to point to the acceptance review and to pause before remediation.
- Review conclusion: current project is partial pass, not final submission-ready. Strong evidence exists for deterministic backend behavior, MySQL approval safety, supplier evaluation, reproducible simulated data, frontend build, and hybrid forecast evaluation.
- Blocking items: current real LLM acceptance is not reproducible because `OPENAI_BASE_URL` is missing; formal Word report is not generated; forecast claims must be narrowed to hybrid fixed-inventory evidence rather than pure full-coverage Prophet.
- Verification run: `python -m pytest backend/tests -q` -> 66 passed, 3 skipped; `python -m backend.app.main --help` passed; supplier eval, baseline eval, forecast comparison, and forecast diagnostics completed; MySQL integration rerun with `reports/generated/mysql_integration_review.json` -> 3 passed; `npm --prefix frontend audit --json` -> 0 vulnerabilities; `npm --prefix frontend run build` passed with a large chunk warning.
- Non-writing real-model acceptance check returned `status=failed`, `error=OPENAI_BASE_URL_missing`. Treat the older `reports/generated/real_model_acceptance.json` as stale/inconsistent evidence until rerun with `base_url_configured=true`.

## 2026-10-12 Minimal Acceptance Remediation

- Per user instruction, performed minimal整改 only: no formal Word report, no new feature module, no frozen model parameter changes, and no frozen recommendation label/test tag changes.
- Root cause for old `real_model_acceptance.json` inconsistency: configuration/report drift. The runner reported missing `OPENAI_BASE_URL`, while older provider behavior could still proceed through a provider/default or separately configured process path. New acceptance reports include non-secret `config_sources`, code version, model, base-url configured state, real persisted tool traces, and final status.
- Preserved old real-model report as `reports/generated/real_model_acceptance.previous-20261012-135908.json`; reran real acceptance with non-secret `$env:OPENAI_BASE_URL='https://api.deepseek.com'`. Latest report status is `ok`, model `deepseek-v4-flash`, draft id 41, formal order `PO-000041`, approval remains human/backend-owned, and boundary states are `material_ambiguous`, `no_shortage`, and `no_qualified_suppliers`.
- Unified draft validation in `backend/app/services/purchase_drafts.py`. Agent tools and direct `/purchase-drafts` now use the same service checks: current server forecast evidence, material match, requested quantity within server shortage, recommendation evidence for supplier/material/rounded quantity, active supplier/material relation, capacity, quote, amounts, and idempotency. MOQ/package-multiple rounding remains allowed when evidence supports the rounded order quantity.
- `recommend_suppliers` responses now include a server-verifiable recommendation evidence ref. Agent `create_purchase_draft` accepts current-run sentinels `use_latest_forecast` and `use_latest_recommendation`, but resolves them before calling the shared business service.
- Added minimal object-level read scoping without a full permission platform or schema migration: Agent run owner is stored in `AgentRun.state_json`; Agent-created order ownership is recorded as an `AuditLog(action="created_draft")`. Buyers see only their own runs/traces/orders; approvers see approval-needed/processed orders and associated Agent traces. Cross-buyer guessed run/trace IDs return 404.
- Forecast comparison/diagnostics now explicitly distinguish chronological rolling-window training from leakage caused by using holdout outcomes for tuning. Current forecast evidence remains exploratory and fixed-inventory; pure Prophet coverage and hybrid strategy coverage are reported separately.
- Supplier eval now records `label_definition`, `label_width`, and `top3_definition`; labels and scores were not changed.
- Verification after remediation: touched backend/API suite -> 45 passed; full backend -> 71 passed, 3 skipped; evaluation structure tests -> 7 passed; real model acceptance -> status ok; supplier eval, forecast comparison, and forecast diagnostics regenerated. MySQL专项 was not rerun because no schema, row-lock, transaction, or approval-state behavior changed.

## 2026-10-12 Word Report And Course Delivery Package

- User requested formal Word report and course delivery package using `bc45878` as the reference baseline, with no new business features.
- Re-read `AGENTS.md`, `docs/PROJECT_INDEX.md`, `agent/HANDOFF.md`, `agent/TASK.md`, the original outline `ERP智能采购Agent_开发实施大纲 .md`, `docs/COURSE_ACCEPTANCE_REVIEW.md`, `docs/REPORT_EVIDENCE_INDEX.md`, and current raw evidence under `reports/generated/`.
- Added `scripts/build_course_delivery.py` to reproducibly generate report charts, architecture diagram, Word report, course delivery folder, `PACKAGE_MANIFEST.md`, and `SENSITIVE_SCAN.md` from current files.
- Added `delivery/` to `.gitignore` so generated coursework artifacts stay local and are not committed.
- Generated local package at `delivery/【待填写姓名】ERP课程作业报告/` with Word report `【待填写姓名】ERP课程作业报告.docx` and `源代码和数据集`.
- Report content uses current evidence values from JSON/CSV/PNG files: exploratory fixed-inventory forecast scope, pure Prophet successful windows separated from dynamic Prophet and full hybrid metrics, supplier Top-3 defined as at least one acceptable supplier in the first three, simulated label source/width, real Function Calling traces, and human approval loop.
- Rendered the Word report using `C:\Users\Leezhaoji\Documents\Codex\tools\render-office-windows.cmd -InputPath "<absolute-docx>"`. Final render produced PDF plus 8 page PNGs. Non-fatal LibreOffice/Poppler warnings appeared, but output files existed and were visually inspectable.
- Fixed layout issues found during render QA: removed a blank trailing page caused by a final empty paragraph after the last table, shortened one crowded heading, and avoided a single-row/empty last page.
- Package check found 131 source/evidence files copied, 0 excluded runtime/cache/secret/database files, 0 real suspected secrets, and 4 explained placeholder/test/demo secret-like constants (`.env.example`, `docs/DEMO_GUIDE.md`, runtime config tests, demo auth default).
- Verification for this slice: `python -m py_compile scripts/build_course_delivery.py`; render-and-inspect workflow for all 8 page PNGs; delivery exclusion/sensitive checks.
- Remaining user-fill items: replace `【待填写姓名】` in folder/file name and fill report cover `【待填写：姓名 / 学号 / 班级】`.

## 2026-10-13 Report Formula And Delivery Refinement

- User explicitly limited this round to the course Word report and delivery package: no new system features, no model-parameter changes, no frozen data regeneration, no repeated real LLM call, and no full backtest rerun.
- Checked Git status first; worktree was clean before edits. Read required project entry docs, acceptance/evidence docs, current delivery generator, relevant source, and raw evidence.
- Expanded `scripts/build_course_delivery.py` so the generated Word report includes source-aligned algorithm formulas: Prophet additive trend/seasonality/error explanation, dynamic yearly-seasonality guard, 30-day moving average, available supply, shortage, MOQ/package ceiling, four-metric cost/benefit normalization and weighted score, MAPE zero handling, and Top-3 hit definition.
- Verified inventory evidence: current real-model happy path records only `get_demand_forecast -> recommend_suppliers -> create_purchase_draft` as model-visible tool calls. Source review shows `get_demand_forecast` internally calls `get_inventory_snapshot`, returns `inventory`, `available_supply`, and `inventory_version`, and uses them for shortage/evidence refs. The report now distinguishes model tool calls from tool-internal business operations and does not fabricate a `get_inventory` trace call.
- Corrected report wording: `持出` -> `留出`, MAPE/Top-3 table headers include percent units, label width is natural language, cover production notes were removed, and unknown name/student/class remain concise placeholders.
- Updated delivery builder: added Chinese chart font setup, avoided LibreOffice heading rendering artifacts by using explicit section heading paragraphs, excluded `.tsbuildinfo`, and wrote `git status --short` output instead of prewriting `clean`.
- Regenerated ignored package at `delivery/【待填写姓名】ERP课程作业报告/` and rendered `【待填写姓名】ERP课程作业报告.docx` with the Windows Office wrapper. Latest render produced PDF plus 9 page PNGs. Non-fatal LibreOffice/Poppler dependency/path warnings appeared, but output files existed and were visually inspectable.
- Package check found 130 copied source/evidence files, 0 real suspected secrets, 4 explained placeholder/test/demo constants, and no `.env`, virtualenv, `node_modules`, cache, `.tsbuildinfo`, SQLite/DB snapshot, or nested delivery artifact inside `源代码和数据集`.
- Updated `docs/REPORT_EVIDENCE_INDEX.md`, `docs/DELIVERY_CHECKLIST.md`, `docs/PROJECT_INDEX.md`, `docs/ROADMAP.md`, `agent/TASK.md`, and `agent/HANDOFF.md` for the refined report/package state.

## 2026-10-22 - GitHub initial publication

- User supplied and authorized https://github.com/cesuogaoshou/erp-procurement-agent as the upload target.
- Confirmed the repository was empty and public, with push permission for the connected account.
- Checked 244 historical file blobs for common secret formats and local credential matches; no findings.
- Added origin, renamed local master to main to match the repository default, and pushed all existing main history with upstream tracking.
- Verified local HEAD and remote refs/heads/main both equal 77a09a8aafb02b690a8cc134f97ac42237b89cc1; fetched remote README successfully; tracked working tree remains clean.
- Preserved exclusions for .env, agent/, local databases, reports/generated/, and delivery/. No generated coursework or secret files were uploaded.

## 2026-10-28 - On-machine acceptance

- Executed user-requested local acceptance without business/test code changes, commits, pushes, data reset, forecast tuning, or label changes. Added docs/LOCAL_ACCEPTANCE_20261028.md; overall partial pass.
- Backend: 71 passed, 3 skipped; frontend build passed with large-bundle warning. Real DeepSeek run #58/#59 reused order #43 and produced PO-000043 via role-simulated approval. Chinese browser run #64 created #44; buyer submit and approver approval produced PO-000044, 972.00 yuan. Backend restart preserved run, 4 traces, approved #44 and pending #49; browser then rejected #49.
- Actual opt-in MySQL tests failed 3/3 with forecast_evidence_required because fixture requests still use placeholder recommendation refs without valid forecasts. Keep reports/generated/local_acceptance_20261028/mysql_tests.log as current evidence. Supplemental live API checks independently passed concurrent approval, duplicate idempotency and post-flush rollback; do not relabel the original suite as passing.
- Confirmed missing auth on POST /purchase-drafts: anonymous valid-evidence request returned 200 and created #45. Reported as P1; no fix implemented. API acceptance report: 14 pass, 1 fail. Recommended future repair: buyer auth/creation audit and current evidence setup for MySQL test requests.
- Preserved existing MySQL erp_procurement data; attempted isolated schema creation was denied by current account. Order count 42→49, all new records retained as evidence.
- Repeated frozen baseline/supplier/forecast comparison: shortage MAPE baseline 5.75%, Prophet 3.35% on 50/160, dynamic 5.34% on 140/160, hybrid 5.72% on 160/160 with 20 fallbacks; composite Top-3 100% on frozen/challenge 60+60. Fixed-inventory/exploratory limits unchanged.
- Evidence and 6 screenshots are in ignored reports/generated/local_acceptance_20261028/. Services kept on loopback 5173/8000; current PIDs recorded in services.json. Existing Word still contains personal placeholders; no Word pagination recheck or package regeneration this turn.

## 2026-10-28 - Draft authorization and MySQL remediation acceptance

- Implemented user-authorized P1/P2 and browser reacceptance. main.py now requires signed buyer auth for POST /purchase-drafts, atomically creates order + creator audit, checks creator before replay/submission, and preserves Agent HTTP ownership/single creation audit during replay. Frontend disables role-inapplicable submit/approve/reject buttons. Existing evidence/business services and schema unchanged.
- Added backend/tests/test_draft_authorization.py: 11 signed-token regressions covering anonymous, forged headers, invalid token, wrong role, own create/query/submit/replay, cross-buyer draft/pending access, atomic audit failure rollback, Agent replay ownership/deduplication. Watched original eight cases fail; added Agent regression exposed duplicate audit then passed after fix. Test-only second demo account is removed by monkeypatch; live auth configuration unchanged.
- Updated existing HTTP draft helpers to authenticate. Replaced stale MySQL evidence with current forecast/recommendation setup and both latest markers; added Barrier, narrow ApprovalConflict catch, explicit wrong-version and no-formal-number-after-rollback assertions.
- Final full backend 82 passed/3 opt-in skipped (130.03s); MySQL 3 passed (7.14s); frontend build passed (existing large chunk warning); baseline, main --help and diff whitespace check passed. MySQL report records concurrent #50 one success/one conflict/one record; rollback #51 pending/version2/no formal/0 records; Agent #52/Run65 persists reconnect; duplicate #53 one record; stale/version #54 conflicts.
- Browser real Agent Run66 created #55 (two forecast calls then recommend/create), Run67 created #56 (forecast/recommend/create); buyer submitted both, approver approved PO-000055, backend11252 restarted as30884, snapshots of 2 runs/7 traces/2 orders/API exactly matched, then approver rejected #56 from UI. Creator audits one per order; decisions one per order. Unicode reason preserved correctly (verified with escaped JSON).
- Live HTTP spot checks: anonymous401, forged identity headers401, approver403, buyer same-key #55 replay200; orders56 and creation-audit1 unchanged. No database reset/migration, orders49→56 retained. Snapshot scripts and five inspected PNGs in ignored reports/generated/remediation_acceptance_20261028/. Services left on loopback5173/8000; frontend launcher13220/backend30884.
- Added docs/REMEDIATION_ACCEPTANCE_20261028.md, updated API/project/roadmap/current review status, and annotated the earlier failure report while preserving all original findings. Local handoff/task refreshed. No commit/push or Word/package regeneration; frozen forecasting scope and personal report placeholders remain.
- Independent code review found a route/service lookup interleaving race. Two deterministic tests exposed same-buyer duplicate audit and cross-buyer erroneous200. Added post-service creator check; two tests passed, then final full suite **82 passed/3 skipped in130.03s**. Review confirmed direct-route fix. Final code reload backend29676; repeated HTTP401/403/own-replay200 and refreshed page still shows55approved/56rejected. Prior PID30884 was the explicitly compared restart target; current services.json holds final PID.


## 2026-10-29 - Publish selected databases and historical course package

- User explicitly authorized uploading local databases and delivery package to the existing public GitHub repository.
- Published commit 3e27cc8 on main to https://github.com/cesuogaoshou/erp-procurement-agent; remote push succeeded.
- artifacts/database/2026-10-29 contains a consistent MySQL SQL dump (13 tables/6080 rows) plus online SQLite backups of erp_demo and erp_dev. Temporary migration-check databases were excluded.
- SQLite integrity, dump table/INSERT row counts, archive CRC, all manifest hashes and staged byte preservation passed. Local MySQL account lacks CREATE DATABASE, so isolated restore was not performed; no privileges or source data changed.
- artifacts/delivery contains the existing 2026-10-13 package as a 147-file ZIP; removed 70 renderer-profile/cache files, preserved Word/PDF/9 page PNGs, data/source/evidence and placeholders. Did not regenerate or claim incorporation of October 28 fixes.
- Credential scan included nested DOCX and PDF text and found no known local credential matches or common token/private-key formats. Configuration secrets remain excluded.
- Only artifacts/ plus scoped .gitignore exceptions were committed. All pre-existing backend/frontend/tests/docs changes from October 28 remain uncommitted and preserved.
- New publication scope supersedes earlier instructions that databases/delivery must never be uploaded; runtime root databases, raw delivery working directory, .env and agent/ remain ignored.

## 2026-10-29 - Extreme business acceptance

- User requested actual extreme business acceptance. Ran 63 checks: 53 passed, 10 failed, 6 finding groups. Added docs/EXTREME_ACCEPTANCE_20261029.md and refreshed status docs. No business/test changes, resets, tuning, commits, pushes or package regeneration.
- P1: duplicate material rows accepted 480 units (#63) against shortage406.11/capacity300; missing shared-budget expression/enforcement accepted #64 at1956 from separate1000-budget refs. Approval guards accepted both in explicitly rolled-back MySQL probes. Both invalid drafts subsequently rejected through normal APIs, no committed formal orders.
- P1: read-only Agent actual HTTP/browser500; last recommendation registry entry incorrectly read for shortage_quantity; failed run/traces rolled back. P2: two concurrent same-key creations returned200/500 with one stored order/audit, IntegrityError1062. P2: tool181day/negative qty accepted versus HTTP422; NaN Decimal exception. P2: normal two-material Run85 hit6-call limit; focused87 correctly used remaining28 and stopped in4calls.
- Passed role/auth, HTTP bounds/evidence checks, serial idempotency, approve/reject race, approved/rejected terminal state refusal, response body disconnect/retry, authoritative price/status, browser cancellation/role switch/double-submit65 (version2/one audit), actual low-budget and1day requests.17 real Agent requests; direct-dispatch and transaction probes separately labelled.
- Evidence ignored under reports/generated/extreme_acceptance_20261029/: raw case JSON, SUMMARY.json, CASE_MATRIX.md, server error excerpts, quarantine, scripts/logs and4JPGs. #57 before/after identical; rows57→68. Kept initial false harness string comparison120.0/120.00 report, then corrected numeric comparison and verified DB; did not change app to pass.
- Full pytest/backtest not repeated. Source defects remain unfixed. Prior scoped remediation pass does not imply full business-quality acceptance. NaN model run stopped at ambiguity, and no-write tests do not establish strict schema coverage.

## 2026-10-29 extreme remediation

Read required handoff/acceptance evidence and saved preexisting Git diff before code edits. Added regressions then repaired aggregate quantity/rounding/approval constraints, explicit confirmed whole-order budget, read-only completion and failure-safe trace persistence, narrow idempotency collision recovery with canonical Decimal fingerprints and MySQL current reads, shared local tool models, and bounded multi-material orchestration. Independent review found latest-ref and malformed-replay paths, both repaired with regression evidence. Kept original 63 failure records byte-for-byte (hash manifest), #57 business snapshot unchanged. Real MySQL tests, model runs, browser submit/approve/reject/roles and full backend/frontend checks recorded in new reports/generated/extreme_remediation_20261029. Migration 0007 applied without reset/backfill. No frozen data/labels, forecasting tuning, delivery generation, commit or push. Full dated report docs/EXTREME_REMEDIATION_20261029.md; old conclusions remain history.

Final verification: backend 133 passed / 5 opt-in skipped; RUN_MYSQL_INTEGRATION=1 suite 5 passed; frontend build and CLI help passed; original63/63 rerun and additional current-code HTTP/model smoke5/5. Unknown-budget approval live422 unchanged snapshot; #57 and original hashes rechecked unchanged. Final backend PID file server.pid (loopback8000); frontend5173 retained.

## 2026-10-29 local commit authorization

User requested local commit after accepting remediation delivery. Preserve existing acceptance documentation and include it with the safety fixes, migration and regressions. Recheck code hashes against prior verified evidence and run backend suite before committing. No push, delivery rebuild or database changes in this commit-only turn.

## 2026-10-29 Independent reacceptance

- User requested fresh reacceptance. On source snapshot c7004b4, reran original63 with explicit valid confirmed budgets and specific business-error assertions; all63 passed.8 extra checks passed,71/71 total. Fresh backend133pass/5skip; realMySQL5pass; frontend build and CLIhelp pass. Raw evidence and6JPGs ignored under reports/generated/reacceptance_20261029_independent/, report docs/REACCEPTANCE_20261029.md.
- No product/test source edits, reset/migration/tuning, commit/push or package generation. Source hashes/original failure-file hashes unchanged; user57 unchanged. Rows132→150 including MySQL controls.
- G1aggregate480 blocked specific shortage error; G2amount1956/budget1000 blocked specific order budget error, not missing-field422. Transaction-local old63/64 clones with explicit budgets rejected at approval and rolled back. Additional320/cap300 blocked,9+9 MOQ20 rounds once, historicalNULL budget refuses approval without changing57.
- True model readonly142 and browser150 complete with2traces/noorder; ordinary shared1000 Run146 noorder; ordinary5000 Run148 creates175 at1956 in5calls. No confirmed budget149 noorder. Concurrent same-key both200/1order/1audit, changed payload409. Browser cancel170 no changes, double-submit175 oneaudit/version2;170 approvedPO-000170,175 rejected. Restart51992→44768 preserves4orders/2runs/7traces and budget values exactly; UI refreshed verified. Keep backend44768/8000, frontend5173.
- Caveat: invalid natural-language quantities return completed/no calls/no orders; hard validation independently verified, but explanatory UI text remains improvement. No stress/blackout, full forecast evaluation, Word/package QA, or cross-process LangGraph checkpoint claim. No new commit/push authorized in this turn.

## 2026-10-29 Nontechnical natural-language acceptance

User rejected technical-ID acceptance prompts and requested normal/extreme cases for nontechnical users plus execution.19 actual real-model requests,16HTTP/3browser, used only Chinese business phrases.19/19 request/order guards,6/6 browser workflow checks;3/3 representative pages failed clarity. Overall partial pass. See docs/NATURAL_LANGUAGE_ACCEPTANCE_20261029.md and ignored reports/generated/natural_language_acceptance_20261029/. Pure names resolve correctly; Chinese120/100 and last correction80 work. Budgets100/1000,1day delivery, missing/nonexistent material,zero/negative/hugeqty,MOQ-no-extra,skipapproval,no budget and conflicting budget did not produce an invalid order. But completed/no follow-up, untranslated status/JSON, order material1, absent approval details and raw expiry error block nontechnical-user quality.182approved810 PO-000182;179rejected1956;178/180/181drafts; rows150→155; user57 and source hashes unchanged. No source fix/regression rerun/reset/commit/push/package work. Prior71/71 was engineering scope only. Initial finalizer audit-label mismatch corrected to existing submitted_for_approval with first outputs preserved, not a business failure.

## 2026-10-29 自然语言交互修复及真实复验

按用户要求修复业务反馈、澄清确认、草稿/审批明细、中文状态/错误；保存模型文字但后端事实主导。新增capture_request，复用现有run.state_json；后端独立核对原文及每次后续工具的物料/数量/交期和加购；无迁移。首次浏览器发现E05误把零当名称、E09停单但无预算原因，保留初次证据后新增红绿回归修复。只读代码审查补出并修复模糊替换/明天延至20天/单价历史预算误冲突，审查复核通过。

最新完整后端163/6skip、独立MySQL6、新反馈30（已包含）、构建/help/diff-check通过；模型deepseek-v4-flash，21不同自然语言用例四维全部通过（含原19句），页面流程12、接口11全部通过。原句/补充共迭代32次+隔离过期恢复1次真实模型，不把重复计算成通过数。195冲突测试已驳回，205双物料已驳回，206/207草稿，208已批准810/PO-000208；本轮全部新订单29（含MySQL）及审计保留。取消205完整快照相同，重复提交/决定无重复审计，错误版本409、越权403、匿名401；真实过时页面409有中文刷新提示并恢复，195快照不变。

隔离过期夹具首令牌签名有效但已过期，真实401后输入预算保留，二次登录再调用模型成功。测试静态服务器Windows .js MIME初次text/plain空白，修正application/javascript并换新端口避免缓存；两个夹具已停止。生产Vite未受影响。

证据/红绿记录/逐条截图在reports/generated/nl_remediation_20261029，报告docs/NATURAL_LANGUAGE_REACCEPTANCE_20261029.md。订单57、冻结源码/数据文件、旧证据散列不变；初始文档修改保留，HEAD c7004b4未变，无提交推送清库调参包重建。

截图QA补记：少量即时弹窗截图先于浏览器绘制；保留旧图，直接CDP补拍并目视核对待审批211（只读）、已批准208和已驳回205明细。报告已区分批准前DOM与批准后补拍，不伪称旧状态。所有订单未因补拍发生写入。

## 2026-10-29 Independent post-remediation natural-language acceptance

User requested acceptance. New docs/INDEPENDENT_NL_ACCEPTANCE_20261029.md: PARTIAL PASS. Original21 real-model HTTP cases pass; extra5 expressions2pass/3fail (20天内交付/两周内到货 rejected,5,000元 read as0). Wrong-model argument fault injection accepts swapped per-material120/80, omitted material, readonly misclassification into drafts;3 rolled back/IDs222-224 absent,2 controls rejected. This is fault injection, not spontaneous model errors. Root: source numeric membership without item binding/completeness/purchase-intent check; downstream validates captured request only.27HTTP attempts/26distinct cases (E10 collector retry)+3browser calls. Browser zero/normal pass,交付 fails. Workflow7/7 and permission/version3/3;227approved810 PO-000227,219rejected1956, cancel full snapshot unchanged. Fresh163pytest/6skip, MySQL6, build/help/diff pass. Source/data/previous NL evidence hashes and full user57 unchanged; rows184→200 (9real-request drafts incl retry,7MySQL). No source fixes/reset/migration/tuning/commit/push/package rebuild. Preserve previous uncommitted remediation. Evidence reports/generated/nl_independent_20261029 incl initial collector404/KeyError logs and corrected list API collection, no lowered assertions. See latest handoff for exact scope.


## 最新：原文需求绑定整改与真实复验（2026-10-29）

**本轮三组缺陷通过（明确范围）**。见 `docs/NL_BINDING_REMEDIATION_20261029.md`；旧独立“部分通过”报告保留原样。服务端独立绑定物料全集/逐项数量/只分析限制，保存有效需求；不可靠对应时完整中文清单明确确认，确认绑定原文/预算/记录/所属人，一次消费；推荐、草稿和审批从原执行记录复核。交付/周单位（两周14天）及合法千分金额已修复，并补历史数量/预算上下文、单位与禁写表达边界。

最终实际验证：后端197 passed / 6默认MySQL跳过；单独真实MySQL6 passed；类型/构建、CLI、diff通过；原21+新增5真实模型接口26/26，最终浏览器8次真实模型业务运行、5种隔离错误模型页面拦截、7个MySQL回滚链探针（6拒绝+1正确对照）、6项实时拒绝/快照检查通过。完整清单明确确认后草稿282（120件轴承+80件外壳，1628元）经人工批准PO-000282；278取消驳回完整快照不变后已驳回；281待审批。

证据 `reports/generated/nl_binding_remediation_20261029/final/`，此前迭代仍在父目录。总62次真实模型业务运行=初轮26接口+2页面+最终26接口+8页面/确认，不当作62个不同用例或底层模型HTTP次数。模拟错误模型参数不计入真实模型请求。57完整快照、冻结数据/预测源码和旧三轮自然语言证据散列一致；错误探针事务回滚。旧服务日志追加尾部另存，本轮基线新结果另存，旧证据字节及已跟踪基线内容已保护。

未提交、推送、清库、迁移、调参或重建交付包。主后端67360/8000及前端5173继续运行，隔离8001夹具已停。限制：复杂自然语言保守确认/追问；单供应商单草稿、演示账号、固定库存、无外部采购与历史订单不回填新锚点。后续仅按用户新任务继续，不用本轮范围结论扩张为课程/生产全部通过。


## 最终：需求绑定整改与复验通过（2026-10-29）

本轮三组缺陷已关闭，最终报告 `docs/NL_BINDING_FINAL_REACCEPTANCE_20261029.md`，证据 `reports/generated/nl_binding_remediation_20261029/final_v3/`。中间197/201/202成绩、条件句/只读推荐缺口及模型幂等键冲突保留记录，不冒充最终结果。

最新实际执行：完整后端203 passed / 6默认MySQL跳过；单独真实MySQL6 passed；前端类型/构建、CLI和diff通过；最终原21+新增5真实模型接口26/26；8次真实页面/确认运行、9个MySQL回滚链探针（8拒绝+1正确对照）、7种隔离页面故障、6项实时拒绝/快照检查通过。最终确认369→修改失效→370明确确认→371草稿326（轴承120+外壳80，1628元），人工批准PO-000326；321取消驳回快照不变后已驳回；324待审批。

模型候选独立绑定原文全集/逐项数量/单位/只分析/交期/预算，有效需求持久化并锚定原始运行。只读中明确条件同样约束推荐；普通前置“如果”不解除禁写。草稿幂等键由服务端运行ID确定，同运行重试只产生一个草稿，直接API幂等协议保留；后续重放不改变最初来源。两周14天、交付等表达及5,000/非法金额/单价历史语境均已覆盖。

全程124次真实模型业务运行=104接口（4轮各26）+20页面/确认，最终只计26不同接口用例+8页面/确认；模拟注入与MySQL Mock不算真实模型请求。57完整快照、冻结数据/预测源码及旧三轮证据散列一致，错误探针全部回滚。没有提交、推送、清库、迁移、调参或重建交付包。

后端62980/8000和原前端5173保持运行，隔离8001已停。保留复杂NL保守确认、单供应商、演示账号、固定库存、无外部采购与不回填历史锚点的既有边界；不同新AgentRun仍是新业务执行，未新增跨运行客户端去重。下一步仅按用户新任务继续。
