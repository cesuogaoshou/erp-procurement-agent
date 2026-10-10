import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


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
        self.base_url = base_url
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
                        {"role": "tool", "content": str(observations[-5:])} if observations else {"role": "system", "content": "No observations yet."},
                    ],
                    "tool_choice": "auto",
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
            import json

            return ToolCall(name=function["name"], arguments=json.loads(function.get("arguments") or "{}"))
        except Exception as exc:
            raise ProviderError("provider_malformed_response") from exc
