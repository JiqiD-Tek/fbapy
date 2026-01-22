#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Project : jiqid-py
@File    : assistant.py
@Author  : guhua@jiqid.com
@Created : 2025/05/20 10:49
"""

import asyncio
import traceback

from typing import Callable, Any

from backend.app.live.agents.core.llm import ChatContext
from backend.common.log import log
from backend.utils.timezone import TimeZone

from backend.app.live.agents.prompt import SYSTEM_PROMPT
from backend.app.live.agents.tools import get_weather

from backend.app.live.agents.providers.coze.stt import CozeSTT as STT
from backend.app.live.agents.providers.coze.tts import CozeTTS as TTS
from backend.app.live.agents.providers.coze.llm import CozeLLM as LLM


class Assistant:
    """大模型服务的高并发客户端(意图识别、内容生成) """

    def __init__(self, uid: str, chat_config=None):
        """ 初始化大模型服务客户端 """
        self.uid = uid
        self.username = chat_config.parameters.get("username", "Lover")
        self.language = chat_config.parameters.get("language", "zh-CN")
        self.tz = chat_config.parameters.get("timezone", "Asia/Shanghai")

        self.stt = STT(language=self.language)
        self.tts = TTS(language=self.language)
        self.llm = LLM()

        self.chat_ctx = ChatContext()
        self.chat_ctx.add_message(role="system", content=SYSTEM_PROMPT)

        self._is_active: asyncio.Event = asyncio.Event()
        self._is_active.set()

        log.info(f"Assistant 初始化完成 [UID:{self.uid}]")

    async def chat(self, user_input: str, on_token=None, on_finish=None, on_error=None) -> None:
        """ 执行流式文本生成查询 """
        content = self.render_user_prompt(user_input)
        self.chat_ctx.add_message(role="user", content=content)

        stream = await self.llm.chat(
            chat_ctx=self.chat_ctx,
            tools=[get_weather],
        )

        content = ""
        try:
            async for chat_chunk in stream:
                if not self._is_active.is_set():
                    log.debug("流数据处理器关闭")
                    raise asyncio.CancelledError

                if chat_chunk.usage:  # 使用统计
                    log.debug(f"使用统计 [{chat_chunk.usage}]")
                    continue

                if chat_chunk.delta.tool_calls:  # 工具调用
                    continue

                await self._invoke(on_token, chat_chunk.delta.content)
                content += chat_chunk.delta.content
                self.tts.push_text(token=chat_chunk.delta.content)

            await self._invoke(on_finish, content)
            self.chat_ctx.add_message(role="assistant", content=content)
            self.chat_ctx.truncate(max_items=5)

        except asyncio.CancelledError:
            log.warning(f"流处理被取消 - {traceback.format_exc()}", exc_info=True)
            raise
        except Exception as ex:
            log.error(f"流处理错误 - {ex} - {traceback.format_exc()}", exc_info=True)
            if on_error:
                await self._invoke(on_error, ex)
            raise
        finally:
            log.debug("流处理完成")
            self.tts.flush()

    @staticmethod
    async def _invoke(callback: Callable, *args: Any) -> None:
        """ 安全调用回调函数 """
        try:
            await callback(*args)
        except Exception as ex:
            log.error(f"回调执行失败 [callback: {callback.__name__} - {ex} - {traceback.format_exc()}]")

    async def aclose(self) -> None:
        """安全关闭活跃流"""
        self._is_active.clear()

        await asyncio.gather(
            self.stt.aclose(),
            self.tts.aclose(),
            self.llm.aclose(),
        )

        log.debug(f"LLM客户端关闭完成 [UID:{self.uid}]")

    def render_user_prompt(self, text: str, api_data=None):
        """初始化用户提示"""
        now = TimeZone(tz=self.tz).now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        current_weekday = now.strftime("%A")

        api_data_block = f"""- API data:
        ```json
        {api_data}
        ```""" if api_data else ""

        user_prompt = f"""
        Context:
        - Language: {self.language}
        - User name: {self.username}
        - Time: {current_time} ({current_weekday})
        {api_data_block}

        Instructions:
        - Respond naturally and politely to the user's message
        - Use {self.language} only
        - Be concise and clear
        - Do NOT explain your reasoning
        - Do NOT use emojis or emoticons
        - Output plain text only

        User message:
        {text}
        """

        return user_prompt.strip()
