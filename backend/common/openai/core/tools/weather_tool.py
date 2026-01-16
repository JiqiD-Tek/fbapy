# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : tst_action_weather.py
@Author  : guhua@jiqid.com
@Date    : 2025/05/28 19:55
"""
from typing import Optional, List, Literal, Dict

from backend.common.log import log
from backend.common.openai.core.prompt import build_user_prompt
from backend.common.openapi.weather_api import open_weather_map

from backend.common.openai.core.tools.base import Tool, timed_execute, ToolResult


class WeatherTool(Tool):
    """天气查询工具（支持实时数据口语化播报）"""
    name = "weather"

    def __init__(self):
        self.api = open_weather_map


    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            chat_config: dict = None,
            **kwargs
    ) -> ToolResult:
        """ content=南京 """
        log.debug(f"获取天气位置: {content}")
        weather = await self._get_weather_info(content=content)

        user_prompt = build_user_prompt(text, chat_config, weather)
        return ToolResult(user_prompt=user_prompt)

    async def _get_weather_info(self, content: str = "") -> str:
        """获取天气信息 """
        try:
            return await self.api.get_weather_info(city=content)
        except Exception as e:
            log.error(f"获取天气信息失败，错误信息：{e}")
            return "I'm sorry, an error occurred while retrieving the weather"
