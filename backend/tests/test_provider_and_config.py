import os

from backend.app.services.agent_provider import OpenAIFunctionCallingProvider, ProviderError, model_from_env
from backend.app.services.agent_tools import build_agent_tools
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


def test_openai_provider_sends_agent_tool_schemas_and_excludes_approval_tools(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "list_materials",
                                        "arguments": "{}",
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("backend.app.services.agent_provider.httpx.post", fake_post)
    provider = OpenAIFunctionCallingProvider(model="deepseek-v4-flash", api_key="test-key")

    call = provider.next_tool_call("need procurement help", [])

    assert call.name == "list_materials"
    payload = captured["json"]
    assert payload["tool_choice"] == "auto"
    assert [tool["type"] for tool in payload["tools"]] == ["function"] * len(build_agent_tools())
    function_names = [tool["function"]["name"] for tool in payload["tools"]]
    assert function_names == [tool.name for tool in build_agent_tools()]
    assert "approve_order" not in function_names
    assert "reject_order" not in function_names
    assert payload["tools"][-1]["function"]["name"] == "create_purchase_draft"
    assert "evidence_refs" in payload["tools"][-1]["function"]["parameters"]["required"]


def test_openai_provider_accepts_openai_compatible_base_root(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"tool_calls": []}}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        return Response()

    monkeypatch.setattr("backend.app.services.agent_provider.httpx.post", fake_post)
    provider = OpenAIFunctionCallingProvider(
        model="deepseek-v4-flash",
        api_key="test-key",
        base_url="https://api.deepseek.com",
    )

    call = provider.next_tool_call("continue", [])

    assert call is None
    assert captured["url"] == "https://api.deepseek.com/chat/completions"


def test_openai_provider_serializes_observations_as_system_context_not_tool_messages(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"tool_calls": []}}]}

    def fake_post(url, *, headers, json, timeout):
        captured["json"] = json
        return Response()

    monkeypatch.setattr("backend.app.services.agent_provider.httpx.post", fake_post)
    provider = OpenAIFunctionCallingProvider(model="deepseek-v4-flash", api_key="test-key")

    call = provider.next_tool_call("continue", [{"tool": "list_materials", "output": [{"id": 1}]}])

    assert call is None
    roles = [message["role"] for message in captured["json"]["messages"]]
    assert roles == ["system", "user", "system"]
    assert "Recent tool observations:" in captured["json"]["messages"][-1]["content"]


def test_requirements_include_cryptography_for_mysql8_caching_sha2_password():
    with open("requirements.txt", encoding="utf-8") as requirements:
        packages = {line.strip().split("==")[0].lower() for line in requirements if line.strip()}

    assert "cryptography" in packages


def test_model_from_env_prefers_user_model_over_default_model(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_MODEL_USER", "deepseek-v4-flash")

    assert model_from_env() == "deepseek-v4-flash"

    monkeypatch.delenv("OPENAI_MODEL_USER", raising=False)
    assert model_from_env() == "gpt-4o-mini"


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
