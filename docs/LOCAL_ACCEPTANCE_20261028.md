# 2026-10-28 本机验收记录

> 后续整改已完成：见 [采购草稿整改复验](REMEDIATION_ACCEPTANCE_20261028.md)。P1/P2 及指定页面闭环复验通过，后端 82 passed/3 skipped，MySQL 专项 3 passed。以下保留整改前的原始发现和失败证据，不代表整改后的当前状态。

## 结论

**部分通过，尚不能签署全部验收通过。** 本机采购、真实模型、人工批准/驳回、持久化和补充 MySQL 并发/回滚验证通过；存在匿名创建草稿的权限缺口，且仓库现有 3 个 MySQL 集成测试全部因旧版证据输入失败。

本次执行了浏览器操作和实际接口请求，未修改业务代码、测试代码、预测参数或冻结标签。未提交、推送或重新生成课程交付包。

## 环境与数据保护

- 验收代码版本：`77a09a8aafb02b690a8cc134f97ac42237b89cc1`，执行前 Git 工作区干净。
- Python 3.13；MySQL 8.4.4；数据库 `erp_procurement`，Alembic `20261011_0006`。
- 真实模型：`deepseek-v4-flash`，OpenAI-compatible endpoint `https://api.deepseek.com`。密钥未打印或写入验收材料。
- 当前数据库账号无权创建独立验收 schema。本次未执行初始化、清库或迁移，只在现有演示数据上追加验收记录。
- 开始时有 42 张订单，结束时有 49 张订单；新增订单 #43–#49 保留为证据。
- 原有数据规模：10 种物料、10 条库存、5400 条历史需求、10 家供应商、100 条供货关系。
- 验收结束时服务保留：前端 `http://127.0.0.1:5173`，后端 `http://127.0.0.1:8000`，均仅监听本机。进程信息见证据目录的 `services.json`。

## 浏览器人工流程

使用 Chrome 实际点击四个页面，登录演示采购员和审批员，并执行下列操作：

| 项目 | 本次结果 | 证据 |
| --- | --- | --- |
| 采购员登录 | 成功，显示 `buyer-1 / buyer` | 浏览器操作记录 |
| 中文指令生成草稿 | Run #64，草稿 #44，华东精工，120 件，单价 8.10 元，总额 972.00 元 | `01-agent-draft.jpg`、`before_restart.json` |
| 工具轨迹 | `get_inventory → get_demand_forecast → recommend_suppliers → create_purchase_draft`，4 条轨迹 | `before_restart.json` |
| 数据分析 | 可用库存 117.00，安全库存 80.00，预测需求 443.11，缺口 406.11；选用动态 Prophet，无回退 | `02-analysis.jpg` |
| 采购员提交 | #44 从 `draft` 变为 `pending_approval`，版本 1→2 | 页面操作、数据库结果 |
| 采购员尝试批准 | 页面显示 `403: approver_role_required`，状态保持待审批 | `03-buyer-approval-denied.jpg` |
| 审批员批准 | #44 变为 `approved`，版本 3，正式单号 `PO-000044` | `04-approved-order.jpg` |
| 后端进程重启 | Run #64、4 条 Trace、#44 已批准状态、#49 待审批状态与重启前完全一致 | `restart_persistence.json` |
| 重启后继续驳回 | #49 从待审批变为 `rejected`，版本 3，无正式单号，填写验收驳回原因 | `05-rejected-after-restart.jpg` |
| 执行记录 | 可选中 Run #64 并查看成功的草稿创建轨迹 | `06-execution-records.jpg` |

中文输入时原有示例文本未清空，实际提交的是示例文本与验收中文指令的拼接；完整原始 prompt 保存在 `before_restart.json`，未将其改写成另一次执行结果。

数据分析页面对完整 406.11 件缺口显示“暂无合格供应商”；120 件采购场景能够推荐并创建草稿。两者数量条件不同，此处保留真实无候选结果。

## 真实模型专项

调用现有 `run_acceptance()`，将本次结果单独保存为 `reports/generated/local_acceptance_20261028/real_model_acceptance.json`，未覆盖旧的真实模型验收报告。

- 总状态 `ok`，报告中 `real_function_calling=true`。
- 首次 Run #58 创建订单 #43，重复 Run #59 复用同一订单。
- 工具链为 `get_demand_forecast → recommend_suppliers → create_purchase_draft`。
- 模型请求批准时未调用审批工具，订单保持 `pending_approval`。
- 测试脚本以采购员/审批员业务身份完成提交和批准，生成 `PO-000043`；这是脚本级角色模拟，另有上述真人工页面操作验证。
- 重复批准仅保留 1 条审批记录。
- 物料歧义、无缺口、无合格供应商分别返回 `material_ambiguous`、`no_shortage`、`no_qualified_suppliers`，均未创建订单。

本次真实模型专项直接运行 AgentLoop；前端代码请求 LangGraph 执行，但未另行截获浏览器响应中的 `langgraph_executed` 标志，不把该标志当成本次单独采集的证据。

## 自动化和补充接口检查

