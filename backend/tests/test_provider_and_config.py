import os

from backend.app.services.agent_provider import OpenAIFunctionCallingProvider, ProviderError
from backend.app.services.auth import auth_secret_from_env


def test_openai_provider_reports_missing_credentials_without_calling_network(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIFunctionCallingProvider(model="gpt-test")

    try:
        provider.next_tool_call("hello", [])
    except ProviderError as exc:
        assert str(exc) == "llm_credentials_missing"
    else:
        raise AssertionError("expected ProviderError")


def test_auth_secret_reads_environment_and_rejects_empty(monkeypatch):
    monkeypatch.setenv("ERP_AUTH_SECRET", "local-demo-secret")
    assert auth_secret_from_env() == "local-demo-secret"

    monkeypatch.setenv("ERP_AUTH_SECRET", "")
    try:
        auth_secret_from_env()
    except ValueError as exc:
        assert str(exc) == "ERP_AUTH_SECRET_empty"
    else:
        raise AssertionError("expected empty secret rejection")
