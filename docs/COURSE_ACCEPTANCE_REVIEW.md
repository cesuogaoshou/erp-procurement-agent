# Course Acceptance Review

> Independent binding reacceptance (2026-10-29), d1e1524: prior3 defect groups passed fresh checks; overall **partial pass**, see `BINDING_INDEPENDENT_ACCEPTANCE_20261029.md`. Fresh203 backend/6skip, MySQL6, build/help pass.26 real-model HTTP cases passed25; N03's month timeframe is wrongly bound as purchase quantity1 and supplier analysis is blocked (HTTP376/browser383, deterministic month/30days control).9 tool-chain probes,2 anchored-approval rollback probes,7 live rejection checks and10 UI confirmation/workflow checks passed. No source edits. A safe no-order reply is insufficient to pass the requested read-only analysis.

> Independent natural-language acceptance (2026-10-29): **partial pass**. See `INDEPENDENT_NL_ACCEPTANCE_20261029.md`. Fresh163 backend passed/6 default skips, realMySQL6 passed, build/help passed. Original21 HTTP replays passed; extra5 expressions passed2/failed3. Wrong-model fault injection accepted3 invalid interpretations into transaction-local drafts, all rolled back;2 controls correctly rejected. UI workflow7/7 and live permission/version3/3 passed. New blockers are per-material quantity/completeness/purchase-intent alignment and common delivery/week/thousands-format parsing. No business source edits; previous scoped passes are preserved as historical evidence.

> Nontechnical-user business acceptance (2026-10-29): **partial pass**, see `NATURAL_LANGUAGE_ACCEPTANCE_20261029.md`.19 pure-Chinese real-model requests passed this run's order/constraint checks and6 browser workflow checks passed, but all3 representative result-page reviews failed usability checks. Missing Chinese outcomes, clarification, material names and approval details prevent complete business-quality sign-off. Existing engineering passes below remain scoped; this turn made no business fixes.

> Independent rerun (2026-10-29): current code c7004b4 passed original63/63 plus8 extra checks, fresh backend133pass/5skip, realMySQL5pass, build/help and browser/restart verification. See `REACCEPTANCE_20261029.md` for evidence and scope. Existing forecast/Word/delivery boundaries remain, and invalid natural-language input explanations still need improvement. Historical failure records below were not overwritten.

> Extreme remediation (2026-10-29): see `EXTREME_REMEDIATION_20261029.md`. All six findings below were repaired; backend 133 passed/5 opt-in skipped, real MySQL 5 passed, original extreme cases 63/63 passed. Original failure evidence and order #57 are preserved. This engineering remediation does not change frozen forecasting limitations or refresh the course delivery package.

> Expanded business-quality acceptance (2026-10-29): 53/63 checks passed; 10 failures map to 6 findings. See `EXTREME_ACCEPTANCE_20261029.md` for aggregate quantity/budget gaps, read-only/concurrent-create 500s, internal schema mismatch and multi-material limits. No business fixes in that acceptance turn. Earlier scoped authentication remediation pass is not full business-quality sign-off.

> Latest remediation acceptance (2026-10-28): see `REMEDIATION_ACCEPTANCE_20261028.md`. P1 draft auth/creator ownership and P2 stale MySQL evidence are fixed and revalidated: 82 backend tests passed/3 default skipped, all 3 opt-in MySQL tests passed, frontend build passed, browser approved PO-000055 and rejected #56 after backend restart with identical persisted runs/traces/orders before continuing. The earlier partial-pass discovery is preserved in `LOCAL_ACCEPTANCE_20261028.md`. This closes the requested engineering blockers; forecasting scope limitations, personal report fields and an unchanged delivery package remain. Older statements below, including missing-report status and historical test counts, must be interpreted at their recorded dates.

Review date: 2026-10-12  
Reference baseline: `39b749f chore: prepare delivery reproducibility`  
Scope: acceptance review only. No business behavior, model parameters, frozen labels, or source algorithms were changed.

## 1. Overall Conclusion

Current project status: **partially meets the course requirements, but should not be submitted as "fully accepted" yet**.

