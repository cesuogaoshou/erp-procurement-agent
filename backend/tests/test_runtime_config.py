import os

import pytest

from backend.app.config import load_project_env, openai_base_url_from_env
from backend.app.db.init_demo_data import initialize_demo_database, validate_demo_database_url
from backend.app.main import create_app


def test_project_env_loads_from_repo_root_without_overriding_process_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL_USER", "process-model")
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=https://api.deepseek.com\n"
        "OPENAI_MODEL_USER=env-file-model\n"
        "OPENAI_API_KEY=should-not-be-printed\n",
        encoding="utf-8",
    )

    loaded = load_project_env(tmp_path)

    assert loaded == tmp_path / ".env"
    assert os.environ["OPENAI_BASE_URL"] == "https://api.deepseek.com"
    assert os.environ["OPENAI_MODEL_USER"] == "process-model"


def test_openai_base_url_is_required_without_printing_secret(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")

    with pytest.raises(ValueError) as exc:
        openai_base_url_from_env()

    assert str(exc.value) == "OPENAI_BASE_URL_missing"
    assert "secret-value" not in str(exc.value)


def test_demo_reset_rejects_non_demo_database_url():
    with pytest.raises(ValueError) as exc:
        validate_demo_database_url("mysql+pymysql://erp_user:pass@127.0.0.1:3306/erp_prod")

    assert str(exc.value) == "demo_database_required"


def test_demo_reset_accepts_explicit_demo_database_url():
    validate_demo_database_url("mysql+pymysql://erp_user:pass@127.0.0.1:3306/erp_demo")
    validate_demo_database_url("sqlite+pysqlite:///./demo_erp.sqlite")


def test_create_app_uses_database_url_from_environment(monkeypatch, tmp_path):
    db_path = tmp_path / "demo_app.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")

    app = create_app()

    assert str(app.state.engine.url).endswith(db_path.as_posix())


def test_initialize_demo_database_creates_sqlite_demo_schema(tmp_path):
    db_path = tmp_path / "erp_demo.sqlite"
    counts = initialize_demo_database(f"sqlite+pysqlite:///{db_path.as_posix()}")

    assert counts["materials"] == 10
    assert counts["purchase_orders"] == 0
