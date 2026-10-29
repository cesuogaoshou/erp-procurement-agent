"""Evaluate natural-language Agent inputs against the real Function Calling model.

The case file lives next to this runner (`agent_input_cases.csv`). Each case
gets a fresh in-memory ERP database so one case cannot affect another. The
runner records status, tool sequence, latency, order creation, budget outcome,
and explicit violations instead of pretending every model response is correct.

Usage:
    python -m backend.evaluation.run_agent_input_eval
    python -m backend.evaluation.run_agent_input_eval --dry-run
    python -m backend.evaluation.run_agent_input_eval --case normal_explicit
    python -m backend.evaluation.run_agent_input_eval --limit 5
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.app.config import load_project_env, openai_base_url_from_env
from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.services.agent_loop import AgentLoop
from backend.app.services.agent_provider import OpenAIFunctionCallingProvider, model_from_env
from backend.app.services.seed import seed_demo_data

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = ROOT / "backend/evaluation/agent_input_cases.csv"
DEFAULT_REPORT = ROOT / "reports/generated/agent_input_eval.json"
DEFAULT_DETAILS = ROOT / "reports/generated/agent_input_eval_cases.csv"


def load_cases(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"case_id", "category", "prompt", "total_budget", "expected_status", "expected_tools", "forbidden_tools", "expect_order", "notes"}
    if not rows:
        raise ValueError(f"no cases in {path}")
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    ids = [row["case_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("case_id must be unique")
    return rows


def _split(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def _status_set(value: str) -> set[str]:
    return {item.strip() for item in (value or "").split("|") if item.strip()}


def evaluate_case(case: dict[str, str], result, elapsed_ms: float) -> dict[str, Any]:
    expected_status = _status_set(case["expected_status"])
    expected_tools = _split(case["expected_tools"])
    forbidden_tools = _split(case["forbidden_tools"])
    order_expectation = case["expect_order"].strip().lower()
    budget = _decimal_or_none(case["total_budget"])
    tool_calls = list(result.tool_calls)
    violations: list[str] = []
    checks: dict[str, bool] = {}

    checks["status"] = result.status in expected_status
    if not checks["status"]:
        violations.append(f"status_mismatch: expected {sorted(expected_status)}, got {result.status}")

    missing_tools = [name for name in expected_tools if name not in tool_calls]
    checks["tools"] = not missing_tools
    if missing_tools:
        violations.append("missing_tools:" + ",".join(missing_tools))

    forbidden_hits = [name for name in forbidden_tools if name in tool_calls]
    checks["forbidden_tools"] = not forbidden_hits
    if forbidden_hits:
        violations.append("forbidden_tools:" + ",".join(forbidden_hits))

    if order_expectation == "yes":
        checks["order"] = result.purchase_order_id is not None
    elif order_expectation == "no":
        checks["order"] = result.purchase_order_id is None
    else:
        checks["order"] = True
    if not checks["order"]:
        violations.append("order_expectation_mismatch")

    if result.purchase_order_id is not None and budget is not None and result.total_amount is not None:
        checks["budget"] = result.total_amount <= budget
        if not checks["budget"]:
            violations.append("order_budget_exceeded")
    else:
        checks["budget"] = True

    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "prompt": case["prompt"],
        "total_budget": case["total_budget"],
        "expected_status": sorted(expected_status),
        "expected_tools": expected_tools,
        "forbidden_tools": forbidden_tools,
        "expect_order": order_expectation,
        "actual_status": result.status,
        "tool_calls": tool_calls,
        "purchase_order_id": result.purchase_order_id,
        "total_amount": None if result.total_amount is None else str(result.total_amount),
        "error": result.error,
        "business_message": result.business_message,
        "checks": checks,
        "violations": violations,
        "passed": all(checks.values()),
        "elapsed_ms": round(elapsed_ms, 1),
    }


def _decimal_or_none(value: str) -> Decimal | None:
    text = (value or "").strip()
    return None if not text else Decimal(text)


def _percent(value: int, total: int) -> float:
    return 0.0 if total == 0 else round(value * 100.0 / total, 2)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    latencies = [row["elapsed_ms"] for row in rows]
    by_category: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = by_category.setdefault(row["category"], {"total": 0, "passed": 0, "violations": 0})
        bucket["total"] += 1
        bucket["passed"] += int(row["passed"])
        bucket["violations"] += len(row["violations"])
    for bucket in by_category.values():
        bucket["pass_rate_percent"] = _percent(bucket["passed"], bucket["total"])
    return {
        "case_count": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate_percent": _percent(passed, total),
        "status_match_count": sum(1 for row in rows if row["checks"]["status"]),
        "tool_violation_count": sum(1 for row in rows if not row["checks"]["tools"] or not row["checks"]["forbidden_tools"]),
        "order_violation_count": sum(1 for row in rows if not row["checks"]["order"]),
        "budget_violation_count": sum(1 for row in rows if not row["checks"]["budget"]),
        "avg_latency_ms": round(statistics.mean(latencies), 1) if latencies else 0.0,
        "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18], 1) if len(latencies) >= 2 else (latencies[0] if latencies else 0.0),
        "by_category": by_category,
    }


def write_details(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "case_id", "category", "actual_status", "expected_status", "passed",
        "tool_calls", "purchase_order_id", "total_amount", "elapsed_ms", "violations",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "case_id": row["case_id"],
                "category": row["category"],
                "actual_status": row["actual_status"],
                "expected_status": "|".join(row["expected_status"]),
                "passed": row["passed"],
                "tool_calls": ";".join(row["tool_calls"]),
                "purchase_order_id": row["purchase_order_id"],
                "total_amount": row["total_amount"],
                "elapsed_ms": row["elapsed_ms"],
                "violations": "|".join(row["violations"]),
            })


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the natural-language Agent input evaluation set.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--details", default=str(DEFAULT_DETAILS))
    parser.add_argument("--case", action="append", dest="case_ids", default=[], help="run only the named case (repeatable)")
    parser.add_argument("--limit", type=int, default=None, help="run at most N cases")
    parser.add_argument("--model", default=None, help="override OPENAI_MODEL_USER/OPENAI_MODEL")
    parser.add_argument("--base-url", default=None, help="override OPENAI_BASE_URL")
    parser.add_argument("--timeout", type=float, default=120.0, help="per-case Agent timeout in seconds")
    parser.add_argument("--max-tool-calls", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true", help="validate and list cases without calling the model")
    args = parser.parse_args()

    load_project_env()
    cases = load_cases(Path(args.cases))
    if args.case_ids:
        wanted = set(args.case_ids)
        cases = [case for case in cases if case["case_id"] in wanted]
        unknown = wanted - {case["case_id"] for case in cases}
        if unknown:
            raise SystemExit(f"unknown case ids: {sorted(unknown)}")
    if args.limit is not None:
        cases = cases[: args.limit]

    if args.dry_run:
        for case in cases:
            print(f"{case['case_id']:28} {case['category']:12} {case['expected_status']}")
        print(f"validated {len(cases)} cases")
        return

    model = args.model or model_from_env()
    if not model:
        raise SystemExit("llm_model_not_configured: set OPENAI_MODEL_USER or OPENAI_MODEL")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY_missing: configure the key before running the real-model evaluation")
    base_url = args.base_url or openai_base_url_from_env()

    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['case_id']} ...", flush=True)
        engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
        try:
            with session_scope(engine) as session:
                seed_demo_data(session)
            provider = OpenAIFunctionCallingProvider(model=model, base_url=base_url, timeout_seconds=30.0)
            loop = AgentLoop(engine=engine, provider=provider, max_tool_calls=args.max_tool_calls, timeout_seconds=args.timeout)
            started = time.perf_counter()
            try:
                result = loop.run(case["prompt"], total_budget=_decimal_or_none(case["total_budget"]))
            except Exception as exc:  # keep one bad case from aborting the whole evaluation
                elapsed_ms = (time.perf_counter() - started) * 1000
                row = {
                    "case_id": case["case_id"],
                    "category": case["category"],
                    "prompt": case["prompt"],
                    "total_budget": case["total_budget"],
                    "expected_status": sorted(_status_set(case["expected_status"])),
                    "expected_tools": _split(case["expected_tools"]),
                    "forbidden_tools": _split(case["forbidden_tools"]),
                    "expect_order": case["expect_order"],
                    "actual_status": "eval_error",
                    "tool_calls": [],
                    "purchase_order_id": None,
                    "total_amount": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "business_message": "",
                    "checks": {"status": False, "tools": False, "forbidden_tools": True, "order": False, "budget": True},
                    "violations": ["eval_error:" + type(exc).__name__],
                    "passed": False,
                    "elapsed_ms": round(elapsed_ms, 1),
                }
                results.append(row)
                print(f"  ERROR {row['error']}", flush=True)
                continue
            elapsed_ms = (time.perf_counter() - started) * 1000
            row = evaluate_case(case, result, elapsed_ms)
            results.append(row)
            print(f"  {row['actual_status']} tools={','.join(row['tool_calls']) or '-'} "
                  f"order={row['purchase_order_id']} {row['elapsed_ms']}ms -> {'PASS' if row['passed'] else 'FAIL'}", flush=True)
        finally:
            engine.dispose()

    summary = summarize(results)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cases_path": str(Path(args.cases)),
        "model": model,
        "base_url_configured": bool(base_url),
        "summary": summary,
        "cases": results,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_details(Path(args.details), results)

    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {report_path}")
    print(f"details: {args.details}")


if __name__ == "__main__":
    main()
