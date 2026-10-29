## 最终：需求绑定整改与复验通过（2026-10-29）

本轮三组缺陷已关闭，最终报告 `docs/NL_BINDING_FINAL_REACCEPTANCE_20261029.md`，证据 `reports/generated/nl_binding_remediation_20261029/final_v3/`。中间197/201/202成绩、条件句/只读推荐缺口及模型幂等键冲突保留记录，不冒充最终结果。

最新实际执行：完整后端203 passed / 6默认MySQL跳过；单独真实MySQL6 passed；前端类型/构建、CLI和diff通过；最终原21+新增5真实模型接口26/26；8次真实页面/确认运行、9个MySQL回滚链探针（8拒绝+1正确对照）、7种隔离页面故障、6项实时拒绝/快照检查通过。最终确认369→修改失效→370明确确认→371草稿326（轴承120+外壳80，1628元），人工批准PO-000326；321取消驳回快照不变后已驳回；324待审批。

模型候选独立绑定原文全集/逐项数量/单位/只分析/交期/预算，有效需求持久化并锚定原始运行。只读中明确条件同样约束推荐；普通前置“如果”不解除禁写。草稿幂等键由服务端运行ID确定，同运行重试只产生一个草稿，直接API幂等协议保留；后续重放不改变最初来源。两周14天、交付等表达及5,000/非法金额/单价历史语境均已覆盖。

全程124次真实模型业务运行=104接口（4轮各26）+20页面/确认，最终只计26不同接口用例+8页面/确认；模拟注入与MySQL Mock不算真实模型请求。57完整快照、冻结数据/预测源码及旧三轮证据散列一致，错误探针全部回滚。没有提交、推送、清库、迁移、调参或重建交付包。

后端62980/8000和原前端5173保持运行，隔离8001已停。保留复杂NL保守确认、单供应商、演示账号、固定库存、无外部采购与不回填历史锚点的既有边界；不同新AgentRun仍是新业务执行，未新增跨运行客户端去重。下一步仅按用户新任务继续。

## 最新：原文需求绑定整改与真实复验（2026-10-29）

**本轮三组缺陷通过（明确范围）**。见 `docs/NL_BINDING_REMEDIATION_20261029.md`；旧独立“部分通过”报告保留原样。服务端独立绑定物料全集/逐项数量/只分析限制，保存有效需求；不可靠对应时完整中文清单明确确认，确认绑定原文/预算/记录/所属人，一次消费；推荐、草稿和审批从原执行记录复核。交付/周单位（两周14天）及合法千分金额已修复，并补历史数量/预算上下文、单位与禁写表达边界。

最终实际验证：后端197 passed / 6默认MySQL跳过；单独真实MySQL6 passed；类型/构建、CLI、diff通过；原21+新增5真实模型接口26/26，最终浏览器8次真实模型业务运行、5种隔离错误模型页面拦截、7个MySQL回滚链探针（6拒绝+1正确对照）、6项实时拒绝/快照检查通过。完整清单明确确认后草稿282（120件轴承+80件外壳，1628元）经人工批准PO-000282；278取消驳回完整快照不变后已驳回；281待审批。

证据 `reports/generated/nl_binding_remediation_20261029/final/`，此前迭代仍在父目录。总62次真实模型业务运行=初轮26接口+2页面+最终26接口+8页面/确认，不当作62个不同用例或底层模型HTTP次数。模拟错误模型参数不计入真实模型请求。57完整快照、冻结数据/预测源码和旧三轮自然语言证据散列一致；错误探针事务回滚。旧服务日志追加尾部另存，本轮基线新结果另存，旧证据字节及已跟踪基线内容已保护。

未提交、推送、清库、迁移、调参或重建交付包。主后端67360/8000及前端5173继续运行，隔离8001夹具已停。限制：复杂自然语言保守确认/追问；单供应商单草稿、演示账号、固定库存、无外部采购与历史订单不回填新锚点。后续仅按用户新任务继续，不用本轮范围结论扩张为课程/生产全部通过。

## 最新独立验收（2026-10-29）：部分通过

