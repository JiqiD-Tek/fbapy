#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : base.py
# @Created   : 2025/4/11 11:06

import time
import httpx
import asyncio

from dataclasses import dataclass
from typing import Optional, AsyncGenerator, List, Dict, Literal

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
            你是一个高效的对话助手，请以最直接的方式响应用户需求。
        """

    def __init__(
            self,
            api_key: str = "",
            base_url: str = "",
            model_name: str = "",
            timeout: Optional[float] = 60.0,
            read: Optional[float] = 60.0,
            write: Optional[float] = 30.0,
            http_client: Optional[httpx.AsyncClient] = None,
    ):
        """
           Args:
               api_key: 模型API密钥
               base_url: 基础请求地址
               model_name: 默认模型名称
               http_client: 自定义HTTP客户端
       """

        self.api_key: str = api_key
        self.base_url: str = base_url
        self.model_name: str = model_name
        self.timeout: float = timeout
        self.read: float = read
        self.write: float = write
        self._http_client: httpx.AsyncClient = http_client or self._create_http_client()
        self._async_client: Optional[AsyncOpenAI] = None

    def _create_http_client(self) -> httpx.AsyncClient:
        """大模型高并发专用HTTP客户端，具备：
        - 智能连接池
        - 流式长超时
        - 多层容错
        - 资源监控
        """
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=300.0
        )

        transport = httpx.AsyncHTTPTransport(
            retries=3,
            http2=True,
            limits=limits,
        )

        return httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(
                timeout=self.timeout,  # 全局超时兜底
                read=self.read,  # 读取超时
                write=self.write,  # 发送超时
                pool=10.0  # 连接池超时
            ),
            limits=limits,
            transport=transport,
            headers={"User-Agent": "ModelClient/2.0"},
            max_redirects=3,
            follow_redirects=True,
            verify=False,  # 可根据生产环境启用SSL验证
        )

    @property
    def async_client(self) -> AsyncOpenAI:
        """获取异步客户端(懒加载)"""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=self._http_client
            )
            log.debug("LLM异步客户端已初始化")
        return self._async_client

    async def query(
            self,
            text: str,
            system_prompt: Optional[str] = None,
            model_name: Optional[str] = None,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            config: Optional[LLMConfig] = None,
            extra_body: Optional[Dict] = None,
            stream: bool = False,
            **kwargs,
    ) -> AsyncGenerator[str, None] | str:
        """
                统一查询接口

                Args:
                    text: 用户输入文本
                    system_prompt: 自定义系统提示
                    model_name: 指定模型名称
                    conversation_history: 对话历史
                    config: 生成配置
                    extra_body: 其他配置
                    stream: 是否流式输出

                Returns:
                    流式模式返回AsyncGenerator，否则返回完整文本

                Raises:
                    RuntimeError: 模型调用失败
        """

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

    async def close(self) -> None:
        """关闭HTTP客户端和异步资源。

        确保所有连接和资源被正确释放。
        """
        if self._async_client is not None:
            await self._async_client.close()
            self._async_client = None
            log.debug("LLM异步客户端已关闭")
        if not self._http_client.is_closed:
            await self._http_client.aclose()
            log.debug("HTTP客户端已关闭")
