# Minimal Acceptance Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the smallest backend/reporting issues identified by `docs/COURSE_ACCEPTANCE_REVIEW.md` without adding formal Word output, feature modules, model tuning, or label changes.

**Architecture:** Keep LLM behavior limited to provider-driven tool orchestration. Centralize business validation in backend services, add object-level read checks in API routes, and make acceptance/evaluation reports disclose configuration and scope precisely.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, pytest, existing evaluation scripts.

---

### Task 1: Real LLM Configuration Reproducibility

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/evaluation/run_real_model_acceptance.py`
- Test: `backend/tests/test_runtime_config.py`
- Test: `backend/tests/test_provider_and_config.py`

- [ ] Inspect root `.env` loading and process environment precedence.
- [ ] Write a failing test proving process environment values override root `.env` values.
- [ ] Write a failing test or report assertion proving `base_url_configured` reflects the actual provider configuration used by the run.
- [ ] Run the targeted tests and confirm they fail for the expected configuration/report reason.
- [ ] Implement the minimal code change so every entrypoint uses the same config loading path and report metadata records non-secret config source/provenance.
- [ ] Run the targeted tests and confirm they pass.

### Task 2: Shared Purchase Draft Validation

**Files:**
- Modify: `backend/app/services/purchase_drafts.py`
- Modify: `backend/app/services/agent_tools.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_purchase_drafts.py`
- Test: `backend/tests/test_agent_persistence_and_edges.py`
- Test: `backend/tests/test_frontend_api_contract.py`

- [ ] Inspect the current MOQ/package-multiple quantity rule and evidence checks.
- [ ] Write failing tests proving direct `/purchase-drafts` and Agent `create_purchase_draft` reject forged, cross-material, stale, or recommendation-free evidence using the same service path.
- [ ] Write a preserving test proving justified MOQ/package-multiple rounding remains allowed.
- [ ] Run the targeted tests and confirm the new tests fail for the expected validation gaps.
- [ ] Move shared server-side evidence validation into `purchase_drafts.py` and call it from both direct API and Agent tools.
- [ ] Run the targeted tests and confirm they pass.

### Task 3: Minimal Object-Level Read Access

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_frontend_api_contract.py`
- Test: `backend/tests/test_auth_api.py`

- [ ] Write failing tests proving a buyer cannot list or fetch another buyer's runs/traces/orders by guessing IDs.
- [ ] Write a preserving test proving an approver can read approval-needed orders and associated evidence.
- [ ] Run the targeted tests and confirm they fail for missing object-level checks.
- [ ] Add buyer-created scoping for runs/traces/orders and approver visibility for approval-required orders and evidence.
- [ ] Run the targeted tests and confirm they pass.

### Task 4: Evaluation Explanation Corrections

**Files:**
- Modify: `backend/evaluation/run_forecast_comparison.py`
- Modify: `backend/evaluation/run_forecast_diagnostics.py`
- Modify: `backend/evaluation/run_supplier_eval.py`
- Modify: `docs/COURSE_ACCEPTANCE_REVIEW.md`

- [ ] Inspect current report fields for leakage, fixed-inventory scope, Prophet coverage, hybrid metrics, label source, label width, and Top-3 definition.
- [ ] Add or adjust metadata fields only; do not change model parameters, frozen tags, labels, or answers.
- [ ] Run the relevant evaluation scripts and inspect generated metadata.

### Task 5: Verification, Docs, Commit

**Files:**
- Modify: `docs/COURSE_ACCEPTANCE_REVIEW.md`
- Modify: `docs/PROJECT_INDEX.md`
- Modify: `docs/ROADMAP.md`
- Modify: `agent/TASK.md`
- Modify: `agent/HANDOFF.md`
- Modify: `agent/MEMORY.md`
- Modify: `agent/DECISIONS.md` if a durable technical decision is introduced.

- [ ] Run targeted tests for changed behavior.
- [ ] Run `python -m backend.evaluation.run_real_model_acceptance` only if non-secret provider configuration is available.
- [ ] Run `python -m backend.app.main --help`.
- [ ] Run MySQL integration only if transaction behavior changed.
- [ ] Update the acceptance review with solved items, evidence, and remaining limitations.
- [ ] Check for secrets in diffs and generated report summaries.
- [ ] Commit locally without pushing.
