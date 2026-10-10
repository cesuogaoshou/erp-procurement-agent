from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.services.seed import seed_demo_data
from backend.evaluation.supplier_recommendation import (
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
