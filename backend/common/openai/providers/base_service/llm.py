#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : llm.py
# @Created   : 2025/4/11 11:06

import time
import httpx
import asyncio

from dataclasses import dataclass
from typing import Optional, AsyncGenerator, List, Dict
from types import TracebackType

from openai import AsyncOpenAI

from backend.common.log import log


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
            api_key: str = "",
            base_url: str = "",
            model_name: str = "",
    ):

        self.api_key: str = api_key
        self.base_url: str = base_url
        self.model_name: str = model_name

        self.async_client: Optional[AsyncOpenAI] = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=httpx.AsyncClient(
                timeout=httpx.Timeout(connect=15.0, read=5.0, write=5.0, pool=5.0),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=50, max_keepalive_connections=50, keepalive_expiry=120
                ),
            )
        )

    async def query(
            self,
            text: str,
            system_prompt: Optional[str] = None,
            model_name: Optional[str] = None,
            conversation_history: Optional[List[Dict[str, str]]] = None,
            config: Optional[LLMConfig] = None,
            extra_body: Optional[Dict] = None,
            stream: bool = False,
            **kwargs,
    ) -> AsyncGenerator[str, None] | str:

        messages = self._build_messages(text, system_prompt, conversation_history)
        model_name = model_name or self.model_name
        llm_config = config or LLMConfig()

        try:
            if stream:
                return self._stream_response(
                    messages=messages,
                    model_name=model_name,
                    config=llm_config,
                    extra_body=extra_body,
                )

            return await self._async_response(
                messages=messages,
                model_name=model_name,
                config=llm_config,
                extra_body=extra_body,
            )

        except Exception as e:
            raise RuntimeError(f"LLM({self.__class__.__name__}) 请求异常 - {e}") from e

    async def _async_response(
            self,
            messages: List[Dict[str, str]],
            model_name: str,
            config: LLMConfig,
            extra_body: Optional[Dict] = None,
    ) -> str:
        try:
            start_time = time.monotonic()
            response = await self.async_client.chat.completions.create(
                messages=messages,
                model=model_name,
                **config.__dict__,
                extra_body=extra_body,
            )

            latency = time.monotonic() - start_time
            log.debug(f"LLM异步调用完成，模型: {model_name}, 耗时: {latency * 1000:.2f}ms")

            return response.choices[0].message.content

        except Exception as e:
            log.error(f"LLM 异步调用异常 - {e}")
            raise

    async def _stream_response(
            self,
            messages: List[Dict[str, str]],
            model_name: str,
            config: LLMConfig,
            extra_body: Optional[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        """处理流式响应"""
        try:
            async with asyncio.timeout(60):  # 流式响应超时保护
                start_time = time.monotonic()
                stream = await self.async_client.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    stream=True,
                    **config.__dict__,
                    extra_body=extra_body,
                )

                latency = time.monotonic() - start_time
                log.debug(f"LLM流式调用完成，模型: {model_name}, 耗时: {latency * 1000:.2f}ms")

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

        except asyncio.CancelledError:
            log.warning("LLM流式调用被终止")
            raise
        except Exception as e:
            log.error(f"LLM流式调用异常 - {e}")
            raise

    def _build_messages(
            self,
            text: str,
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

        messages.append({"role": "user", "content": text})
        return messages

    async def aclose(self) -> None:
        ...

    async def __aenter__(self):
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()
