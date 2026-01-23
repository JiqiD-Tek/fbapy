#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : llm.py
# @Created   : 2025/4/11 11:06

import asyncio

from dataclasses import dataclass
from typing import Any, Literal, AsyncIterator, cast
from types import TracebackType
from collections.abc import Sequence
from pydantic import BaseModel, Field
from typing_extensions import TypeAlias

from openai import NOT_GIVEN
from openai.types.chat import ChatCompletionToolParam, ChatCompletionMessageParam
from openai.types.chat.chat_completion_chunk import Choice

from backend.common.log import log

from backend.app.live.agents.core.llm.chat_context import ChatContext
from backend.app.live.agents.core.utils import aio
from backend.app.live.agents.core.llm import utils
from backend.app.live.agents.core.llm.tool_context import (
    ProviderTool,
    FunctionTool,
    RawFunctionTool,
    is_raw_function_tool,
    get_raw_function_info,
    is_function_tool
)


@dataclass
class ChatCompletionOptions:
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
    def __init__(self, model: str):
        self.model = model
        self._client = None

    def chat(
            self,
            chat_ctx: ChatContext,
            tools: list[FunctionTool | RawFunctionTool | ProviderTool] = None,
    ):
        return LLMStream(
            self,
            model=self.model,
            chat_ctx=chat_ctx,
            tools=tools,
            strict_tool_schema=True,
            extra_kwargs=ChatCompletionOptions().__dict__,
        )

    async def aclose(self) -> None:
        client = self._client
        self._client = None

        if client is not None:
            try:
                await client.close()
            except Exception as e:
                log.error(f"关闭 AsyncOpenAI client 失败: {e}")

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()


class LLMStream:

    def __init__(
            self,
            llm: LLM,
            model: str,
            chat_ctx: ChatContext,
            tools: list[FunctionTool | RawFunctionTool | ProviderTool],
            strict_tool_schema: bool,
            extra_kwargs: dict[str, Any],
            provider_fmt: str = "openai",  # used internally for chat_ctx format

    ):
        self._llm = llm
        self._model = model
        self._chat_ctx = chat_ctx
        self._tools = tools
        self._strict_tool_schema = strict_tool_schema
        self._extra_kwargs = extra_kwargs
        self._provider_fmt = provider_fmt

        self._event_ch = aio.Chan[ChatChunk]()
        self._task = asyncio.create_task(self._main_task(), name="LLM._main_task")
        self._task.add_done_callback(lambda _: self._event_ch.close())

    async def _main_task(self):
        self._tool_call_id: str | None = None
        self._fnc_name: str | None = None
        self._fnc_raw_arguments: str | None = None
        self._tool_extra: dict[str, Any] | None = None
        self._tool_index: int | None = None

        chat_ctx, _ = self._chat_ctx.to_provider_format(format=self._provider_fmt)

        fnc_ctx = (
            to_fnc_ctx(self._tools, strict=self._strict_tool_schema)
            if self._tools
            else NOT_GIVEN
        )
        try:
            stream = await self._llm._client.chat.completions.create(
                messages=cast(list[ChatCompletionMessageParam], chat_ctx),
                model=self._model,
                stream=True,
                stream_options={"include_usage": True},
                tools=fnc_ctx,
            )

            thinking = asyncio.Event()
            async with stream:
                async for chunk in stream:
                    for choice in chunk.choices:
                        chat_chunk = self._parse_choice(chunk.id, choice, thinking)
                        if chat_chunk is not None:
                            self._event_ch.send_nowait(chat_chunk)

                        if chunk.usage is not None:
                            tokens_details = chunk.usage.prompt_tokens_details
                            cached_tokens = tokens_details.cached_tokens if tokens_details else 0
                            chunk = ChatChunk(
                                id=chunk.id,
                                usage=CompletionUsage(
                                    completion_tokens=chunk.usage.completion_tokens,
                                    prompt_tokens=chunk.usage.prompt_tokens,
                                    prompt_cached_tokens=cached_tokens or 0,
                                    total_tokens=chunk.usage.total_tokens,
                                ),
                            )
                            self._event_ch.send_nowait(chunk)

        except asyncio.CancelledError:
            log.warning("LLMStream 调用被终止")
            raise
        except Exception as e:
            log.error(f"LLMStream 调用异常 - {e}")
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

    async def aclose(self) -> None:
        await aio.cancel_and_wait(self._task)

    async def __anext__(self) -> ChatChunk:
        try:
            val = await self._event_ch.__anext__()
        except StopAsyncIteration:
            if not self._task.cancelled() and (exc := self._task.exception()):
                raise exc  # noqa: B904

            raise StopAsyncIteration from None

        return val

    def __aiter__(self) -> AsyncIterator[ChatChunk]:
        return self

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
