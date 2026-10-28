# 2026-10-28 采购草稿整改复验

## 结论

**本次指定的 P1、P2 和页面闭环复验通过。** 草稿接口认证、采购员角色、创建归属、幂等复用和提交权限已补齐；3 个 MySQL 专项已实际进入目标逻辑并通过；页面批准、驳回和后端重启恢复均通过。

本记录接续 `LOCAL_ACCEPTANCE_20261028.md` 的问题发现，原始失败记录保留。此结论针对本次整改范围，不改变预测实验属于模拟数据、固定库存、已用于诊断的探索性窗口等课程报告边界，也不代表已经更新或提交课程交付包。

## 实现范围

- `backend/app/main.py`：`POST /purchase-drafts` 使用现有签名登录令牌，采购员角色才能创建；新订单和 `created_draft` 创建审计在同一事务提交，审计失败则订单一并回滚。
- 重复幂等键首先校验已持久化创建者；本人复用原订单，不新增订单或创建审计；其他采购员返回 403，不返回订单内容。无创建归属的历史订单也不能通过直接草稿接口认领。
- 服务返回订单后再次核对创建审计，覆盖“首次查询后另一请求恰好提交同一键”的交错窗口；同采购员复用不加审计，跨采购员拒绝返回。
- `POST /purchase-orders/{id}/submit` 在状态转换及重复提交返回前校验采购员角色和创建者，拒绝跨采购员提交。查询继续沿用创建审计过滤归属。
- Agent HTTP 路径复用订单时也检查已有创建者，并避免重复追加创建审计，防止从另一入口绕过幂等归属检查。
- `backend/tests/test_mysql_integration.py`：用当前预测服务返回的引用和当前推荐服务确认的候选生成有效证据；Mock Agent 同时使用 `use_latest_forecast`、`use_latest_recommendation`。业务证据校验代码及强度未降低。
- MySQL 并发测试增加线程屏障，只捕获预期 `ApprovalConflict`，不能将连接失败等异常当作正常冲突。保留原有断言，并增加真实错误版本、回滚后无正式单号断言。
- 前端提交/批准/驳回按钮按登录角色和订单状态禁用，后端独立执行权限校验。

## 自动化验证

| 命令/检查 | 新鲜执行结果 |
| --- | --- |
| 新增草稿权限回归（最终并入全套） | 11 项通过；先复现原始失败，再修复转绿 |
| `python -m pytest backend/tests -q` | **82 passed, 3 skipped**，130.03 秒；3 个跳过项为默认不开启的 MySQL 专项 |
| `$env:RUN_MYSQL_INTEGRATION='1'; python -m pytest backend/tests/test_mysql_integration.py -q` | **3 passed**，7.14 秒，无跳过 |
| `npm --prefix frontend run build` | 通过；仍有 Vite 大包提示，主 JS 约 2175.52 kB，gzip 721.68 kB |
| `python -m backend.evaluation.run_baseline` | 通过，160 个窗口，原有冻结策略未修改 |
| `python -m backend.app.main --help` | 通过 |
| `git diff --check` | 通过 |

新增回归覆盖匿名、伪造身份头、无效令牌、审批员创建、采购员创建/查询/提交、跨采购员读取/提交/幂等键复用（草稿及待审批两种状态）、重复创建与重复提交不增加审计、创建审计失败回滚，以及 Agent 入口的同人复用和跨人复用。

跨采购员回归在测试内临时注册第二个演示账号并使用真实签名令牌，通过正常令牌验证；没有为运行中的服务新增账号或启用测试身份头。既有 HTTP 测试已改为显式采购员身份。

## MySQL 目标逻辑证据

测试使用现有本机 MySQL 演示数据，没有初始化、清空或迁移数据库。