见 `docs/INDEPENDENT_NL_ACCEPTANCE_20261029.md`。本轮重新执行后端163通过/6默认跳过、真实MySQL6通过、前端构建/CLI通过。原21条接口复验通过；新增5条自然表达2通过/3误拦截。另有错误模型参数探针3种可生成与原文不符的事务内草稿（全部回滚）；2个对照组正确拒绝。页面代表请求2/3、审批流程7/7、实时权限/版本检查3/3。整体部分通过，下面修复阶段“全部通过”限于其原先列明范围。

证据 `reports/generated/nl_independent_20261029/`；30次真实模型请求=27接口尝试（26不同用例，含采集重试1次）+3页面。优先整改逐项物料数量/完整性/只分析意图核对，再补交付/周单位和5,000元解析。无业务源码修改；源码/冻结数据/旧证据/用户57一致。219已驳回，227已批准PO-000227。未提交、推送或重建交付包。

## 最新：普通采购人员业务交互修复与复验（2026-10-29）

**全部通过（本轮明确范围）**：原19条自然语言原句+缺数量/物料歧义2条，真实模型、浏览器逐条执行，四维检查21/21；审批/取消/恢复/补充/冲突页面12/12；实时接口幂等/版本/权限等11/11。详见 `docs/NATURAL_LANGUAGE_REACCEPTANCE_20261029.md`，原验收报告的部分通过结论作为修复前历史保留。

最新实际命令：完整后端163 passed / 6 opt-in skips，单独真实MySQL6 passed，新增反馈回归30 passed（包含在163中），前端类型/构建、CLI help、diff-check通过。证据 `reports/generated/nl_remediation_20261029/`，全部本地忽略。32次原句/补充用例迭代请求加1次过期恢复真实模型请求；最终按21个不同用例计数，不把重试重复加成通过项。

保留原架构；新增capture_request由模型提取，后端核对缺项、名称、原文数量/交期、预算冲突及加购，主结果由后端事实生成；结果与模型辅助说明保存state_json并传递API/LangGraph。页面中文状态和物料名称，技术数据折叠，审批前可查行明细/预算/交期/依据，过期保留输入，冲突提示刷新。

本轮代表订单：195（N01，随后用于过时页面冲突检查，已驳回）；205（双物料1956元，取消驳回快照不变，随后已驳回）；206（80件648元草稿）；207（要求跳过审批，仅草稿972元）；208（100件810元，已批准PO-000208）。本轮连同MySQL及迭代草稿共新增29张，全部保留记录，不清库。#57完整快照、冻结代码/数据文件及旧验收证据一致。

**本轮明确禁止提交、推送、重新生成交付包**；下方旧Local commit authorization仅是历史授权，不适用于本轮。没有迁移、回填历史预算、预测调参或外部采购。后端69204/8000，原前端5173继续运行；过期测试5174/5175夹具已停止。当前工作保留在原目录未提交，保护之前文档修改。

限制：补齐需求后新运行，无聊天续单；复杂中文/其他单位无法核对时保守追问；单供应商单草稿、演示账号与固定库存预测的既有边界不变；没有验证真实收货日期或供应商接单。完整交付包和全课程/生产上线不在本轮全部通过范围。

## Local commit authorization (2026-10-29)

User explicitly requested a local Git commit after the remediation report. This supersedes the earlier no-commit instruction only; no push or delivery regeneration is authorized. The remediation code, regressions and existing acceptance documentation are included; generated evidence remains ignored.

# Project Index

Latest nontechnical-user acceptance (2026-10-29): **partial pass**, see `docs/NATURAL_LANGUAGE_ACCEPTANCE_20261029.md`. Executed19 plain-Chinese real-model requests (16HTTP +3browser): request/order guards19/19; browser workflow checks6/6. All3 representative result pages have readability/feedback defects; missing clarification, Chinese outcome/reasons, material names and approval details block complete user-facing acceptance. Orders178/180/181 remain drafts,179 rejected,182 approved PO-000182. Source hashes and user57 unchanged; no business fixes or regression-suite rerun. Raw evidence: `reports/generated/natural_language_acceptance_20261029/`. Prior71/71 below is the earlier engineering gate, not this user-facing acceptance result.

