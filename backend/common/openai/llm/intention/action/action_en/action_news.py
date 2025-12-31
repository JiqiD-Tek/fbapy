# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : action_news.py
@Author  : guhua@jiqid.com
@Date    : 2025/05/28 19:55
"""
from typing import Optional, List, Literal, Dict

from backend.common.openapi.news.news_api import news_api
from backend.common.device.repository import DeviceStateRepository

from backend.common.openai.llm.intention.action.base import Action, timed_execute, ActionResult


class ActionNews(Action):
    """实时新闻查询与播报工具"""
    name = "news"

    def __init__(self):
        self.api = news_api

    @property
    def system_prompt(self) -> str:
        return """Structured News Broadcast Prompt Template

        Role:
        - You are a professional news anchor, skilled at delivering concise, credible news phrases.

        Requirements:
        - Content must be objective and positive, avoiding non-authoritative sources, politically sensitive, or vague terms.
        - Generate a cohesive news phrase, 50-100 words, 3-5 sentences, covering event, time, entities, and updates.
        - Use [BREAKING] prefix for urgent news, "Today at + time" for daily news, or specific dates for past news.
        - Cite sources with "According to {agency}" or "Compiled from multiple sources"; political news requires full agency names.
        - Default to "general news" if no category is specified.

        Output Format:
        - Generate a complete news phrase, without question-answer format.

        Example:
        [BREAKING] According to the National Weather Service, Typhoon Dujuan made landfall in Fujian today at 10 AM, triggering coastal emergency measures, with heavy rain expected.
        """

    @timed_execute(threshold_ms=1000)
    async def process(
            self, text: str, content: str,
            conversation_history: Optional[List[Dict[Literal["user", "assistant"], str]]] = None,
            device_repo: DeviceStateRepository = None,
            **kwargs
    ) -> ActionResult:
        """ content=小米YU7的新闻 """

        # try:
        #     news = await self.api.get_news(query=content)
        # except Exception as e:
        #     news = "Unable to obtain news information temporarily"

        news = "Unable to obtain news information temporarily"
        return ActionResult(
            user_prompt=f"""
                Current time: {self.en_formatted_date}
                Input: {text}
                News API data: {news}
                Generate a relevant response considering:
                - Previous conversation history
                - Related data
            """
        )
