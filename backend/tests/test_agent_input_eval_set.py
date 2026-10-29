from pathlib import Path

from backend.evaluation.run_agent_input_eval import load_cases


def test_agent_input_evaluation_set_has_required_coverage():
    cases = load_cases(Path(__file__).resolve().parents[1] / "evaluation/agent_input_cases.csv")

    assert 20 <= len(cases) <= 30
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {"normal", "missing", "validation", "intent", "security", "language"} <= {case["category"] for case in cases}
    for case in cases:
        assert case["prompt"].strip()
        assert case["expected_status"].strip()
        assert case["expect_order"] in {"yes", "no", "any"}
        assert case["expected_tools"] is not None
        assert case["forbidden_tools"] is not None
