#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : llm.py
# @Created   : 2025/4/11 11:06

import httpx
import asyncio

from dataclasses import dataclass
from typing import Optional, AsyncGenerator, List, Dict
from types import TracebackType

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypeAlias

from openai import AsyncOpenAI, NOT_GIVEN
from openai.types.chat import ChatCompletionToolParam
from openai.types.chat.chat_completion_chunk import Choice

from backend.common.log import log

from backend.common.agents.core.llm import utils
from backend.common.agents.core.llm.tool_context import (
    ProviderTool,
    FunctionTool,
    RawFunctionTool,
    is_raw_function_tool,
    get_raw_function_info,
    is_function_tool, function_tool
)


@dataclass
class LLMConfig:
    """大模型生成参数配置，影响意图识别和输出。

    属性:
        max_tokens: 最大生成文本长度（默认: 4096）。
        temperature: 控制输出随机性（0.0完全确定性，1.0高度随机，默认: 1.0）。
        top_p: 动态限制采样范围（默认: 0.7）。
        frequency_penalty: 惩罚重复token（默认: 0.0）。
        presence_penalty: 惩罚已出现token（默认: 0.5）。
    """
    max_tokens: int = 4096
    temperature: float = 1.0
    top_p: float = 0.7
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.5

    def __post_init__(self) -> None:
        """验证配置参数。"""
        if self.max_tokens <= 0:
            raise ValueError("max_tokens必须为正整数")
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError("temperature必须在[0.0, 1.0]范围内")
        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError("top_p必须在[0.0, 1.0]范围内")
        if not -2.0 <= self.frequency_penalty <= 2.0:
            raise ValueError("frequency_penalty必须在[-2.0, 2.0]范围内")
        if not -2.0 <= self.presence_penalty <= 2.0:
            raise ValueError("presence_penalty必须在[-2.0, 2.0]范围内")


class CompletionUsage(BaseModel):
    completion_tokens: int
    """The number of tokens in the completion."""
    prompt_tokens: int
    """The number of input tokens used (includes cached tokens)."""
    prompt_cached_tokens: int = 0
    """The number of cached input tokens used."""
    cache_creation_tokens: int = 0
    """The number of tokens used to create the cache."""
    cache_read_tokens: int = 0
    """The number of tokens read from the cache."""
    total_tokens: int
    """The total number of tokens used (completion + prompt tokens)."""


class FunctionToolCall(BaseModel):
    type: Literal["function"] = "function"
    name: str
    arguments: str
    call_id: str
    extra: dict[str, Any] | None = None
    """Provider-specific extra data (e.g., Google thought signatures)."""


ChatRole: TypeAlias = Literal["developer", "system", "user", "assistant"]


class ChoiceDelta(BaseModel):
    role: ChatRole | None = None
    content: str | None = None
    tool_calls: list[FunctionToolCall] = Field(default_factory=list)
    extra: dict[str, Any] | None = None
    """Provider-specific extra data (e.g., Google thought signatures)."""


class ChatChunk(BaseModel):
    id: str
    delta: ChoiceDelta | None = None
    usage: CompletionUsage | None = None