The system has strong evidence for deterministic procurement services, supplier scoring, purchase draft creation, human approval, audit logs, MySQL transaction/concurrency behavior, reproducible simulated ERP data, and frontend build readiness. However, three acceptance boundaries remain important:

1. **Real LLM Agent evidence is currently insufficient in this environment.** The code supports OpenAI-compatible Function Calling and the historical report records a real run, but this review reran the real-model acceptance path without writing the report file and got `OPENAI_BASE_URL_missing`. The existing `reports/generated/real_model_acceptance.json` also contains an internal inconsistency: `base_url_configured=false` while `status=ok`.
2. **Forecast MAPE evidence must be stated narrowly.** The full service strategy is hybrid dynamic Prophet plus moving-average fallback, not pure Prophet. Dynamic Prophet succeeds on 140/160 windows with shortage MAPE 5.34%; the hybrid covers 160/160 with shortage MAPE 5.72%; pure long-history Prophet only covers 50/160 windows. Shortage evaluation uses a fixed 2026-10-10 inventory snapshot, not historical inventory snapshots.
3. **Formal Word report is not generated yet.** The project has report outline/evidence docs, but the instructor-required Word artifact remains pending and cannot be claimed complete.

Recommended acceptance stance: **course-demo ready after fixing/revalidating real LLM configuration and writing the Word report; forecasting claim should be "hybrid strategy under fixed-inventory rolling backtest achieved <8% shortage MAPE" rather than "pure Prophet fully passed."**

## 2. Requirement Acceptance Matrix

