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

Ready for packaging after final verification commands and local commit. Reports under `reports/generated/` are intentionally ignored by Git, so packaging must copy them explicitly.
