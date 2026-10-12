# Word Report Outline And Evidence Index

## Suggested Report Outline

1. Project background and course topic mapping.
2. Requirements and scope boundaries.
3. System architecture and data flow.
4. Simulated ERP procurement dataset and CSV schema.
5. Inventory, shortage, and supplier recommendation algorithms.
6. LLM Agent orchestration and backend-owned tool execution.
7. Human approval workflow, permissions, idempotency, and audit trail.
8. Forecasting experiments and frozen service strategy.
9. Recommendation and procurement-loop evaluation.
10. Frontend demo and operation screenshots.
11. Limitations, risks, and future work.
12. Reproduction appendix.

## Course Requirement Mapping

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| ERP procurement decision workflow | Inventory, forecast, supplier recommendation, draft, submit, approve | `backend/app/services/`, `docs/API.md`, screenshot `03-approval-approved-order.png` |
| LLM Agent for intent and orchestration | OpenAI-compatible Function Calling provider and bounded Agent loop | `backend/app/services/agent_loop.py`, `backend/app/services/agent_provider.py`, `reports/generated/real_model_acceptance.json` |
| Backend owns business logic | SQL access, scoring, calculations, approval, idempotency are service-owned | `docs/ARCHITECTURE.md`, backend tests |
| Reproducible data | Deterministic demo seed and exported CSV files | `data/raw/*.csv`, `data/raw/generation_metadata.json` |
| Algorithm evaluation | Baseline, supplier eval, forecast comparison and diagnostics | `reports/generated/*.json`, `forecast_window_diagnostics.csv` |
| Demo UI | Vue frontend pages for Agent, analysis, approval, records | `frontend/src/App.vue`, `reports/generated/screenshots/*.png` |

## Evidence Index

- Baseline shortage/demand metrics: `reports/generated/baseline_eval.json`.
- Supplier recommendation Top-3 evaluation: `reports/generated/supplier_eval.json`.
- Forecast comparison: `reports/generated/forecast_comparison.json`.
- Forecast diagnostics and curves: `reports/generated/forecast_diagnostics/`.
- MySQL integration evidence: `reports/generated/mysql_integration.json`.
- Real model acceptance: `reports/generated/real_model_acceptance.json`.
- Browser screenshots: `reports/generated/screenshots/`.

## Reporting Notes And Boundaries

- Shortage evaluation uses a fixed 2026-10-10 inventory snapshot. Present it as a fixed-inventory scenario, not a true historical inventory backtest.
- Forecast comparison is exploratory because the declared holdout/test range has already been inspected during diagnostics. Do not describe it as fully untouched independent final testing.
- Long-history Prophet covers only 50/160 rolling windows under the project guard.
- Dynamic Prophet covers 140/160 windows.
- The frozen service strategy is hybrid dynamic-Prophet-or-moving-average and falls back to moving average for 20/160 windows. Do not package the hybrid result as pure Prophet.
- Prophet coverage, dynamic-seasonality exploration, and hybrid fallback are evidence for engineering tradeoffs, not separate test-pass claims.
- LangGraph execution is accepted for graph invocation; restart recovery is SQL persistence, not a cross-process LangGraph checkpoint backend.

## Reproduction Commands

```powershell
python -m pytest backend/tests -q
python -m backend.evaluation.run_baseline
python -m backend.evaluation.run_supplier_eval
python -m backend.evaluation.run_forecast_comparison
python -m backend.evaluation.run_forecast_diagnostics
python -m backend.evaluation.run_real_model_acceptance
npm --prefix frontend audit --json
npm --prefix frontend run build
```

Run MySQL integration only against a configured MySQL demo/integration database:

```powershell
$env:RUN_MYSQL_INTEGRATION = "1"
$env:MYSQL_INTEGRATION_REPORT_PATH = "reports/generated/mysql_integration.json"
python -m pytest backend/tests/test_mysql_integration.py -q
```

## Missing Before Formal Word Writing

- Final instructor-required Word template, if any.
- Final selected screenshots with captions and figure numbers.
- Any course-specific grading rubric wording that must be quoted or mirrored.
- Confirmation whether to include a demo database snapshot or only CSV plus initialization commands.