| Requirement | Implementation location | Verification method | Actual evidence | Conclusion |
| --- | --- | --- | --- | --- |
| LLM understands natural-language procurement instruction and orchestrates Function Calling | `backend/app/services/agent_provider.py`, `backend/app/services/agent_loop.py`, `backend/app/services/agent_tools.py`, `backend/app/services/langgraph_runner.py`, `backend/app/main.py` | Source review; provider/tool tests; real acceptance dry rerun without writing report | Tool schemas are real and exclude approval tools. Agent loop persists runs/traces and lets provider choose next tool. Current real acceptance rerun returned `OPENAI_BASE_URL_missing`; old `real_model_acceptance.json` says `status=ok` but also `base_url_configured=false`. | **Evidence insufficient** |
| Agent is not a fixed script pretending to be an Agent | `AgentLoop.run()` calls `provider.next_tool_call()` per step; observations are fed back; `ToolTrace` persists each call | Source review; `python -m pytest backend/tests -q`; trace report inspection | Tests cover provider tool choices, blocked approval tool attempts, tool errors, call limits, and persisted traces. Historical real trace has variable tool sequence including repeated inventory/forecast calls, but current real LLM config is not reproducible. | **Partial pass** |
| Workflow checks inventory, forecast, supplier recommendation, then creates draft | `agent_tools.py` tools: `get_inventory`, `get_demand_forecast`, `recommend_suppliers`, `create_purchase_draft`; `purchase_drafts.py` | Tests and historical trace review | Tool surface supports the sequence and historical report includes these calls. Server validates forecast evidence before draft creation. | **Partial pass** |
| Approval tools are not exposed to model | `build_agent_tools()` in `agent_tools.py`; provider schema tests | Source review; `backend/tests/test_agent_loop.py`; `backend/tests/test_provider_and_config.py` | Registered tools are list/resolve/inventory/forecast/recommend/create draft only. Tests assert no approve/reject tools and reject provider attempts. | **Pass** |
| Server owns SQL, calculations, scoring, permissions, approvals, transactions, and idempotency | `services/`, `algorithms/`, `approvals.py`, `purchase_drafts.py`, `recommendation.py` | Source review; backend tests; MySQL integration rerun | `python -m pytest backend/tests -q` -> 66 passed, 3 skipped. MySQL integration rerun with isolated report path -> 3 passed. | **Pass** |
| Role/auth checks and human confirmation | `main.py` auth dependency; `auth.py`; `approvals.py` | Source review; auth/approval tests | Buyer submits; approver approves/rejects. Body actor fields are ignored. Buyer token cannot approve even with forged headers. | **Pass** |
| Approval transaction, row lock, idempotency, stale/concurrent conflict | `approvals.py`; `backend/tests/test_mysql_integration.py` | MySQL integration rerun | `RUN_MYSQL_INTEGRATION=1` with `MYSQL_INTEGRATION_REPORT_PATH=reports/generated/mysql_integration_review.json` -> 3 passed. Report covers one approved outcome plus one conflict, duplicate idempotency, rollback, and stale-session conflict. | **Pass** |
| Business validation: amount, MOQ, package multiple, capacity, quote validity | `purchase_drafts.py`, `approvals.py`, `recommendation.py` | Source review; tests | Draft rounds quantity by MOQ/package multiple; approval revalidates current supplier relation, active supplier, capacity, quote, line amount, and total amount. | **Pass** |
| Budget and lead-time/capacity constraints in supplier recommendation | `recommendation.py` | Source review; recommendation tests/eval | Recommendation filters inactive supplier, wrong material, MOQ, lead time, capacity, and budget before scoring. | **Pass** |
| Evidence validity for draft creation | `agent_tools._validate_forecast_evidence()`, `purchase_drafts.py` | Source review; agent persistence/edge tests | Agent draft tool requires forecast evidence and rejects quantity above server shortage. Direct `/purchase-drafts` requires evidence refs but does not fully validate semantic recommendation evidence. | **Partial pass** |
| Trace/order/approval APIs avoid unauthorized access | `main.py` list/get endpoints | Source review | Write actions are role-gated. Read/list endpoints require authentication, but do not filter runs/orders by actor or role and have no object-level authorization. Course demo may accept this, but it is not strong ERP access control. | **Partial pass** |
| Material shortage prediction uses Prophet/LSTM | `forecasting.py`; `run_forecast_comparison.py`; `run_forecast_diagnostics.py` | Source review; forecast comparison/diagnostics rerun | Service strategy is `hybrid_dynamic_prophet_or_moving_average_30d`: dynamic Prophet main path, moving-average fallback. No LSTM by design. | **Partial pass** |
| Shortage MAPE < 8% | `reports/generated/forecast_comparison.json`, `forecast_diagnostics.json` | Reran `python -m backend.evaluation.run_forecast_comparison` and diagnostics | Moving average: shortage MAPE 5.75% on 160/160. Dynamic Prophet: 5.34% on 140/160. Hybrid service: 5.72% on 160/160 with 20 fallbacks. Long-history Prophet: 3.35% on only 50/160. Fixed-inventory scenario, not historical inventory backtest. | **Partial pass** |
| No future leakage in forecast backtest | `run_forecast_comparison.py`, `run_forecast_diagnostics.py` | Source review; diagnostics rerun | Train dates precede holdout, 30-day holdout length and continuity checks pass. But diagnostics also report declared test windows have already been inspected and 10 windows train into the declared test period. | **Partial pass** |
| MAPE zero handling | `evaluation/metrics.py`; diagnostics JSON | Source review; tests; report inspection | Metrics exclude zero actuals from MAPE and report positive/zero counts and coverage. Current shortage samples have zero actual count 0. | **Pass** |
| Supplier scoring uses price, delivery, quality, complaint with weights | `recommendation.py`, `recommendations.py` | Source review; unit tests/eval | Defaults: price 0.35, delivery 0.30, quality 0.25, complaint 0.10. Price/complaint are cost metrics; delivery/quality are benefit metrics. | **Pass** |
| Supplier recommendation Top-3 hit rate >= 85% | `supplier_recommendation.py`, `reports/generated/supplier_eval.json` | Reran `python -m backend.evaluation.run_supplier_eval` | Frozen 60 cases: composite 100%, price baseline 93.33%. Challenge 60 cases: composite 100%, price baseline 95.00%. Top-3 means at least one acceptable supplier hit. | **Pass with limitation** |
| Recommendation labels independent from tested formula | `supplier_recommendation.py`, `recommendation_cases.csv`, `recommendation_challenge_cases.csv` | Source review; generated result review | Labels use scenario threshold rules, not the weighted composite formula. They are still derived from the same simulated supplier attributes and are not human/real-world independent labels. | **Partial pass** |
| Public ERP data or self-built simulated ERP database | `backend/app/services/seed.py`, `data/raw/*.csv`, `docs/DATA_DICTIONARY.md` | Source review; seed export tests; data metadata | Seed `20261010`, 10 materials, 10 suppliers, 5400 demand rows, inventory/supplier/performance CSVs and metadata are present. | **Pass** |
| Dataset reproducibility and CSV/database consistency | `seed.py`, `seed_export.py`, `test_seed_export.py`, `data/raw/generation_metadata.json` | Source review; tests | Deterministic seed and export scripts exist; tests cover export shape. Full CSV-vs-live-MySQL equivalence was not rerun in this review beyond integration seed behavior. | **Partial pass** |
| Autonomous contribution | Custom simulated ERP dataset; supplier scoring/evaluation; hybrid forecast strategy; approval safety design | Source and doc review | Clear self-built data and scenario-specific evaluation. No evidence of copying an open-source ERP system. | **Pass** |
| Minimum startup/reproducibility | `README.md`, `docs/DEMO_GUIDE.md`, `docs/DELIVERY_CHECKLIST.md`, `.env.example` | Ran selected commands | Backend tests/evals and frontend build run. Real LLM startup currently blocked by missing `OPENAI_BASE_URL`. | **Partial pass** |
| Frontend four pages use real API/auth/error/model fallback display | `frontend/src/App.vue`, `frontend/src/api.ts` | Source review; `npm audit`; `npm run build`; screenshots | Four pages exist, use bearer auth, show errors/traces and forecast fallback/model metadata. Browser loop was not rerun this review; existing screenshots are from prior run. | **Partial pass** |
| Source, dataset, dependencies, migrations, eval results, screenshots, report materials deliverable | Repo layout, `data/raw/`, `requirements.txt`, `frontend/package-lock.json`, `backend/alembic`, `reports/generated/`, docs | Source review; verification commands | Most deliverables exist; generated reports are ignored by Git and must be packaged manually. Formal Word report is not generated. | **Partial pass** |
| At least 4-page Word report with implementation process and steps | `docs/REPORT_EVIDENCE_INDEX.md` | Artifact review | Outline/evidence index exists; Word `.docx` report is not present. | **Not passed** |

