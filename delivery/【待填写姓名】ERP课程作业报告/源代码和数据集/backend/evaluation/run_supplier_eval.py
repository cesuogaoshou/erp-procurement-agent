from sqlalchemy import create_engine

from backend.app.db.session import create_session_factory, create_sqlite_engine, session_scope
from backend.app.services.seed import seed_demo_data
from backend.evaluation.supplier_recommendation import (
    build_challenge_cases,
    build_independent_cases,
    evaluate_supplier_recommendations,
    write_cases_csv,
    write_result_json,
)


def main() -> None:
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        frozen_cases = build_independent_cases(session, case_count=60)
        challenge_cases = build_challenge_cases(session, case_count=60)
        frozen_result = evaluate_supplier_recommendations(
            session,
            frozen_cases,
            dataset_name="supplier_recommendation_frozen",
            dataset_version="frozen_v1",
        )
        challenge_result = evaluate_supplier_recommendations(
            session,
            challenge_cases,
            dataset_name="supplier_recommendation_challenge",
            dataset_version="challenge_v1",
        )
        result = {
            "run_name": "supplier_recommendation_eval",
            "data_version": "demo_seed_20261010",
            "seed": 20261010,
            "reproduce_command": "python -m backend.evaluation.run_supplier_eval",
            "outputs": {
                "frozen_cases": "data/raw/recommendation_cases.csv",
                "challenge_cases": "data/raw/recommendation_challenge_cases.csv",
                "result": "reports/generated/supplier_eval.json",
            },
            "frozen": frozen_result,
            "challenge": challenge_result,
        }
        write_cases_csv(frozen_cases, "data/raw/recommendation_cases.csv")
        write_cases_csv(challenge_cases, "data/raw/recommendation_challenge_cases.csv")
        write_result_json(result, "reports/generated/supplier_eval.json")
    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
