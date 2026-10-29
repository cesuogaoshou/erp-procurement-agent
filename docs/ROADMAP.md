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

## 最新独立业务验收（2026-10-29）

整体部分通过，详见 `docs/INDEPENDENT_NL_ACCEPTANCE_20261029.md`。原21接口用例通过，新增5种表达仅2通过；真实模型原句之外的错误参数注入发现数量对调、物料遗漏、只分析误判允许采购仍能建草稿（均回滚）。下一步优先绑定原文逐项数量/物料完整性/采购意图，补交付/两周/千位金额解析及回归。本轮后端163/6skip、MySQL6、构建/CLI通过，页面审批7/7、实时权限版本3/3。未改源码、冻结数据或旧证据。下方“全部通过”为前一修复阶段限定范围，不是本轮扩展验收结论。

## 最新：普通采购人员业务交互修复与复验（2026-10-29）

**全部通过（本轮明确范围）**：原19条自然语言原句+缺数量/物料歧义2条，真实模型、浏览器逐条执行，四维检查21/21；审批/取消/恢复/补充/冲突页面12/12；实时接口幂等/版本/权限等11/11。详见 `docs/NATURAL_LANGUAGE_REACCEPTANCE_20261029.md`，原验收报告的部分通过结论作为修复前历史保留。

最新实际命令：完整后端163 passed / 6 opt-in skips，单独真实MySQL6 passed，新增反馈回归30 passed（包含在163中），前端类型/构建、CLI help、diff-check通过。证据 `reports/generated/nl_remediation_20261029/`，全部本地忽略。32次原句/补充用例迭代请求加1次过期恢复真实模型请求；最终按21个不同用例计数，不把重试重复加成通过项。

保留原架构；新增capture_request由模型提取，后端核对缺项、名称、原文数量/交期、预算冲突及加购，主结果由后端事实生成；结果与模型辅助说明保存state_json并传递API/LangGraph。页面中文状态和物料名称，技术数据折叠，审批前可查行明细/预算/交期/依据，过期保留输入，冲突提示刷新。

本轮代表订单：195（N01，随后用于过时页面冲突检查，已驳回）；205（双物料1956元，取消驳回快照不变，随后已驳回）；206（80件648元草稿）；207（要求跳过审批，仅草稿972元）；208（100件810元，已批准PO-000208）。本轮连同MySQL及迭代草稿共新增29张，全部保留记录，不清库。#57完整快照、冻结代码/数据文件及旧验收证据一致。

**本轮明确禁止提交、推送、重新生成交付包**；下方旧Local commit authorization仅是历史授权，不适用于本轮。没有迁移、回填历史预算、预测调参或外部采购。后端69204/8000，原前端5173继续运行；过期测试5174/5175夹具已停止。当前工作保留在原目录未提交，保护之前文档修改。

限制：补齐需求后新运行，无聊天续单；复杂中文/其他单位无法核对时保守追问；单供应商单草稿、演示账号与固定库存预测的既有边界不变；没有验证真实收货日期或供应商接单。完整交付包和全课程/生产上线不在本轮全部通过范围。

## Local commit authorization (2026-10-29)

User explicitly requested a local Git commit after the remediation report. This supersedes the earlier no-commit instruction only; no push or delivery regeneration is authorized. The remediation code, regressions and existing acceptance documentation are included; generated evidence remains ignored.

# Roadmap

## Latest Nontechnical User Gate: 2026-10-29

**Partial pass** after19 plain-Chinese real-model requests and6 browser workflow checks. Order guards19/19 and workflow6/6, but representative UI3/3 failed user-facing clarity checks. Next work: preserve/render Chinese business outcomes and clarification, replace internal material IDs/statuses with names/Chinese labels, provide approval line/delivery details, explicit conflicting/missing-budget confirmation, and readable session/error feedback. See `docs/NATURAL_LANGUAGE_ACCEPTANCE_20261029.md`. No source fixes performed; prior remediation gate remains scoped engineering evidence.

Independent quality reacceptance (2026-10-29): original63/63 and8 additional checks passed; backend133pass/5skip, realMySQL5pass, build/help passed. See `docs/REACCEPTANCE_20261029.md`. Confirmed explicit budget/aggregation guards, concurrent replay, readonly persistence, ordinary multi-material workflow and browser approval/rejection; application restart preserved budget/orders/runs/traces. No business edits or tuning in this turn. Invalid-input explanations, large frontend bundle, historical budget handling and prior evaluation limits remain documented.

Final verification (2026-10-29): backend 133 passed / 5 opt-in skips; real MySQL 5 passed; build/help passed; original extreme 63/63 passed. Evidence: reports/generated/extreme_remediation_20261029/.


## Extreme Remediation Gate: 2026-10-29

The six defects identified in the earlier gate below are repaired and verified; see `docs/EXTREME_REMEDIATION_20261029.md`. Original 63-case rerun passed, real MySQL INSERT contention uses a barrier after both key misses, and browser buyer/approver approval/rejection checks completed. Ordinary Chinese two-material request completed in 6 LLM-selected calls. Final backend/MySQL counts are recorded in the remediation report and release-check logs. Historical failure evidence remains authoritative for the pre-fix version. Unknown historical budgets remain unknown and block approval until a new confirmed-budget request is created. No forecasting/data/label changes or delivery rebuild.

## Latest Business Quality Gate: 2026-10-29

Extreme acceptance: 53/63 checks passed; full business sign-off is reopened. See `docs/EXTREME_ACCEPTANCE_20261029.md` for aggregate quantity/budget gaps, read-only/concurrent-create 500s, tool parameter mismatch, and multi-material limits. Prior authentication fixes still passed targeted checks. No business/test or frozen-strategy changes this turn. Evidence is ignored under `reports/generated/extreme_acceptance_20261029/`; user #57 unchanged, invalid #63/#64 rejected. Earlier dated pass statements below describe historical or narrower scopes.

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
