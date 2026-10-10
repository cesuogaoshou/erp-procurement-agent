# ERP 智能采购 Agent

基于 LLM Agent 的 ERP 智能采购决策系统，用于课程选题 3.2：采购订单自动生成与供应商推荐算法研究。

当前阶段优先完成不依赖 LLM 凭据的业务与算法基础：模拟 ERP 数据、库存与缺口计算、供应商四指标推荐、采购草稿基础 API，以及评测器雏形。

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pytest backend/tests -q
.\.venv\Scripts\python -m backend.evaluation.run_baseline
.\.venv\Scripts\python -m backend.evaluation.run_supplier_eval
.\.venv\Scripts\python -m scripts.export_seed_data
.\.venv\Scripts\uvicorn backend.app.main:app --reload
```

API 默认使用 SQLite 开发库。MySQL 集成通过 `.env` 的 `DATABASE_URL` 配置，详见 `.env.example`。

## Scope

- 已纳入：库存查询、需求基线预测、缺口计算、供应商约束过滤和综合评分、基础评测、采购草稿持久化和幂等。
- 后续阶段：Function Calling Agent Loop、Trace 持久化、审批权限、最小前端、真实模型端到端记录。
- 不纳入 MVP：真实外部采购、付款、邮件、完整 ERP 模块、RAG、MCP 服务化、多 Agent、LSTM。

## Verification

```powershell
python -m pytest backend/tests -q
python -m backend.evaluation.run_baseline
python -m backend.evaluation.run_supplier_eval
```

评测输出必须保留真实结果。未达标时记录风险和局限，不调整测试集掩盖问题。