## 3. Key Findings

### Blocking Course Acceptance

1. **Current real LLM acceptance is blocked by configuration.**  
   Current environment has `OPENAI_API_KEY` and `OPENAI_MODEL=deepseek-v4-flash`, but no `OPENAI_BASE_URL`. A non-writing rerun of `run_acceptance()` returned `status=failed`, `error=OPENAI_BASE_URL_missing`. Reconfigure and rerun `python -m backend.evaluation.run_real_model_acceptance`, then ensure the report shows `base_url_configured=true`, `status=ok`, and real tool calls.

2. **Formal Word report is missing.**  
   `docs/REPORT_EVIDENCE_INDEX.md` is only an outline/evidence map. The course requires a Word report of at least 4 pages; this cannot be claimed complete yet.

3. **Forecast claim must be narrowed before submission.**  
   The service passes the numeric threshold only as a hybrid operational strategy over fixed-inventory windows. Pure long-history Prophet is not full-coverage, and dynamic Prophet excludes 20 failed windows. A report claiming "Prophet shortage MAPE < 8% on all samples" would be inaccurate.

### Affects Experiment Persuasiveness

1. **Forecast test split is no longer untouched.**  
   Diagnostics report already-inspected windows, test overlap counts, and training reaching into declared test period for 10 windows.

2. **Shortage backtest uses static inventory.**  
   There is no historical inventory snapshot/movement table, so shortage MAPE is a fixed-inventory scenario rather than a true historical shortage backtest.

3. **Supplier Top-3 metric is lenient.**  
   It counts a hit when any acceptable supplier appears in Top-3. Several label sets have width greater than 1, up to 5 in frozen cases. The 100% result is valid for this definition, but not equivalent to exact best-supplier ranking.

