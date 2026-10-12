# Course Delivery Checklist

## Include

- Source code: `backend/`, `frontend/`, `scripts/`, `docs/`, `alembic.ini`, `docker-compose.yml`, `README.md`, `AGENTS.md`.
- Data: all CSV and metadata files under `data/raw/`.
- Dependency locks: `requirements.txt`, `frontend/package.json`, `frontend/package-lock.json`.
- Configuration examples: `.env.example`; do not include `.env`.
- Evaluation raw results: copy `reports/generated/` into the delivery package even though it is Git-ignored.
- Screenshot evidence: `reports/generated/screenshots/`.
- Reproduction commands: see `docs/DEMO_GUIDE.md` and `docs/REPORT_EVIDENCE_INDEX.md`.

## Exclude

- Secrets and local credentials: `.env`, API keys, private keys, certificates.
- Runtime caches: `node_modules/`, `frontend/dist/`, `.pytest_cache/`, `__pycache__/`, Chrome profiles, temporary logs.
- Local development databases unless intentionally packaging a clearly named demo database snapshot.

## Generated Evidence To Package

- `reports/generated/baseline_eval.json`
- `reports/generated/supplier_eval.json`
- `reports/generated/forecast_comparison.json`
- `reports/generated/forecast_diagnostics/forecast_diagnostics.json`
- `reports/generated/forecast_diagnostics/forecast_window_diagnostics.csv`
- `reports/generated/forecast_diagnostics/curves/*.png`
- `reports/generated/mysql_integration.json`
- `reports/generated/real_model_acceptance.json`
- `reports/generated/screenshots/*.png`

## Security And Dependency Status

- `npm audit` originally reported one moderate direct dependency issue: `echarts < 6.1.0`, advisory GHSA-fgmj-fm8m-jvvx, XSS risk in Apache ECharts.
- Import path: root frontend dependency `echarts@5.6.0`, used by `frontend/src/App.vue` demand-history charts.
- Runtime impact: browser runtime exposure is limited to the local course demo UI, but chart rendering is user-visible and should not keep a known XSS advisory.
- Resolution: upgraded direct dependency to `echarts@^6.1.0` without `--force`.
- Verification after upgrade: `npm audit --json` reported 0 vulnerabilities, and `npm run build` passed.

## Current Delivery State

Generated locally on 2026-10-13 by `python scripts/build_course_delivery.py` after report-formula and inventory-evidence wording updates.

- Delivery folder: `delivery/【待填写姓名】ERP课程作业报告/`.
- Word report: `delivery/【待填写姓名】ERP课程作业报告/【待填写姓名】ERP课程作业报告.docx`.
- Report content includes source-aligned formulas for Prophet, dynamic seasonality and fallback, 30-day moving average, available supply, shortage, MOQ/package rounding, four-metric normalization/scoring, MAPE zero handling, and Top-3 hit rate.
- Inventory evidence wording: real model trace remains `get_demand_forecast -> recommend_suppliers -> create_purchase_draft`; source review confirms `get_demand_forecast` internally reads inventory and returns inventory evidence, so the report does not fabricate a separate historical `get_inventory` call.
- Render check: `C:\Users\Leezhaoji\Documents\Codex\tools\render-office-windows.cmd -InputPath "<absolute-docx>"` should produce a PDF and page PNGs; LibreOffice/Poppler warnings are non-fatal when the PDF/PNG files are created and inspectable.
- Package contents: source/evidence files under `源代码和数据集`.
- Exclusion check: no `.env`, key/certificate files, virtual environments, `node_modules`, caches, Chrome profiles, SQLite/DB snapshots, TypeScript build caches, or nested delivery output should be present in the package.
- Sensitive scan: expected output is 0 real suspected secrets, with placeholder/test/demo constants listed in `SENSITIVE_SCAN.md` if matched.
- Remaining manual fields: Word/package name still uses `【待填写姓名】`; the report cover still has `【待填写：姓名 / 学号 / 班级】`.

Reports under `reports/generated/` are intentionally ignored by Git; the delivery script copies the selected generated JSON/CSV/PNG evidence into the ignored local package.
