import os

import pytest

from backend.app.config import load_project_env, openai_base_url_from_env
from backend.app.db.init_demo_data import initialize_demo_database, validate_demo_database_url
from backend.app.main import create_app
from backend.evaluation.run_real_model_acceptance import build_acceptance_config_report


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


def test_project_env_reports_source_without_secret_values(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_USER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "process-default-model")
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=https://api.deepseek.com\n"
        "OPENAI_MODEL_USER=env-file-user-model\n"
        "OPENAI_API_KEY=secret-value\n",
        encoding="utf-8",
    )

    loaded = load_project_env(tmp_path)

    assert loaded == tmp_path / ".env"
    assert os.environ["OPENAI_MODEL"] == "process-default-model"
    assert os.environ["OPENAI_MODEL_USER"] == "env-file-user-model"
    assert os.environ["OPENAI_API_KEY"] == "secret-value"


def test_openai_base_url_is_required_without_printing_secret(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")

    with pytest.raises(ValueError) as exc:
        openai_base_url_from_env()

    assert str(exc.value) == "OPENAI_BASE_URL_missing"
    assert "secret-value" not in str(exc.value)


def test_real_acceptance_config_report_records_non_secret_sources(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///process.sqlite")
    monkeypatch.setenv("OPENAI_MODEL", "process-model")
    monkeypatch.delenv("OPENAI_MODEL_USER", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite+pysqlite:///env-file.sqlite\n"
        "OPENAI_MODEL_USER=env-file-user-model\n"
        "OPENAI_BASE_URL=https://api.deepseek.com\n"
        "OPENAI_API_KEY=env-file-secret\n",
        encoding="utf-8",
    )

    load_project_env(tmp_path)
    report = build_acceptance_config_report()

    assert report["database_configured"] is True
    assert report["base_url_configured"] is True
    assert report["model_used"] == "env-file-user-model"
    assert report["config_sources"]["DATABASE_URL"] == "process_environment"
    assert report["config_sources"]["OPENAI_MODEL_USER"] == str(tmp_path / ".env")
    assert report["config_sources"]["OPENAI_API_KEY"] == "process_environment"
    assert "secret-value" not in str(report)
    assert "env-file-secret" not in str(report)


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