4. **Labels are simulated-rule labels.**  
   They are not the same weighted scoring formula, which is good, but they are generated from the same simulated attributes and should not be presented as real human labels.

5. **Read APIs have limited object-level authorization.**  
   Listing orders/runs/traces requires login but is not scoped to user ownership or role. Acceptable for a course demo only if documented.

6. **Existing real-model JSON is stale or internally inconsistent.**  
   The historical report says `base_url_configured=false` and `status=ok`; current code would fail in that state. Treat it as a clue, not as current acceptance evidence.

### Optional Improvements

1. Add object-level read filtering for `/purchase-orders`, `/agent/runs`, and `/agent/runs/{id}/traces`.
2. Add a historical inventory snapshot table and rerun shortage backtests on time-appropriate inventory.
3. Add a final frozen holdout dataset or new seed split not used during diagnostics.
4. Add stricter recommendation metrics such as MRR/NDCG/exact best-supplier hit in addition to Top-3 any-label hit.
5. Code-split frontend dependencies to reduce the large Vite bundle warning.

## 4. Minimal Remediation Plan

| Priority | Remediation | Acceptance standard |
| --- | --- | --- |
| P0 | Restore real LLM config and rerun real acceptance | `OPENAI_BASE_URL` configured to the intended OpenAI-compatible endpoint; `python -m backend.evaluation.run_real_model_acceptance` writes `status=ok`, `base_url_configured=true`, real tool calls including forecast/recommend/draft, model approval attempt does not approve, boundary cases pass. |
| P0 | Generate the formal Word report | `.docx` with at least 4 pages, includes implementation steps, architecture, data, forecast/recommendation experiments, Agent/tool trace, approval safety, screenshots, limitations, and reproduction commands. |
| P0 | Rewrite forecast claims accurately | Report states: hybrid service strategy achieved 5.72% shortage MAPE on 160 fixed-inventory rolling windows; dynamic Prophet achieved 5.34% on 140 successful windows; long-history Prophet only 50/160; fixed inventory and inspected split limitations are explicit. |
| P1 | Package generated evidence | Delivery package includes `reports/generated/` JSON/CSV/PNG evidence, screenshots, source, `data/raw/`, dependency locks, migrations, `.env.example`, and no secrets. |
| P1 | Rerun final verification before packaging | Backend tests, baseline, supplier eval, forecast comparison, forecast diagnostics, real model acceptance, MySQL integration, npm audit, and frontend build all pass or are explicitly marked not executed with reason. |
| P2 | Add object-level read authorization or document demo limitation | Either implement scoped reads or state clearly that demo read APIs require login but are not production multi-tenant authorization. |

## 5. What Can and Cannot Be Claimed in the Report

Can claim:

- The project implements a Python/FastAPI ERP procurement decision demo with SQLAlchemy models, Alembic migrations, simulated ERP data, inventory lookup, shortage forecast, supplier recommendation, draft creation, human approval, audit logs, and a Vue frontend.
- Backend services, not the LLM, calculate shortage, scores, prices, amounts, MOQ/package rounding, approval validation, idempotency, and transactions.
- Supplier recommendation combines historical price, on-time delivery, quality acceptance, and complaint rate with normalized weighted scoring.
- Supplier Top-3 hit rate is 100% on the current frozen/challenge simulated cases under the project's "any acceptable supplier in Top-3" definition.
- MySQL integration tests passed in this review for concurrent approval, duplicate approval idempotency, stale-session conflict, rollback, and persisted Agent trace/order recovery.
- Forecasting uses dynamic Prophet as main model and moving-average fallback, and the full hybrid fixed-inventory rolling backtest has shortage MAPE 5.72%.
- The project has a self-built simulated ERP procurement dataset and scenario-specific evaluation rules.

Cannot claim yet:

- Do not claim the current environment has a passing real LLM run. This review found `OPENAI_BASE_URL_missing`.
- Do not claim pure Prophet covers all windows with MAPE < 8%.
- Do not claim fully untouched independent final-test forecast evidence.
- Do not claim true historical inventory shortage backtesting.
- Do not claim production-grade ERP identity/authorization or multi-tenant read isolation.
- Do not claim the Word report deliverable is complete.
- Do not claim external supplier integration, payment, email, real purchase execution, RAG, MCP, multi-agent, or LSTM implementation.

