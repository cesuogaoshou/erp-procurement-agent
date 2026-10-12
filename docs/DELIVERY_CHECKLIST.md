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

Generated locally on 2026-10-12 by `python scripts/build_course_delivery.py`.

- Delivery folder: `delivery/【待填写姓名】ERP课程作业报告/`.
- Word report: `delivery/【待填写姓名】ERP课程作业报告/【待填写姓名】ERP课程作业报告.docx`.
- Render check: `C:\Users\Leezhaoji\Documents\Codex\tools\render-office-windows.cmd -InputPath "<absolute-docx>"` produced a PDF and 8 page PNGs; LibreOffice/Poppler warnings were non-fatal because the PDF/PNG files were created and inspectable.
- Package contents: 131 source/evidence files under `源代码和数据集`.
- Exclusion check: no `.env`, key/certificate files, virtual environments, `node_modules`, caches, Chrome profiles, SQLite/DB snapshots, or nested delivery output were found in the package.
- Sensitive scan: 0 real suspected secrets; 4 explained placeholder/test/demo constants are listed in `SENSITIVE_SCAN.md`.
- Remaining manual fields: Word/package name still uses `【待填写姓名】`; the report cover still has `【待填写：姓名 / 学号 / 班级】`.

Reports under `reports/generated/` are intentionally ignored by Git; the delivery script copies the selected generated JSON/CSV/PNG evidence into the ignored local package.
