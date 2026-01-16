# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : news_tool.py
@Author  : guhua@jiqid.com
@Date    : 2025/05/28 19:55
"""
from typing import Optional, List, Literal, Dict

from backend.common.log import log
from backend.common.openai.core.prompt import build_user_prompt
from backend.common.openapi.news_api import news_api

from backend.common.openai.core.tools.base import Tool, timed_execute, ToolResult


class NewsTool(Tool):
    """实时新闻查询与播报工具"""
    name = "news"

    def __init__(self):
        self.api = news_api

    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            chat_config: dict = None,
            **kwargs
    ) -> ToolResult:
        """ content=小米YU7的新闻 """

        try:
            news = await self.api.get_news(query=content)
        except Exception as e:
            log.error(f"获取新闻信息失败，错误信息：{e}")
            news = "I'm sorry, an error occurred while searching for content"

        user_prompt = build_user_prompt(text, chat_config, news)
        return ToolResult(user_prompt=user_prompt)
