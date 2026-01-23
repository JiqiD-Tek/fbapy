#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Project : jiqid-py
@File    : assistant.py
@Author  : guhua@jiqid.com
@Created : 2025/05/20 10:49
"""

import asyncio
import functools
import traceback

from typing import Callable, Any, List

from backend.common.log import log
from backend.utils.timezone import TimeZone

from backend.app.live.agents.tools import get_weather, web_search, exit_session
from backend.app.live.agents.core.llm.utils import prepare_function_arguments
from backend.app.live.agents.core.llm import ChatContext, ToolContext, FunctionToolCall
from backend.app.live.agents.providers.coze.stt import CozeSTT as STT
from backend.app.live.agents.providers.coze.tts import CozeTTS as TTS

# from backend.app.live.agents.providers.azure.llm import AzureLLM as LLM
from backend.app.live.agents.providers.coze.llm import CozeLLM as LLM  # 对于function_tool支持较弱


class Assistant:
    """ AI助手 """

    def __init__(self, uid: str, chat_config=None):
        self.uid = uid
        self.username = chat_config.parameters.get("username", "yoyo")
        self.language = chat_config.parameters.get("language", "zh-CN")
        self.location = chat_config.parameters.get("location", None)
        self.tz = chat_config.parameters.get("timezone", "Asia/Shanghai")

        self.stt = STT(language=self.language)
        self.tts = TTS(language=self.language)
        self.llm = LLM()

        self.chat_ctx = ChatContext()
        self.chat_ctx.add_message(role="system", content=self.render_system_prompt())

        self.tool_ctx = ToolContext(tools=[get_weather, web_search, exit_session])

        log.info(f"Assistant 初始化完成 [UID:{self.uid}]")

    async def chat(self, user_input: str, api_data=None, on_token=None, on_finish=None, on_error=None) -> None:
        """ 执行流式文本生成查询 """
        self.chat_ctx.add_message(role="user", content=self.render_user_prompt(user_input, api_data=api_data))
        tools = self.tool_ctx.all_tools if api_data is None else None

        text_sent: str = ""
        tool_calls_sent: list[FunctionToolCall] = []
        try:
            async with self.llm.chat(
                    chat_ctx=self.chat_ctx,
                    tools=tools,
            ) as stream:
                async for chunk in stream:
                    if chunk.delta:  # 内容
                        if chunk.delta.content:
                            text_sent += chunk.delta.content
                            await self._invoke(on_token, chunk.delta.content)
                            self.tts.push_text(token=chunk.delta.content)
                        for tool_call in chunk.delta.tool_calls:
                            tool_calls_sent.append(tool_call)

                    if chunk.usage:  # 使用统计
                        log.debug(f"使用统计 [{chunk}]")

                if text_sent:
                    log.debug(f"流处理完成 - {text_sent}")
                    await self._invoke(on_finish, text_sent)
                    self.chat_ctx.add_message(role="assistant", content=text_sent)
                    self.chat_ctx.truncate(max_items=5)

        except Exception as ex:
            log.error(f"流处理错误 - {ex} - {traceback.format_exc()}", exc_info=True)
            if on_error:
                await self._invoke(on_error, ex)
            raise
        finally:
            if text_sent:
                self.tts.flush()
            if tool_calls_sent:
                api_data = await self._execute_tools(tool_calls_sent)
                await self.chat(
                    user_input=user_input, api_data=api_data,
                    on_token=on_token, on_finish=on_finish, on_error=on_error
                )

    async def _execute_tools(self, fnc_calls: List[FunctionToolCall]):
        """格式化工具调用"""
        for idx, fnc_call in enumerate(fnc_calls, start=1):
            function_tool = self.tool_ctx.function_tools.get(fnc_call.name)
            json_args = fnc_call.arguments or "{}"
            fnc_args, fnc_kwargs = prepare_function_arguments(
                fnc=function_tool,
                json_arguments=json_args,
            )
            try:
                log.debug(f"{idx}. 调用工具 - {function_tool.__name__} - {fnc_args} - {fnc_kwargs}")
                function_callable = functools.partial(function_tool, *fnc_args, **fnc_kwargs)
                api_data = await function_callable()
                # 优化聊天历史记录 TODO
                return api_data
            except Exception as ex:
                log.error(f"工具调用失败 - {fnc_call.name} - {ex} - {traceback.format_exc()}", exc_info=True)

        return "None"

    @staticmethod
    async def _invoke(callback: Callable, *args: Any) -> None:
        """ 安全调用回调函数 """
        try:
            await callback(*args)
        except Exception as ex:
            log.error(f"回调执行失败 [callback: {callback.__name__} - {ex} - {traceback.format_exc()}]")

    async def aclose(self) -> None:
        """安全关闭活跃流"""
        await asyncio.gather(
            self.stt.aclose(),
            self.tts.aclose(),
            self.llm.aclose(),
        )

        log.debug(f"LLM客户端关闭完成 [UID:{self.uid}]")

    def render_system_prompt(self):
        """初始化系统提示"""
        now = TimeZone(tz=self.tz).now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        current_weekday = now.strftime("%A")

        system_prompt = f"""