class LLM:
    """智能对话引擎

    特性：
    - 动态提示词管理
    - 自适应HTTP连接池
    - 全异步IO支持
    """
    MODEL_NAMES = []  # 支持的模型名称
    LITE_MODEL_NAME: str = ''  # 使用最小模型, 做意图识别
    THINK_MODEL_NAME: str = ''  # 推理模型

    @property
    def system_prompt(self) -> str:
        """默认系统提示词。"""
        return """
            You are a helpful assistant. Keep your responses concise and to the point.
        """

    def __init__(
            self,
            api_key: str = '',
            base_url: str = '',
            model_name: str = '',
            tools: list[FunctionTool | RawFunctionTool | ProviderTool] = None,
            strict_tool_schema: bool = True,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

        self._tools = tools
        self._strict_tool_schema = strict_tool_schema

        self.async_client = None

    async def query(
            self,
            user_prompt: str,
            system_prompt: Optional[str] = None,
            model_name: Optional[str] = None,
            conversation_history: Optional[List[Dict[str, str]]] = None,
            config: Optional[LLMConfig] = None,
            extra_body: Optional[Dict] = None,
            **kwargs,
    ) -> AsyncGenerator[ChatChunk, None]:
        messages = self._build_messages(user_prompt, system_prompt, conversation_history)
        model_name = model_name or self.model_name
        llm_config = config or LLMConfig()

        self._tool_call_id: str | None = None
        self._fnc_name: str | None = None
        self._fnc_raw_arguments: str | None = None
        self._tool_extra: dict[str, Any] | None = None
        self._tool_index: int | None = None

        fnc_ctx = (
            to_fnc_ctx(self._tools, strict=self._strict_tool_schema)
            if self._tools
            else NOT_GIVEN
        )

        try:
            stream = await self.async_client.chat.completions.create(
                messages=messages,
                model=model_name,
                stream=True,
                tools=fnc_ctx,
                **llm_config.__dict__,
                extra_body=extra_body,
            )

            thinking = asyncio.Event()
            async with stream:
                async for chunk in stream:
                    for choice in chunk.choices:
                        chat_chunk = self._parse_choice(chunk.id, choice, thinking)
                        if chat_chunk is not None:
                            yield chat_chunk

        except asyncio.CancelledError:
            log.warning("LLM流式调用被终止")
            raise
        except Exception as e:
            log.error(f"LLM流式调用异常 - {e}")
            raise

    def _parse_choice(
            self, id: str, choice: Choice, thinking: asyncio.Event
    ) -> ChatChunk | None:
        delta = choice.delta

        # https://github.com/livekit/agents/issues/688
        # the delta can be None when using Azure OpenAI (content filtering)
        if delta is None:
            return None

        if delta.tool_calls:
            for tool in delta.tool_calls:
                if not tool.function:
                    continue

                call_chunk = None
                if self._tool_call_id and tool.id and tool.index != self._tool_index:
                    call_chunk = ChatChunk(
                        id=id,
                        delta=ChoiceDelta(
                            role="assistant",
                            content=delta.content,
                            tool_calls=[
                                FunctionToolCall(
                                    arguments=self._fnc_raw_arguments or "",
                                    name=self._fnc_name or "",
                                    call_id=self._tool_call_id or "",
                                    extra=self._tool_extra,
                                )
                            ],
                        ),
                    )
                    self._tool_call_id = self._fnc_name = self._fnc_raw_arguments = None
                    self._tool_extra = None

                if tool.function.name:
                    self._tool_index = tool.index
                    self._tool_call_id = tool.id
                    self._fnc_name = tool.function.name
                    self._fnc_raw_arguments = tool.function.arguments or ""
                    # Extract extra from tool call (e.g., Google thought signatures)
                    self._tool_extra = getattr(tool, "extra_content", None)
                elif tool.function.arguments:
                    self._fnc_raw_arguments += tool.function.arguments  # type: ignore

                if call_chunk is not None:
                    return call_chunk

        if choice.finish_reason in ("tool_calls", "stop") and self._tool_call_id:
            call_chunk = ChatChunk(
                id=id,
                delta=ChoiceDelta(
                    role="assistant",
                    content=delta.content,
                    tool_calls=[
                        FunctionToolCall(
                            arguments=self._fnc_raw_arguments or "",
                            name=self._fnc_name or "",
                            call_id=self._tool_call_id or "",
                            extra=self._tool_extra,
                        )
                    ],
                ),
            )
            self._tool_call_id = self._fnc_name = self._fnc_raw_arguments = None
            self._tool_extra = None
            return call_chunk

        delta.content = utils.strip_thinking_tokens(delta.content, thinking)

        # Extract extra from delta (e.g., Google thought signatures on text parts)
        delta_extra = getattr(delta, "extra_content", None)

        if not delta.content and not delta_extra:
            return None

        return ChatChunk(
            id=id,
            delta=ChoiceDelta(
                content=delta.content,
                role="assistant",
                extra=delta_extra,
            ),
        )

    def _build_messages(
            self,
            user_prompt: str,
            system_prompt: Optional[str],
            history: Optional[List[Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = [{"role": "system", "content": system_prompt or self.system_prompt}]

        if history:
            messages.extend([
                {"role": role, "content": content}
                for turn in history
                for role, content in [("user", turn["user"]), ("assistant", turn["assistant"])]
            ])

        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def aclose(self) -> None:
        """
        关闭 LLM 客户端，释放底层 HTTP 连接资源
        """
        client = self.async_client
        self.async_client = None

        if client is not None:
            try:
                await client.close()
            except Exception as e:
                log.error(f"关闭 AsyncOpenAI client 失败: {e}")

    async def __aenter__(self):
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()


def to_fnc_ctx(
        fnc_ctx: Sequence[FunctionTool | RawFunctionTool | ProviderTool],
        *,
        strict: bool = True,
) -> list[ChatCompletionToolParam]:
    tools: list[ChatCompletionToolParam] = []
    for fnc in fnc_ctx:
        if is_raw_function_tool(fnc):
            info = get_raw_function_info(fnc)
            tools.append(
                {
                    "type": "function",
                    "function": info.raw_schema,  # type: ignore
                }
            )
        elif is_function_tool(fnc):
            schema = (
                utils.build_strict_openai_schema(fnc)
                if strict
                else utils.build_legacy_openai_schema(fnc)
            )
            tools.append(schema)  # type: ignore

    return tools