## 6. Verification Run in This Review

Executed:

```powershell
git status --short
python -m pytest backend/tests -q
python -m backend.app.main --help
python -m backend.evaluation.run_supplier_eval
python -m backend.evaluation.run_baseline
python -m backend.evaluation.run_forecast_comparison
python -m backend.evaluation.run_forecast_diagnostics
$env:RUN_MYSQL_INTEGRATION='1'; $env:MYSQL_INTEGRATION_REPORT_PATH='reports/generated/mysql_integration_review.json'; python -m pytest backend/tests/test_mysql_integration.py -q
npm --prefix frontend audit --json
npm --prefix frontend run build
```

Results:

- Git status was clean before review work.
- Backend tests: `66 passed, 3 skipped`.
- App help: passed.
- Supplier eval: regenerated `reports/generated/supplier_eval.json`; frozen composite Top-3 100%, challenge composite Top-3 100%.
- Baseline eval: regenerated `reports/generated/baseline_eval.json`; demand MAPE 5.18%, shortage MAPE 5.75%.
- Forecast comparison: regenerated `reports/generated/forecast_comparison.json`; hybrid shortage MAPE 5.72%, dynamic Prophet shortage MAPE 5.34% on 140/160, long-history Prophet 50/160.
- Forecast diagnostics: regenerated diagnostics JSON/CSV/curves; implementation checks had no issues; inventory scope remains fixed-inventory scenario.
- MySQL integration: `3 passed`; wrote `reports/generated/mysql_integration_review.json`.
- npm audit: 0 vulnerabilities.
- Frontend build: passed; Vite warned about a large chunk.
- Real model acceptance check without writing report: failed with `OPENAI_BASE_URL_missing`.

Not executed:

- Browser end-to-end loop was not rerun in this review. Existing screenshots remain prior evidence.
- Formal Word report generation was not started by instruction.
- No Git commit, push, or course submission was performed.

## 7. Minimal Remediation Update

Remediation date: 2026-10-12  
Scope: minimal code/reporting整改 only. No formal Word report was generated, no new feature module was added, frozen forecast parameters and frozen recommendation labels were not changed, and course submission was not performed.

### Resolved Items

1. **Real LLM configuration evidence is reproducible again.**  
   Root cause: the old report's `base_url_configured=false` with `status=ok` came from configuration/reporting drift. The runner reported whether `OPENAI_BASE_URL` was present in its environment, while earlier provider behavior could still proceed through a provider default or separately configured process path.  
   Fix: root `.env` loading now records non-secret config sources while preserving process-environment priority; real acceptance reports `config_sources`, code version, dirty state, model, base URL configured state, real persisted tool traces, and final approval state. A missing base URL now consistently fails with `OPENAI_BASE_URL_missing`.  
   Evidence: the old report was preserved as `reports/generated/real_model_acceptance.previous-20261012-135908.json`; rerun with `OPENAI_BASE_URL=https://api.deepseek.com` wrote `reports/generated/real_model_acceptance.json` with `status=ok`, `base_url_configured=true`, model `deepseek-v4-flash`, real Function Calling traces, draft `purchase_order_id=41`, human approval to `PO-000041`, and boundary states `material_ambiguous`, `no_shortage`, and `no_qualified_suppliers`. No secret value is printed in the report.

2. **Draft validation is unified between Agent tool and direct `/purchase-drafts`.**  
   Current rule: requested quantity must be positive and within the server forecast shortage; MOQ/package-multiple rounding remains allowed when backed by current forecast evidence and recommendation evidence for the rounded order quantity.  
   Fix: `create_purchase_draft()` now performs shared forecast/ref validation, recommendation evidence validation, supplier/material validation, capacity check, quote/amount calculation, and evidence persistence. Agent tools now resolve `use_latest_forecast` and `use_latest_recommendation` to concrete server-issued refs before calling the same service. Direct recommendation API responses now include a server-verifiable `evidence_ref`.  
   Evidence: tests reject forged forecast refs, wrong-supplier recommendation refs, missing evidence, and forecast overbuy while preserving MOQ/package rounding.

