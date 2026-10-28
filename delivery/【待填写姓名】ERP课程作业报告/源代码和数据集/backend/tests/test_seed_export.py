import csv

from sqlalchemy import func, select

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import DemandHistory, Inventory, Material, Supplier
from backend.app.services.seed import seed_demo_data
from backend.app.services.seed_export import export_seed_dataset


def test_seed_data_has_phase_one_scale_and_inventory_snapshots():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)

        assert session.scalar(select(func.count()).select_from(Material)) == 10
        assert session.scalar(select(func.count()).select_from(Supplier)) == 10
        assert session.scalar(select(func.count()).select_from(Inventory)) == 10
        assert session.scalar(select(func.count()).select_from(DemandHistory)) == 10 * 540


def test_seed_dataset_export_writes_csv_and_metadata(tmp_path):
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        export_seed_dataset(session, tmp_path)

    expected = {
        "materials.csv",
        "inventory_snapshots.csv",
        "demand_history.csv",
        "suppliers.csv",
        "supplier_materials.csv",
        "supplier_performance.csv",
        "data_splits.csv",
        "generation_metadata.json",
    }
    assert expected.issubset({path.name for path in tmp_path.iterdir()})

    with (tmp_path / "data_splits.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["split"] for row in rows] == ["train", "validation", "test"]
    assert rows[-1]["end_date"] == "2026-10-09"
