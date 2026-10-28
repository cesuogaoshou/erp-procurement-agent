import os
import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from backend.app.services.agent_tools import build_agent_tools


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


class LLMProvider(Protocol):
    def next_tool_call(self, prompt: str, observations: list[dict[str, Any]]) -> ToolCall | None:
        raise NotImplementedError


class ProviderError(RuntimeError):
    pass


class MockLLMProvider:
    def __init__(self, calls: list[ToolCall], error: ProviderError | None = None) -> None:
        self._calls = list(calls)
        self._error = error
        self.real_function_calling = False

    def next_tool_call(self, prompt: str, observations: list[dict[str, Any]]) -> ToolCall | None:
        if self._error is not None:
            raise self._error
        if not self._calls:
            return None
        return self._calls.pop(0)


class OpenAIFunctionCallingProvider:
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1/chat/completions",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = _chat_completions_url(base_url)
        self.timeout_seconds = timeout_seconds
        self.real_function_calling = True

    def next_tool_call(self, prompt: str, observations: list[dict[str, Any]]) -> ToolCall | None:
        if not self.api_key:
            raise ProviderError("llm_credentials_missing")
        try:
            response = httpx.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Use procurement tools only when needed."},
                        {"role": "user", "content": prompt},
                        _observation_message(observations),
                    ],
                    "tool_choice": "auto",
                    "tools": _openai_tool_schemas(),
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderError("provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"provider_http_error:{exc.__class__.__name__}") from exc
        try:
            tool_calls = payload["choices"][0]["message"].get("tool_calls") or []
            if not tool_calls:
                return None
            function = tool_calls[0]["function"]
            return ToolCall(name=function["name"], arguments=json.loads(function.get("arguments") or "{}"))
        except Exception as exc:
            raise ProviderError("provider_malformed_response") from exc


def _observation_message(observations: list[dict[str, Any]]) -> dict[str, str]:
    if not observations:
        return {"role": "system", "content": "No observations yet."}
    return {
        "role": "system",
        "content": "Recent tool observations: "
        + json.dumps(observations[-5:], ensure_ascii=False, default=str),
    }


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def model_from_env() -> str | None:
    return os.getenv("OPENAI_MODEL_USER") or os.getenv("OPENAI_MODEL")


def _openai_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in build_agent_tools()
    ]
