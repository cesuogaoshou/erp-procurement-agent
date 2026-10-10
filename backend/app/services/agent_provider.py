from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


class LLMProvider(Protocol):
    def next_tool_call(self, prompt: str, observations: list[dict[str, Any]]) -> ToolCall | None:
        raise NotImplementedError


class MockLLMProvider:
    def __init__(self, calls: list[ToolCall]) -> None:
        self._calls = list(calls)
        self.real_function_calling = False

    def next_tool_call(self, prompt: str, observations: list[dict[str, Any]]) -> ToolCall | None:
        if not self._calls:
            return None
        return self._calls.pop(0)
