from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.services.seed import seed_demo_data
from backend.evaluation.supplier_recommendation import (
    build_challenge_cases,
    build_independent_cases,
    evaluate_supplier_recommendations,
)


def test_supplier_evaluation_compares_price_baseline_and_composite_top3():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        cases = build_independent_cases(session, case_count=50)
        result = evaluate_supplier_recommendations(session, cases)

    assert len(cases) == 50
    assert {case.label_source for case in cases} == {"scenario_thresholds_v1"}
    assert all(case.acceptable_supplier_ids for case in cases)
    assert result["case_count"] == 50
    assert "price_sort_top3_hit_rate_percent" in result
    assert "composite_top3_hit_rate_percent" in result
    assert result["label_source"] == "scenario_thresholds_v1"


def test_supplier_evaluation_challenge_set_reports_label_width_and_candidate_count():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        frozen_cases = build_independent_cases(session, case_count=20)
        challenge_cases = build_challenge_cases(session, case_count=20)
        result = evaluate_supplier_recommendations(
            session,
            challenge_cases,
            dataset_name="supplier_recommendation_challenge",
            dataset_version="challenge_v1",
        )

    assert len(frozen_cases) == 20
    assert len(challenge_cases) == 20
    assert {case.label_source for case in frozen_cases} == {"scenario_thresholds_v1"}
    assert {case.label_source for case in challenge_cases} == {"challenge_thresholds_v1"}
    assert result["dataset_name"] == "supplier_recommendation_challenge"
    assert result["dataset_version"] == "challenge_v1"
    assert result["reproduce_command"] == "python -m backend.evaluation.run_supplier_eval"
    assert result["label_width"]["min"] >= 1
    assert result["label_width"]["max"] <= 5
    assert result["candidate_count"]["min"] >= 3
    assert "price_sort_top3_hit_rate_percent" in result
    assert "composite_top3_hit_rate_percent" in result
