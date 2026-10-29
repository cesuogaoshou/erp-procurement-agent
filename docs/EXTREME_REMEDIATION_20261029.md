# 2026-10-29 极端业务验收修复与复验

## 结论与证据边界

已实施六类缺陷修复、回归测试、真实 MySQL、真实模型和浏览器复验。原始 63 项极端用例复验全部通过，另加普通中文双物料和浏览器批准/驳回检查。逐项映射见 `reports/generated/extreme_remediation_20261029/CASE_MATRIX.md` 和 `SUMMARY.json`。

原失败结论仍在 `docs/EXTREME_ACCEPTANCE_20261029.md`；原证据目录没有覆盖，其 SHA-256 校验无变化。修改前已有的文档和 agent 修改已保留，起始差异备份为新目录中的 `preexisting.patch`。订单 #57 的业务快照前后相同，新增历史字段为 NULL。未清库、调参、修改冻结数据/标签、提交、推送或重建课程包。

## 实际实现

1. `purchase_drafts.py` 按物料合并申请量，比较聚合申请量与当前预测缺口，再计算 `ceil(max(聚合申请量, MOQ) / 包装倍数) × 包装倍数`。取整只执行一次；取整结果必须同时满足供应商容量和推荐证据。保存取整前需求，审批复用聚合证据校验，检查持久化数量、报价、行金额、整单金额。合法 MOQ 取整回归保留。
2. 结构化需求 `prompt + total_budget` 经 HTTP/前端明确确认后绑定运行；模型的草稿参数不包含预算字段，后端注入已确认预算。新草稿必须有预算，按实际报价和取整数量校验整单金额；审批再次检查。推荐的单行预算不能替代整单上限。迁移 `20261029_0007` 只添加 nullable 字段，没有回填历史预算。历史未知预算单保持未知，批准返回 `budget_confirmation_required`，可驳回并以明确预算重新建单；已批准订单不改动。
3. 结束状态按 `forecast:` 类型读取预测；推荐证据不再被误读为预测。运行先持久化身份和预算，工具业务在 SAVEPOINT 内执行，失败先回滚，再保存错误 Trace。已完成读工具轨迹独立提交。供应商异常、工具异常及其他未预期循环异常均受控，保留失败运行；不会为保存日志提交半成品订单。SQLite 关闭 legacy transaction control，防止释放 SAVEPOINT 后外层回滚失效。
4. 只恢复订单幂等唯一索引的竞争；其他完整性错误继续抛出。SAVEPOINT 回滚后通过 MySQL 当前读重查订单、明细和创建者，保证安全复用、一张订单、一条创建审计，跨采购员仍为 403。请求指纹规范化聚合数量、Decimal 和证据，`120.0` 与 `120.00` 相同；不同内容为明确 409。畸形证据 Decimal 在首次创建及幂等重放路径都返回受控错误。
5. 六个工具均使用本地 Pydantic 参数模型；模型 JSON Schema 来自同一模型。禁止未知字段、非法对象/数组、缺字段、非法 ID/长度/周期、非正数及 NaN/Infinity；保留 Decimal 和字符串金额。参数通过后仍执行权限和业务证据校验，没有依赖供应商 strict 配置。
6. 工具描述明确预测已含库存；保留全部有界观察，复用同运行预测缓存；“最新证据”按物料选择，重复访问缓存也更新顺序。保留 LLM 选择工具，默认上限 8 次、循环期限 180 秒、模型请求超时 30 秒。上限耗尽仍持久化运行/轨迹并返回 409。普通中文双物料实测使用 6 次调用，不靠无限增加调用预算。

前端新增明确整单预算输入，在订单审批表显示预算或“未知（历史）”，角色登录时清理旧运行/Trace 缓存。

## 回归与命令

在业务实现前运行的新回归记录了 30 项预期失败；真实 MySQL 同键 INSERT 屏障测试的两种账号组合均复现 1062。排错中另外保留了 MySQL 旧快照导致重复审计/空明细、最新引用、畸形重放、缓存顺序、未知预算审批等失败日志。没有修改原用例断言来降低要求；既有合法测试只补充新接口必需的确认预算。

