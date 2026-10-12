import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_SOURCES: dict[str, str] = {}
_ENV_SOURCE_VALUES: dict[str, str] = {}


def load_project_env(project_root: Path | str = PROJECT_ROOT) -> Path | None:
    env_path = Path(project_root) / ".env"
    if not env_path.exists():
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if key in os.environ:
            _ENV_SOURCES[key] = "process_environment"
            _ENV_SOURCE_VALUES[key] = os.environ[key]
            continue
        os.environ[key] = value
        _ENV_SOURCES[key] = str(env_path)
        _ENV_SOURCE_VALUES[key] = value
    return env_path


def openai_base_url_from_env() -> str:
    value = os.getenv("OPENAI_BASE_URL")
    if not value:
        raise ValueError("OPENAI_BASE_URL_missing")
    return value


def env_source(key: str) -> str | None:
    value = os.getenv(key)
    if value is None:
        return None
    if _ENV_SOURCE_VALUES.get(key) == value:
        return _ENV_SOURCES.get(key, "process_environment")
    return "process_environment"
