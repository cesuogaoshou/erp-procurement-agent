from pathlib import Path

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.services.seed import seed_demo_data
from backend.app.services.seed_export import export_seed_dataset


def main() -> None:
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        export_seed_dataset(session, Path("data/raw"))
    print("exported data/raw")


if __name__ == "__main__":
    main()