Independent reacceptance (2026-10-29), code `c7004b4`: original63/63 plus8 extra checks passed (71/71). Fresh backend133pass/5skip, realMySQL5pass, build/help pass; browser #170 approved/PO-000170, multi-material #175 rejected, readonlyRun150 completed, restart snapshots unchanged. See `docs/REACCEPTANCE_20261029.md` and ignored `reports/generated/reacceptance_20261029_independent/`. Source/original evidence hashes and #57 unchanged. Invalid natural-language quantity explanations remain a UI improvement item; this is scoped remediation acceptance, not all course/production requirements.

Final verification (2026-10-29): backend 133 passed / 5 opt-in skips; real MySQL 5 passed; build/help passed; original extreme 63/63 passed. Evidence: reports/generated/extreme_remediation_20261029/.

## Current State

Latest extreme remediation on 2026-10-29: implemented all six defect classes with regressions and local verification. Read `docs/EXTREME_REMEDIATION_20261029.md` before interpreting historical conclusions below. Original 63 checks reran successfully; structured confirmed whole-order budget, aggregate quantity/rounding/approval guards, runtime tool models, durable error traces, and real MySQL idempotency contention recovery are implemented. Migration head `20261029_0007`; historical budgets remain NULL and unknown-budget approval is blocked. Evidence is separate under `reports/generated/extreme_remediation_20261029/`; original failure files and user order #57 preserved. No commit/push or course package regeneration.


Latest extreme acceptance on 2026-10-29: **partial pass**, see `docs/EXTREME_ACCEPTANCE_20261029.md`. Executed 63 checks: 53 passed/10 failed, grouped into aggregate quantity/capacity bypass, missing shared order-budget enforcement, read-only Agent 500/trace loss, concurrent same-key create 500, internal tool/schema mismatch, and a multi-material run hitting 6-call limit. No business/test code changed. User #57 unchanged; invalid test #63/#64 rejected for isolation. Evidence: ignored `reports/generated/extreme_acceptance_20261029/`. Earlier remediation passes below remain scoped to that earlier work.

Latest remediation acceptance on 2026-10-28: **P1/P2 and requested browser loop passed**, see `docs/REMEDIATION_ACCEPTANCE_20261028.md`. Draft creation requires a signed buyer token, atomically writes creator audit, and checks ownership on replay/submission; Agent HTTP replay also preserves ownership and a single creation audit. Fresh verification: 82 backend tests passed (3 opt-in skips), all 3 MySQL tests passed with current evidence, frontend build passed, real browser runs #66/#67 created #55/#56, PO-000055 was approved, and #56 was rejected after a real backend restart. Run/order/7-trace snapshots matched across restart. Evidence: ignored `reports/generated/remediation_acceptance_20261028/`. The earlier partial-pass discovery is preserved in `docs/LOCAL_ACCEPTANCE_20261028.md`. Frozen forecasting limitations and unfilled course report fields remain; the delivery package was not regenerated.

Initialized on 2026-10-10 from the original ERP intelligent procurement Agent outline in the repository root.

Course acceptance review was added on 2026-10-12 in `docs/COURSE_ACCEPTANCE_REVIEW.md`, followed by a minimal remediation addendum and local course-delivery generation. The current acceptance stance is course-delivery prepared with explicit limitations: deterministic backend, MySQL approval safety, supplier evaluation, hybrid forecast evaluation, reproducible data, frontend build evidence, and real LLM acceptance are strong; draft evidence validation and minimal object-level read access were tightened; the forecast requirement is reported as exploratory hybrid fixed-inventory evidence rather than pure full-coverage Prophet; the formal Word report and delivery folder now exist locally under `delivery/【待填写姓名】ERP课程作业报告/` and remain Git-ignored.

The project has completed deterministic backend acceptance work through approval loop basics, MySQL integration verification, real OpenAI-compatible/DeepSeek Agent orchestration, real Prophet comparison and diagnostics, real LangGraph execution, and the first minimal Vue frontend: local Git baseline, backend skeleton, SQLAlchemy models, Alembic migrations, reproducible simulated CSV data, inventory and shortage calculation, supplier recommendation, MOQ/package-multiple purchase draft rounding, purchase draft persistence, server-signed demo token authentication, role-gated approval transitions, audit logs, API routes, mock-provider Agent loop, OpenAI-compatible tool schema dispatch, real Function Calling to purchase draft, real `StateGraph` wrapper execution, persisted run/tool traces, frozen hybrid forecast service strategy, baseline and forecast-comparison backtesting, per-window Prophet diagnostics, dynamic-seasonality and hybrid forecast evidence, fixed-inventory shortage scenario reporting, supplier Top-3 evaluation, frontend-facing run/trace/order/history APIs, and four minimal frontend pages for intelligent procurement, data analysis, approval, and execution records.

