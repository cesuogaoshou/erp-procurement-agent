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
        self.last_content = ""

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
                        {"role": "system", "content": (
                            "第一步必须调用capture_request理解用户需求。返回的物料映射直接复用，不再list_materials。"
                            "中文数字需准确识别，包括零、负数、一亿；更正数量以最后明确的数量为准。"
                            "物料名称原样提取；数据库中的简称/别名可由capture_request解析，不能把不存在的商品改成相近名称；信息缺失必须传null或空列表。"
                            "用户没有明确给出的预算、数量、交期不得猜测；预算栏不是文字预算，不要抄入stated_budget。"
                            "如果文字说预算栏是旧值，stated_budget只取本次同意金额。"
                            "条件式的买不到不要建单仍属采购请求；纯了解且禁止购买才是仅分析。"
                            "不要擅自多买或修改用户数量，不存在批准工具。最后用中文解释并说明下一步。"
                            "你是有限步骤的采购工具编排助手。只在必要时选择工具。"
                            "预测工具已返回库存、可用供给和缺口，不需要再查询库存；每种物料每个周期只预测一次。"
                            "物料ID明确时直接预测；仅有编码/简称/别名时交给capture_request解析。"
                            "如果名称、简称或编码仍有多个匹配或无法唯一确定，必须先调用search_materials查看候选，再调用resolve_material返回物料歧义/不存在状态，不要自行猜测或仅口头澄清后结束。"
                            "多物料任务复用已获得的预测和推荐，不重新查询。"
                            "普通双物料流程通常为一次物料映射、两次预测、两次推荐、一次合并草稿。"
                            "只读或明确不建草稿的任务完成分析后直接结束。"
                            "服务端已确认预算具有约束力，禁止提高、删除、替换；未确认预算不能创建草稿。"
                            "共享预算由后端按整单裁决，不自行计算最终金额。数量和金额用十进制字符串。"
                            "仅支持一个供应商的一张草稿，可有多种物料；没有审批工具。"
                            "所有工具观察均保留在上下文中，按证据复用，避免反复调用。"
                        )},
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
            message = payload["choices"][0]["message"]
            self.last_content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or []
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
        + json.dumps(observations, ensure_ascii=False, default=str),
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