| 检查 | 本次结果 |
| --- | --- |
| `python -m pytest backend/tests -q` | **71 passed, 3 skipped**；跳过项为选择性 MySQL 集成测试 |
| `npm --prefix frontend run build` | 通过；Vite 保留大包体积提示，主 JS 约 2175 kB，gzip 约 722 kB |
| `RUN_MYSQL_INTEGRATION=1` 下运行 `backend/tests/test_mysql_integration.py` | **3 failed**，均为 `forecast_evidence_required`，尚未进入相应并发/回滚测试主体 |
| 补充真实 HTTP/API 验收 | **14 项通过、1 项失败**，见 `api_acceptance.json` |

补充 API 检查通过项包括：健康与登录、未登录订单列表拒绝、错误密码拒绝、缺口公式、历史需求、供应商推荐、草稿幂等和金额、伪造预测证据拒绝、匿名审批拒绝、采购员伪造角色审批拒绝、批准幂等、驳回、MySQL 并发审批、事务回滚。

MySQL 实际补充证据：

- #48 两个独立 HTTP 审批请求并发，结果为一次 HTTP 200、一次 HTTP 409，仅 1 条审批记录。
- #49 在服务完成 flush 后主动抛出异常并回滚，恢复为 `pending_approval`、版本 2，无正式单号、无审批记录，审批成功审计未留下。此检查通过后才进行重启及页面驳回，因此最终 #49 为 `rejected`。
- 这些通过项是补充验证，不改变仓库 MySQL 测试 **3 failed** 的事实。

## 本次重新运行的算法指标

| 模型/方法 | 缺口 MAPE | 成功窗口 / 全部窗口 |
| --- | --- | --- |
| 30 天移动平均 | 5.75% | 160/160 |
| 长历史 Prophet | 3.35% | 50/160 |
| 动态季节性 Prophet | 5.34% | 140/160 |
| 动态 Prophet + 移动平均回退 | 5.72% | 160/160，20 次回退 |

供应商综合评分 Top-3 命中率：冻结集 60 案例为 100.00%，挑战集 60 案例为 100.00%；最低价格基线分别为 93.33% 和 95.00%。

本次仅重跑现有冻结策略，未调参、未改标签。指标仍属于**模拟数据、固定库存场景、已用于诊断的探索性窗口**；混合策略不等同纯 Prophet 全覆盖，模拟标签命中率不代表真实企业有效性。

## 未通过项及建议整改

### P1：匿名请求可创建采购草稿

- 位置：`backend/app/main.py` 的 `POST /purchase-drafts`，当前处理函数没有认证和采购员角色依赖。
- 复现：不携带 `Authorization`，提交服务可验证的预测/推荐证据及有效物料、供应商和数量。
- 实际结果：HTTP **200**，创建订单 **#45**，状态 `draft`，金额 972.00 元。
- 预期结果：匿名请求返回 401/403，不写入草稿。
- 建议：直接草稿创建接口要求采购员身份，并记录创建者审计，检查创建后订单读取归属。
- 本次未修改业务代码；#45 保留以便核查，未批准或执行外部采购。

### P2：MySQL 专项测试输入与现行证据规则不一致

- 位置：`backend/tests/test_mysql_integration.py`。
- 现有测试使用 `recommendation:mysql-integration`、`recommendation:mysql-duplicate` 等旧占位引用，缺少当前后端要求的预测和供应商推荐证据。
- 因此三个测试都在准备草稿时被正确拒绝，无法验证原本的并发、幂等、回滚目标。
- 建议：通过当前预测/推荐服务准备有效证据；Mock Agent 路径使用实际返回的推荐引用，再运行专项及全量测试。不得放松业务证据校验来迁就旧测试。
- 旧文档中的 MySQL “3 passed”属于历史执行结果，不是本次现行代码专项通过证据。

### 交付材料待办

- 本机已有课程 Word 文件；正文仍有“待填写”个人信息，占位尚未完成。
- 本次未重新用 Word 检查分页，也未重新生成、提交课程交付包；DOCX 元数据中的页数不能替代真实 Word 排版验收。
- 当前课程包未包含本次新发现及新证据，后续整改后需更新交付材料。

## 证据与复现

本次证据目录：`reports/generated/local_acceptance_20261028/`，保持 Git-ignored。

主要文件：`context.json`、`services.json`、`api_acceptance.py`、`api_acceptance.json`、`api_acceptance.log`、`mysql_tests.log`、`real_model_acceptance.json`、`baseline_eval.json`、`supplier_eval.json`、`forecast_comparison.json`、`forecast_comparison.log`、`before_restart.json`、`restart_persistence.json`、`browser_acceptance.json`、`delivery_inspection.json`、6 张 JPG 截图。`prior_evidence/` 保存此次重跑前的算法报告副本。

```powershell
python -m pytest backend/tests -q
npm --prefix frontend run build
$env:RUN_MYSQL_INTEGRATION = '1'
$env:MYSQL_INTEGRATION_REPORT_PATH = 'reports/generated/local_acceptance_20261028/mysql_integration.json'
python -m pytest backend/tests/test_mysql_integration.py -q
python reports/generated/local_acceptance_20261028/api_acceptance.py
python -m backend.evaluation.run_baseline
python -m backend.evaluation.run_supplier_eval
python -m backend.evaluation.run_forecast_comparison
```

接口验收脚本会追加新验收订单，保留匿名接口未拒绝的失败项；不要把其 JSON 的 `partial_failed` 状态当作通过。真实模型专项 JSON 的状态应结合重复订单复用、审批记录数量、边界状态和实际 Trace 一起检查。