3. **Minimal object-level read access was added.**  
   Fix: buyer-created Agent runs are marked in persisted run state; Agent-created draft orders get a creation audit entry. Buyer read/list endpoints now return only their own runs, traces, and orders. Approvers can read orders requiring/after approval and associated Agent traces, but cannot use model tools to approve. Direct guessed run/trace IDs from another buyer return 404.  
   Evidence: `backend/tests/test_frontend_api_contract.py::test_read_apis_scope_runs_traces_and_orders_by_buyer_owner_and_approver_need` covers cross-buyer list/detail/trace denial plus approver evidence access.

4. **Forecast and recommendation explanations were corrected in generated reports.**  
   Fix: forecast comparison/diagnostics now explicitly distinguish chronological rolling-window training from using holdout outcomes for tuning. They also mark the current evidence as exploratory fixed-inventory evidence and keep pure Prophet coverage separate from the full hybrid strategy. Supplier evaluation now records label source, label generation boundary, label width, and the exact Top-3 hit definition.  
   Evidence: regenerated `reports/generated/forecast_comparison.json`, `reports/generated/forecast_diagnostics/forecast_diagnostics.json`, and `reports/generated/supplier_eval.json` include the new metadata. Scores and labels were not changed.

### Fresh Verification After Remediation

Executed:

```powershell
python -m pytest backend/tests/test_runtime_config.py backend/tests/test_purchase_drafts.py backend/tests/test_agent_loop.py backend/tests/test_agent_persistence_and_edges.py backend/tests/test_frontend_api_contract.py backend/tests/test_api_flow.py backend/tests/test_auth_api.py backend/tests/test_approval_flow.py backend/tests/test_langgraph_execution.py -q
python -m pytest backend/tests -q
python -m pytest backend/tests/test_forecast_comparison.py backend/tests/test_supplier_evaluation.py -q
$env:OPENAI_BASE_URL='https://api.deepseek.com'; python -m backend.evaluation.run_real_model_acceptance
python -m backend.evaluation.run_supplier_eval
python -m backend.evaluation.run_forecast_comparison
python -m backend.evaluation.run_forecast_diagnostics
```

Results:

- Touched backend/API suite: `45 passed`.
- Full backend suite: `71 passed, 3 skipped`; skipped tests remain opt-in MySQL integration tests.
- Evaluation structure tests: `7 passed`.
- Real model acceptance: `status=ok`; real Function Calling traces persisted and reported; approval remained human/backend-owned.
- Supplier eval regenerated: frozen composite Top-3 100.00%, challenge composite Top-3 100.00%, with label-width/source/top-3 definitions recorded.
- Forecast comparison/diagnostics regenerated with exploratory/fixed-inventory scope metadata.

Not rerun:

- MySQL专项 was not rerun in this remediation because no schema, row-lock, transaction, or approval-state behavior was changed. Previous MySQL integration evidence remains the latest MySQL-specific verification.
- Frontend browser loop and Word report generation were not run by instruction.

### Remaining Acceptance Items

- Formal Word report is still missing and remains the main uncompleted course deliverable.
- Forecast evidence must still be reported as exploratory hybrid fixed-inventory evidence, not untouched final-test evidence and not pure full-coverage Prophet.
- Object-level authorization is intentionally minimal and demo-scoped; it is not a full ERP permission platform.
- Generated reports under `reports/generated/` remain ignored by Git and must be packaged separately for delivery.

## 2026-10-29 普通采购人员交互整改复验补记

本轮明确业务交互范围全部通过：原19句+2附加句浏览器真实模型21/21，页面流程12/12，实时接口11/11；新后端163pass/6skip、独立MySQL6pass、构建/help通过。详见NATURAL_LANGUAGE_REACCEPTANCE_20261029.md。未重新生成课程包，未改变冻结预测和原课程指标限制；不能扩展为全课程或生产上线通过。
