from sqlalchemy import create_engine

from backend.app.db.session import create_session_factory, create_sqlite_engine, session_scope
from backend.app.services.seed import seed_demo_data
from backend.evaluation.supplier_recommendation import (
    build_independent_cases,
    evaluate_supplier_recommendations,
    write_cases_csv,
    write_result_json,
)


def main() -> None:
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        cases = build_independent_cases(session, case_count=60)
        result = evaluate_supplier_recommendations(session, cases)
        write_cases_csv(cases, "data/raw/recommendation_cases.csv")
        write_result_json(result, "reports/generated/supplier_eval.json")
    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