| 验证 | 结果 | 新证据目录内文件 |
| --- | --- | --- |
| `python -m pytest backend/tests -q` | 133 通过、5 项 opt-in 跳过 | `backend-final-verification.txt` |
| `RUN_MYSQL_INTEGRATION=1 python -m pytest backend/tests/test_mysql_integration.py -q` | 5 项真实 MySQL 专项，含同账号/跨账号 INSERT 屏障竞争 | `mysql-final-verification.txt`、`mysql-final-verification.json` |
| `python -m backend.app.main --help` | 通过 | `cli-help-final.txt` |
| `npm --prefix frontend run build` | 通过，保留大 chunk 警告 | `frontend-build-verified.txt` |
| 原始 HTTP 极端用例 | 32/32 通过 | `final_acceptance/http_cases.json` |
| 原始真实模型用例 | 14/14 通过 | `final_acceptance/real_model_cases.json` |
| 真实内部工具边界和共享预算 | 4/4 通过 | `final_acceptance/supplement_cases.json` |
| 终态 6 项、事务内旧异常单克隆批准探针 2 项、普通双物料、原共享预算诊断 | 10/10 通过 | `final_acceptance/additional_cases.json` |
| 浏览器只读、取消、双击提交、角色限制、批准和驳回 | 6/6 通过 | `final_acceptance/browser_cases.json`、根目录截图 |

MySQL 命令在 PowerShell 实际使用 `$env:RUN_MYSQL_INTEGRATION='1'`，报告路径指向新目录。并发屏障放在 INSERT 前，要求两个独立连接均已错过旧单查询；响应状态、实际明细、一张订单、一条审计均有断言，不把任意异常当冲突。

真实模型使用现有 DeepSeek/OpenAI-compatible/LangGraph HTTP 路径，没有注入 Mock。最终主验收中：只读 Run #117 正常结束、无草稿；共享 1000 元 Run #121 无订单；普通中文双物料 Run #119 以 6 次调用创建 #124，实际整单 1956 元、确认预算 5000 元。浏览器最终只读 Run #124 保留 3 条结构化 Trace、无订单；采购员双击提交 #101 后只产生一条提交审计，审批员批准为 `PO-000101`；#102 取消驳回时快照完全相同，再正式驳回。订单与运行 ID 属于不同表。

独立审查发现的旧引用和畸形重放问题已补回归修复。早期修复模型验收曾有 1 项歧义状态不明确，记录在新目录根层 `real_model_cases.json`；加入明确解析工具指引后，`final_acceptance/` 的同原用例 14/14 通过。早期并发排错生成的 #79/#81 已通过业务提交/驳回隔离，重复创建审计证据保留，见 `final_acceptance/early-race-artifact-quarantine.json`。

## 适配与限制

- 原始执行脚本复制到新目录，只适配预算确认字段、独立幂等前缀和输出位置；`HARNESS_CHANGES.md` 明列固定预算来源。原审批坏单 #63/#64 已驳回，因此复验在 MySQL 事务内克隆其内容测试批准，再回滚克隆，不改原单。
- 最终追加边界修复后的模型/HTTP抽查见 `final_acceptance/verified_current_code.json`；服务重启初始就绪检查失败日志也保留，重试在健康检查后执行，不计为业务通过。
- 支持一个供应商、一张多物料草稿；没有扩为完整需求管理系统。历史预算和请求身份未知时不推断，不提供旧单预算原地修改模块。
- 模型编排仍有随机性，单次验收不保证所有中文表述；创建、金额、预算、权限和批准继续由后端硬校验。
- 未重新执行预测调参、完整算法回测、Word 分页/课程包生成或压力测试；冻结策略和原有探索性指标限制保持。此次没有进行断电/进程崩溃恢复测试。
- 前端生产构建仍有包体积警告；LangGraph 跨进程 checkpoint 恢复仍未实现。