## Read Order

1. `AGENTS.md`
2. `docs/PROJECT_INDEX.md`
3. `agent/HANDOFF.md`
4. `agent/TASK.md`
5. `docs/REQUIREMENTS.md`
6. `docs/ARCHITECTURE.md`
7. `docs/API.md`
8. `docs/DATA_DICTIONARY.md`
9. Original ERP intelligent procurement Agent outline in the repository root.

## Source Map

- `backend/app/main.py`: FastAPI application factory and routes.
- `frontend/`: Vue 3 + TypeScript + Element Plus + ECharts minimal demo application.
- `frontend/src/App.vue`: four-page procurement workspace and browser-demo flow.
- `frontend/src/api.ts`: typed frontend API client using bearer tokens.
- `backend/app/config.py`: root `.env` loader and OpenAI-compatible base URL validation.
- `backend/app/models/`: SQLAlchemy data model.
- `backend/app/schemas/`: Pydantic request and response schemas.
- `backend/app/services/`: deterministic business services independent of LLM.
- `backend/app/services/auth.py`: preset demo accounts and signed bearer token verification.
- `backend/app/services/forecasting.py`: frozen service prediction strategy `forecast_strategy_v1_20261011`, dynamic Prophet main path, moving-average fallback, and forecast evidence metadata.
- `backend/app/services/agent_provider.py`: provider protocol and mock provider for offline tests.
- `backend/app/services/agent_tools.py`: model tool schemas and deterministic tool execution.
- `backend/app/services/agent_loop.py`: bounded Agent tool loop.
- `backend/app/services/langgraph_runner.py`: real LangGraph `StateGraph` wrapper around the bounded procurement Agent loop.
- `backend/tests/test_mysql_integration.py`: opt-in MySQL integration tests for approval concurrency, duplicate approval idempotency, rollback, and Agent persistence.
- `backend/evaluation/run_forecast_comparison.py`: moving-average vs real Prophet backtest over identical windows, same-window moving-average comparison on Prophet success windows, dynamic-seasonality Prophet exploration, hybrid Prophet-or-moving-average strategy reporting, and explicit failure reporting.
- `backend/evaluation/run_forecast_diagnostics.py`: Prophet error diagnostic runner that writes per-window errors, split-overlap notes, validation-grid results, fixed-inventory scenario scope, and representative curves.
- `backend/evaluation/run_real_model_acceptance.py`: real-provider business-loop and boundary-case acceptance runner.
- `backend/app/algorithms/`: forecasting, shortage, recommendation, and metrics.
- `backend/app/db/`: engine, sessions, initialization, and seed loading.
- `backend/evaluation/`: baseline evaluation scripts.
- `backend/alembic/`: Alembic migration environment.
- `backend/tests/`: automated tests for core business and algorithm behavior.
- `reports/generated/baseline_eval.json`: latest local baseline evaluation output, generated by command and ignored by Git.
- `reports/generated/forecast_comparison.json`: latest forecast model comparison output, generated by command and ignored by Git.
- `reports/generated/forecast_diagnostics/`: latest local Prophet diagnostic baseline, hashes, per-window CSV, JSON, and curves; generated by command and ignored by Git.
- `reports/generated/supplier_eval.json`: latest supplier recommendation evaluation output, generated by command and ignored by Git.
- `data/raw/`: reproducible simulated source CSV files.
- `docs/`: human-facing project documentation.
- `docs/DEMO_GUIDE.md`: repeatable initialization, startup, login, procurement, approval, and query demo steps.
- `docs/DELIVERY_CHECKLIST.md`: course package contents, ignored evidence handling, and dependency-audit conclusion.
- `docs/REPORT_EVIDENCE_INDEX.md`: Word report outline, course requirement mapping, evidence index, and reporting boundaries.
- `docs/COURSE_ACCEPTANCE_REVIEW.md`: course acceptance audit with requirement-to-evidence mapping, blocking issues, remediation plan, and report-claim boundaries.
- `scripts/build_course_delivery.py`: reproducibly generates the formal Word report, report charts, delivery folder, package manifest, and sensitive-info scan from current evidence files.
- `delivery/【待填写姓名】ERP课程作业报告/`: ignored local course delivery package with 9-page Word report, `源代码和数据集`, manifest, render outputs, and sensitive scan.
- `agent/`: local working memory and handoff notes; ignored by Git by default.

