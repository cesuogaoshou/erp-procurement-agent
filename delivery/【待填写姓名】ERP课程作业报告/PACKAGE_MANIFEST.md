# 交付包清单

- 生成时间：2026-10-13 00:30:42
- 代码版本：77a09a8aafb02b690a8cc134f97ac42237b89cc1
- Git分支：master
- Git状态快照（git status --short）：<empty output>
- Word报告：【待填写姓名】ERP课程作业报告.docx
- 源代码和数据集目录：源代码和数据集
- 文件数量：130

## 已纳入

- 后端/前端源码、Alembic迁移、测试、评测脚本。
- data/raw CSV和generation_metadata.json。
- requirements.txt、frontend/package-lock.json、.env.example、README和docs说明。
- reports/generated下的JSON/CSV/PNG评测证据、曲线和截图。

## 已排除

- .env、密钥、证书、虚拟环境、node_modules、__pycache__、pytest缓存、Chrome profile缓存、SQLite/DB快照、delivery目录。

## 复现命令

```powershell
python -m pytest backend/tests -q
python -m backend.evaluation.run_baseline
python -m backend.evaluation.run_supplier_eval
python -m backend.evaluation.run_forecast_comparison
python -m backend.evaluation.run_forecast_diagnostics
python -m backend.evaluation.run_real_model_acceptance
npm --prefix frontend audit --json
npm --prefix frontend run build
$env:RUN_MYSQL_INTEGRATION='1'; $env:MYSQL_INTEGRATION_REPORT_PATH='reports/generated/mysql_integration.json'; python -m pytest backend/tests/test_mysql_integration.py -q
```
