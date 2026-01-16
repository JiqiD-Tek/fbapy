# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : recognizer_zh.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/19 14:04
"""

import re
import traceback

from typing import Optional, Dict, Tuple, Any, Literal, List
from dataclasses import dataclass, field

from backend.common.log import log
from backend.common.openai.core.prompt import SYSTEM_PROMPT

from backend.common.openai.core.tools.news_tool import NewsTool
from backend.common.openai.core.tools.weather_tool import WeatherTool
from backend.common.openai.core.tools.chat_tool import ChatTool


@dataclass(frozen=True)
class Intention:
    """标准化意图表示（中英文通用）。

    属性:
        intent: 识别的意图名称。
        content: 意图内容。
        user_prompt: 用户提示词（可选）。
        system_prompt: 系统提示词（可选）。
        meta_data: 附加元数据（默认空字典）。
    """
    intent: str
    content: str
    user_prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


class Recognizer(object):
    """意图识别类"""

    # 预编译正则表达式，支持引号和灵活的空格、分隔符
    INTENT_PATTERN = re.compile(r'^\s*(?:"|\')?([^:：|]+?)(?:"|\')?\s*[:：|]\s*(?:"|\')?(.*?)(?:"|\')?\s*$')

    def __init__(self, llm):
        self._llm = llm
        self._tool_registry = self._init_tool_registry()

    @staticmethod
    def _init_tool_registry() -> Dict[str, Any]:
        return {
            cls.name: cls() for cls in [
                WeatherTool, NewsTool, ChatTool
            ]
        }

    @property
    def system_prompt(self) -> str:
        return """
        # ROLE: Multilingual Intent Classifier
            You are a high-performance, multilingual intent classification engine. Your only job is to analyze user input in **any language** and classify it into a predefined, standardized format. DO NOT chat. Your output MUST be a single line: `intent:parameter`.

            ---
            # INTENTS (Priority: 1 > 2 > 3)

            1.  **weather**
                - **Keywords (examples)**: weather, temperature, forecast, tiempo, 天気, etc.
                - **Parameter**: `{location}`
                - **Parameter Extrtool Rule**: Identify the geographical location from the user's input, regardless of the language, and **normalize it to its standard English name**.
                - **Format**: `weather:{location}`
                - **Examples (Multi-language)**:
                    - "forecast for london" -> `weather:London`
                    - "北京的天气怎么样" -> `weather:Beijing`
                    - "¿Qué tiempo hace en Madrid?" -> `weather:Madrid`
                    - "東京の天気を教えて" -> `weather:Tokyo`

            2.  **news**
                - **Keywords (examples)**: news, update, noticias, ニュース, etc.
                - **Parameter**: `{topic}` (Up to 3 keywords from user input, joined by `+`)
                - **Format**: `news:{topic}`
                - **Example**: "what's new with AI and ML?" -> `news:AI+ML`

            3.  **chat** (Fallback)
                - **Keywords**: Universal greetings, help requests, thanks, etc.
                - **Parameter**: `greeting`, `help`, `farewell`, `general`
                - **Format**: `chat:{sub_intent}`
                - **Example**: "Hola" -> `chat:greeting`

            ---
            # RULES

            - **Strict Priority**: Always evaluate in the order: `weather` -> `news` -> `chat`.
            - **Context**: Analyze the last 3 conversation turns.
            - **Defaults**: If a location cannot be reliably identified from the input, use `unknown` (e.g., `weather:unknown`).
            - **Error Handling**: Nonsensical or empty input defaults to `chat:general`.
            - **Strict Format**: Single line, no extra text, no spaces around the colon `:`.
            """

    async def detect(
            self, text: str,
            conversation_history: Optional[List[Dict[str, str]]] = None,
            chat_config=None,
            **kwargs) -> Intention:
        """
        执行意图识别查询
        Args:
            text: 用户输入文本
            conversation_history: 对话历史
            chat_config: 对话变量
            **kwargs: 传递给意图识别的额外参数

        Returns:
            Intention 对象包含识别结果
        """
        try:
            llm_response = await self._call_llm(text, self._llm.LITE_MODEL_NAME, conversation_history)
            intent, content = self.extract_intent_content(llm_response)
            log.debug(f"意图处理器解析完成: text={text}, response={llm_response}, intent={intent}, content={content}")

            tool = self._tool_registry.get(intent, ChatTool())
            try:
                tool_result = await tool.process(
                    text=text,
                    content=content,
                    conversation_history=conversation_history,
                    chat_config=chat_config,
                    **kwargs
                )
                return Intention(
                    intent=intent,
                    content=content,
                    user_prompt=tool_result.user_prompt,
                    system_prompt=SYSTEM_PROMPT,
                    meta_data=tool_result.meta_data,
                )
            except Exception as ex:
                log.error(f"动作处理失败 [Intent:{intent} - {ex} - {traceback.format_exc()}]")
                return Intention(
                    intent=intent,
                    content=content,
                    user_prompt=text,
                    system_prompt=None
                )
        except Exception as ex:
            log.error(f"意图识别失败 [Text:{text} - {ex} - {traceback.format_exc()}]")
            raise RuntimeError(f"意图识别失败: {ex}") from ex

    async def _call_llm(
            self, text: str,
            model_name: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
    ) -> str:
        """统一的LLM调用"""
        try:
            return await self._llm.query(
                text=text,
                system_prompt=self.system_prompt,
                model_name=model_name,
                conversation_history=conversation_history,
            )
        except Exception as ex:
            log.error(f"LLM调用失败 [Model:{model_name} - Text:{text} - {ex} - {traceback.format_exc()}]")
            raise

    @classmethod
    def extract_intent_content(cls, response: str) -> Tuple[Optional[str], str]:
        """从大模型响应中提取意图和内容。 """
        if not response or not isinstance(response, str):
            return None, ""

        response = response.strip()
        if match := cls.INTENT_PATTERN.match(response):
            intent, content = match.group(1).strip(), match.group(2).strip()
            return intent, content

        return None, response
