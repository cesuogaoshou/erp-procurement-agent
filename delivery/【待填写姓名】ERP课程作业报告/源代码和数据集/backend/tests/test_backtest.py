from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.services.seed import seed_demo_data
from backend.evaluation.run_baseline import run_shortage_backtest


def test_backtest_uses_many_material_cutoffs_and_orders_train_before_holdout():
    engine = create_sqlite_engine("sqlite+pysqlite:///:memory:")
    with session_scope(engine) as session:
        seed_demo_data(session)
        result = run_shortage_backtest(session)

    windows = result["backtest_windows"]
    assert result["shortage_metrics"]["sample_count"] >= 100
    assert len(windows) == result["shortage_metrics"]["sample_count"]
    assert result["shortage_metrics"]["mape_coverage_percent"] is not None
    for window in windows:
        assert window["train_end"] < window["holdout_start"]
        assert window["cutoff_date"] == window["holdout_start"]
        assert window["holdout_end"] <= "2026-10-09"