## Reference Source

The original development outline remains in the repository root and is not copied in full into every document. This index links to it as the detailed acceptance reference.

## Latest Verified Commands

- `git commit -m "chore: establish phase 1 foundation baseline"`: created local baseline commit `8903dec`.
- `python -m alembic upgrade head` with temporary SQLite `DATABASE_URL`: applied initial schema and purchase draft migrations.
- `python -m backend.app.db.init_demo_data --database-url sqlite+pysqlite:///./tmp_alembic_check.sqlite`: inserted 10 materials, 10 suppliers, 5400 demand rows, 100 supplier-material rows, 100 performance rows.
- `python -m backend.evaluation.run_baseline`: completed with 160 backtest samples and wrote `reports/generated/baseline_eval.json`.
- `python -m backend.evaluation.run_supplier_eval`: completed with 60 frozen recommendation cases, 60 challenge recommendation cases, wrote `data/raw/recommendation_cases.csv`, `data/raw/recommendation_challenge_cases.csv`, and `reports/generated/supplier_eval.json`.
- `python -m scripts.export_seed_data`: wrote UTF-8 CSV files under `data/raw/`.
- `python -m pytest backend/tests -q`: passed 42 tests for deterministic services, API flow, signed-token auth, approval permissions/idempotency/rollback, forecast comparison, mock Agent loop, provider error handling, run/trace persistence, and evaluation metadata.
- `python -m alembic upgrade head` with temporary SQLite `DATABASE_URL`: applied approval migration through revision `20261010_0003`.
- `python -m alembic upgrade head` with temporary SQLite `DATABASE_URL`: applied Agent run/trace migration through revision `20261010_0004`.
- `python -m backend.evaluation.run_forecast_comparison`: completed moving-average comparison and reported Prophet as failed when the optional package was unavailable.
- `python -m backend.app.db.init_demo_data --database-url sqlite+pysqlite:///./tmp_alembic_approval_check.sqlite`: inserted 10 materials, 10 inventory rows, 5400 demand rows, 10 suppliers, 100 supplier-material rows, 100 performance rows, and 0 purchase orders after migrations.
- `python -m alembic current` with MySQL `DATABASE_URL`: reported `20261010_0004 (head)`.
- MySQL data count check with current `DATABASE_URL`: materials 10, inventory 10, demand_history 5400, suppliers 10, supplier_materials 100, supplier_performance 100, purchase_orders 0 before integration test writes.
- `$env:RUN_MYSQL_INTEGRATION='1'; $env:MYSQL_INTEGRATION_REPORT_PATH='reports/generated/mysql_integration.json'; python -m pytest backend/tests/test_mysql_integration.py -q`: passed 1 MySQL integration test covering approval row-lock concurrency, transaction rollback, and Agent run/tool trace/pending draft queryability after reconnect.
- `python -m pytest backend/tests -q`: passed 53 tests and skipped the 3 opt-in MySQL integration tests by default.
- `OPENAI_BASE_URL=https://api.deepseek.com` and `OPENAI_MODEL_USER=deepseek-v4-flash` were configured in the user environment without printing secrets.
- Real DeepSeek/OpenAI-compatible Function Calling smoke wrote `reports/generated/real_llm_function_calling.json`: status `draft_created`, tool calls `list_materials`, `get_inventory`, `get_demand_forecast`, `recommend_suppliers`, `create_purchase_draft`, run id 6, purchase order id 7, and `real_function_calling=true`. Approval/rejection tools were not exposed or called.
- `python -m pip show prophet langgraph cmdstanpy`: confirmed Prophet 1.5.0, LangGraph 1.2.14, and CmdStanPy 1.3.0 are installed locally.
- `python -m alembic upgrade head` with MySQL `DATABASE_URL`: applied package-multiple revisions through `20261011_0006`.
- `python -m backend.evaluation.run_forecast_comparison`: completed exploratory real moving-average and Prophet comparison over 160 identical windows; report path `reports/generated/forecast_comparison.json`; service strategy config `forecast_strategy_v1_20261011`; full moving average demand MAPE 5.18%, shortage MAPE 5.75%; long-history Prophet status `partial`, 50/160 successful windows, 110 `insufficient_history` failures, successful-window demand MAPE 3.04%, shortage MAPE 3.35%; moving average on the same 50 windows demand MAPE 6.95%, shortage MAPE 7.66%; dynamic Prophet status `partial`, 140/160 successful windows, demand MAPE 4.75%, shortage MAPE 5.34%; hybrid dynamic-Prophet-or-moving-average full-window demand MAPE 5.09%, shortage MAPE 5.72%, 20/160 fallbacks.
- `python -m backend.evaluation.run_forecast_diagnostics`: wrote `reports/generated/forecast_diagnostics/forecast_diagnostics.json`, `forecast_window_diagnostics.csv`, and representative curves; implementation checks found no date/order/30-day aggregation issue. Diagnostics identified short training history, split/test consumption limitations, and fixed-inventory scenario limitations.
- `python -m pytest backend/tests -q`: passed 58 tests with 3 opt-in MySQL tests skipped after wiring the frozen hybrid forecast strategy into service/tool flow.
- `python -m backend.evaluation.run_real_model_acceptance`: wrote `reports/generated/real_model_acceptance.json`; real model loop still passed after forecast service integration with status `ok`, draft creation, blocked model approval, human approval to formal order `PO-000034`, and boundary statuses `material_ambiguous`, `no_shortage`, and `no_qualified_suppliers`.
- `python -m pytest backend/tests/test_langgraph_execution.py -q`: passed 2 tests for real LangGraph execution plus persisted run/tool/order state queryability through a new DB session.
- `$env:RUN_MYSQL_INTEGRATION='1'; $env:MYSQL_INTEGRATION_REPORT_PATH='reports/generated/mysql_integration.json'; python -m pytest backend/tests/test_mysql_integration.py -q`: passed 3 MySQL integration tests covering dual-session concurrent approval, duplicate approval idempotency, rollback, and restart-style Agent persistence.
- `python -m backend.evaluation.run_real_model_acceptance`: wrote `reports/generated/real_model_acceptance.json`; real DeepSeek created a draft, buyer submitted it, the model could not approve it, approver approved it to formal order `PO-000028`, duplicate operations reused existing state, and boundary cases returned expected business states.
- `python -m pytest backend/tests/test_frontend_api_contract.py -q`: passed 2 tests for frontend-facing Agent run/trace/order approval loop and demand-history chart API.
- `npm run build` in `frontend/`: passed TypeScript and Vite build; Vite reported a large chunk warning from Element Plus/ECharts.
- Browser validation at `http://127.0.0.1:5173`: buyer login, real DeepSeek/OpenAI-compatible Agent run with explicit MAT-001/120/20-day/5000 prompt, draft creation, submit, approver login, approve, and formal order `PO-000001` displayed in the order list. An earlier broader prompt returned `no_qualified_suppliers` because the model pursued the forecast shortage quantity beyond supplier capacity.
- Startup configuration now loads root `.env` for backend app, Alembic, and real-model acceptance without overriding existing process variables. `DATABASE_URL` is used by the FastAPI app when no explicit engine is injected. Missing `OPENAI_BASE_URL` returns `OPENAI_BASE_URL_missing`; missing model returns `llm_model_not_configured`; secrets are not printed.
- Demo reset is restricted to explicit demo database URLs and no longer defaults to arbitrary `DATABASE_URL`. SQLite demo initialization creates schema directly; MySQL demo initialization should still run Alembic first.
- `npm audit` moderate finding for direct `echarts@5.6.0` / GHSA-fgmj-fm8m-jvvx was resolved by upgrading to `echarts@^6.1.0` without `--force`; `npm audit --json` reports 0 vulnerabilities and `npm run build` passes.
- Latest screenshot evidence saved under `reports/generated/screenshots/`: buyer Agent page, analysis page, and approval page showing approved order `PO-000002`. Generated evidence remains Git-ignored and must be copied into the course package.
- Course acceptance review commands on 2026-10-12: `python -m pytest backend/tests -q` -> 66 passed, 3 skipped; `python -m backend.app.main --help` passed; `python -m backend.evaluation.run_supplier_eval`, `python -m backend.evaluation.run_baseline`, `python -m backend.evaluation.run_forecast_comparison`, and `python -m backend.evaluation.run_forecast_diagnostics` completed; MySQL integration rerun with `MYSQL_INTEGRATION_REPORT_PATH=reports/generated/mysql_integration_review.json` -> 3 passed; `npm --prefix frontend audit --json` -> 0 vulnerabilities; `npm --prefix frontend run build` passed with a large chunk warning; non-writing real-model acceptance check failed with `OPENAI_BASE_URL_missing`.
- Minimal remediation verification on 2026-10-12: touched backend/API suite -> 45 passed; `python -m pytest backend/tests -q` -> 71 passed, 3 skipped; evaluation structure tests -> 7 passed; real acceptance rerun with `OPENAI_BASE_URL=https://api.deepseek.com` wrote `reports/generated/real_model_acceptance.json` with `status=ok`, `base_url_configured=true`, real tool traces, draft id 41, and human approval to `PO-000041`; supplier eval, forecast comparison, and forecast diagnostics regenerated with corrected explanatory metadata.
- Course delivery refinement on 2026-10-13: `python scripts/build_course_delivery.py` regenerated `delivery/【待填写姓名】ERP课程作业报告/【待填写姓名】ERP课程作业报告.docx` plus `源代码和数据集`; the Word report now includes source-aligned algorithm formulas, percentage units in metric headers, natural-language label-width wording, and an explicit inventory-evidence conclusion distinguishing model tool calls from forecast-tool internal inventory reads. It rendered with `C:\Users\Leezhaoji\Documents\Codex\tools\render-office-windows.cmd -InputPath "<docx>"`, producing PDF and 9 page PNGs. `py_compile` passed for the generator. Package check found 130 source/evidence files, 0 excluded runtime/cache/secret/database files, 0 real suspected secrets, and 4 explained placeholder/test/demo secret-like constants.