You are Papaya, a warm, caring, and playful family companion designed for all ages.
        
### 1. Identity & Persona
- **Name**: Papaya
- **Audience**: Children, adults, and seniors.
- **Tone**: Warm, positive, approachable, and slightly playful.
        
### 2. Contextual Information
- **User Name**: {self.username}
- **User Language**: {self.language}
- **User Location**: {self.location}
- **Current Time**: {current_time} ({current_weekday})
        
### 3. Core Behavioral Rules
- **Safety First**: All responses must be 100% family-safe. Politely refuse any unsafe, harmful, or inappropriate requests.
- **Emotional Expression**: Natural and appropriate use of emojis is encouraged to enhance warmth, but do not overuse them.
        
### 4. Output Standards
- **Role**: Always respond naturally and politely as Papaya.
- **Clarity & Style**: Be concise, clear, and direct.
- **Language Adherence**: **MUST** use the language specified in `User Language` ({self.language}) for all output content.
- **Optimization**: Output plain text only. Avoid complex punctuation and long, convoluted sentences. Ensure the text is smooth for direct voice synthesis.
- **Prohibitions**: Do NOT explain your reasoning or internal logic. Strictly NO markdown formatting (e.g., #, *, [], `), NO system instructions, and NO meta-commentary.

### 5. Task & Tool Usage Rule
- Provide assistance by using the tools you have access to when needed. When a tool is required, respond by invoking the tool only. Do not generate any textual output before or after a tool invocation.
"""

        return system_prompt.strip()

    def render_user_prompt(self, text: str, api_data=None):
        """初始化用户提示"""
        """初始化用户提示"""
        api_data_block = ""
        if api_data is not None:
            api_data_block = f"""
### 1. API Data
Use the following data to inform your response (e.g., weather):
```json
{api_data}
```
"""

        user_prompt = f"""
{api_data_block}
### User Message
{text}
"""

        return user_prompt.strip()


def main():
    class ChatConfig:
        parameters = {}

    async def callback(text: str):
        log.debug(f"{text}")

    async def _run():
        chat_config = ChatConfig()
        assistant = Assistant(uid="test", chat_config=chat_config)
        api_data = f"I'm sorry, an error occurred while retrieving the weather for Nanjing."
        api_data = None
        user_input = "西红柿炒鸡蛋怎么做。"
        user_input = "帮我查一下苹果手机的价格。"
        user_input = "请给我讲一个笑话。"
        user_input = "明天的天气。"
        await assistant.chat(user_input, api_data=api_data, on_token=callback, on_finish=callback)
        await asyncio.sleep(30)
        await assistant.aclose()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_run())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