| 专项 | 订单 | 核对结果 |
| --- | --- | --- |
| 并发审批 | #50 | 2 个线程同时开始，一次 `approved`、一次 `order_not_pending_approval`；只有 1 条审批记录及 1 条批准审计 |
| flush 后强制回滚 | #51 | 保持 `pending_approval`、版本 2、无正式单号、0 条审批记录，只保留此前提交审计 |
| Agent 与重连 | Run #65 / #52 | 预测→推荐→创建，3 条持久化轨迹；新引擎重连后订单仍待审批 |
| 重复审批幂等 | #53 | 两次相同审批键返回同一订单，只有 1 条审批记录及 1 条批准审计 |
| 错误版本及双会话冲突 | #54 | 错误版本先返回 `order_version_conflict`；第一会话提交后第二会话返回 `order_not_pending_approval`；只有 1 条审批记录 |

详细输出：`reports/generated/remediation_acceptance_20261028/mysql_integration.json`。

## 页面闭环与重启恢复

页面通过正常登录、输入、点击完成；后端使用现有真实 OpenAI-compatible/DeepSeek 配置，未注入 Mock Provider。没有直接改写数据库状态代替页面操作。

| 操作 | 核对结果 |
| --- | --- |
| 采购员页面生成并提交 | Run #66 → 草稿 #55，华东精工，120 件 × 8.10 元，总额 972.00 元；提交后版本 2 |
| 审批员页面批准 | #55 为 `approved`、版本 3，正式单号 **PO-000055** |
| 第二次页面生成并提交 | Run #67 → #56，金额 972.00 元，待审批、版本 2 |
| 后端真实进程重启 | PID 11252 → 30884；重启前后 #55 已批准、#56 待审批、Run #66/#67、7 条 Trace 及 API 查询结果完全一致 |
| 刷新页面后驳回 | 审批员驳回 #56，最终 `rejected`、版本 3，无正式单号，1 条驳回审批记录；原因“整改复验：重启恢复后人工驳回，采购需求需重新确认。” |
| 归属审计 | #55/#56 各有 1 条 `created_draft`，创建者均为 `buyer-1`；分别保留提交和批准/驳回审计 |

Run #66 实际工具序列为预测两次→推荐→创建，Run #67 为预测→推荐→创建；保留模型真实选择，不把它们描述为完全相同的固定链。重启恢复验证的是数据库中的订单、运行和轨迹查询及待审批继续处理，不是跨进程 LangGraph checkpoint 恢复。

独立实时 HTTP 复查还确认：匿名创建 401、伪造身份头创建 401、审批员创建 403；采购员以相同幂等键复用 #55 返回 200。复查前后订单总数均为 56，#55 创建审计均为 1 条。

## 证据位置与保留状态

独立代码审查发现上述交错窗口，随后增加同人/跨人两项确定性交错回归，先观察到重复审计/错误 200 两个失败，再修复并验证 2 项通过。审查复核确认该修复关闭了已复现的直接接口窗口；没有将它扩展描述为 Agent 内部创建与归属标记两个事务的生产级原子化保证。

所有生成证据位于 Git 忽略目录 `reports/generated/remediation_acceptance_20261028/`：

- `backend-tests.txt`、`frontend-build.txt`、`mysql_integration.json`、`baseline.txt`。
- `before_restart.json`、`after_restart.json`、`restart_comparison.json`、`final_state.json`，包含运行、完整 Trace、订单和审计证据。
- `live_auth_checks.py` / `.json`：实时 HTTP 认证和幂等复查。
- `snapshot.py`：本次指定运行/订单的快照与比较脚本。
- `01-agent-draft.png`、`02-buyer-submitted.png`、`03-approved-and-pending.png`、`04-recovered-after-restart.png`、`05-rejected-after-restart.png`。
- 服务日志和 `services.json`：最终代码重载后后端 PID 29676，前端启动进程 PID 13220（监听进程 3596）；仅监听本机 8000/5173。重载后再次确认实时 HTTP 权限及页面 #55/#56 最终状态正确。

本轮在原有 49 张订单上追加 #50–#56，未清除旧验收数据。未执行 Git 提交或推送。课程 Word 个人信息占位与旧交付包仍待单独处理；本次不重新生成 Word/课程包，也未重新调参、修改冻结标签或宣称纯 Prophet 全覆盖通过。