## Current Backend Acceptance Status

MySQL integration is verified with the current `DATABASE_URL`, including migration head, deterministic seed counts, dual-session approval concurrency, duplicate approval idempotency, rollback, and Agent persistence after reconnect. SQLite tests still do not substitute for this check; rerun the opt-in MySQL tests when schema or transaction behavior changes. Real external DeepSeek/OpenAI-compatible Function Calling is accepted for the natural-language-to-draft path and controlled boundary states; the latest acceptance report records non-secret config sources, code version, model, real persisted tool traces, and final approval state. Purchase draft validation is shared by Agent tools and direct API/service paths: current forecast evidence and recommendation evidence are required, requested quantity cannot exceed server shortage, and MOQ/package-multiple rounding remains allowed when evidence supports the rounded order. Minimal object-level read access scopes buyer runs/traces/orders to the creator and lets approvers read approval-needed/processed orders and associated evidence. Forecasting is frozen at service config `forecast_strategy_v1_20261011`: the actual service/tool strategy is hybrid dynamic-Prophet-or-moving-average, uses dynamic Prophet as the main model, and falls back to 30-day moving average for short history or Prophet failure. The hybrid strategy returns and persists model name, selected model, config version, training range, fallback reason, and forecast evidence through tool traces and purchase draft evidence payloads; it must not be described as pure Prophet. Evaluation remains exploratory: long-history yearly+weekly Prophet succeeds on 50/160 windows, dynamic Prophet succeeds on 140/160 windows, and the full hybrid uses moving-average fallback for 20/160 windows. The 365-day threshold is a project engineering strategy, not a Prophet universal hard requirement. The current holdout/test range has already been inspected for diagnostics, so do not claim fully untouched independent final-test evidence. Shortage comparisons reuse the static 2026-10-10 inventory snapshot as a fixed-inventory scenario, not a true historical inventory backtest. Reports under `reports/generated/` are Git-ignored but reproducible by the documented commands and should be copied into the course delivery package when packaging evidence. Real LangGraph execution is accepted for graph invocation; cross-process recovery is provided by database persistence rather than a durable LangGraph checkpoint backend. The minimal frontend is accepted for the course/demo browser loop, but it remains a demo UI rather than a production ERP frontend.
