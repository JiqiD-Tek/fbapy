# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：llm.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/23 11:12
"""
import httpx
import asyncio

from typing import Optional

from openai import AsyncOpenAI

from backend.core.conf import settings
from backend.common.agents.core.llm.tool_context import function_tool
from backend.common.agents.core.llm.llm import LLM
from backend.common.log import log


class CozeLLM(LLM):
    """ Coze 大模型 """
    LITE_MODEL_NAME: str = "doubao-1.5-lite-32k-250115"
    THINK_MODEL_NAME: str = "doubao-1.5-pro-32k-250115"

    def __init__(self, model_name: str = "doubao-1.5-pro-32k-250115", tools=None):
        super().__init__(
            api_key=settings.DOUBAO_API_KEY.get_secret_value(),
            base_url=settings.DOUBAO_BASE_URL,
            model_name=model_name,
            tools=tools,
        )

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


async def main():
    @function_tool()
    async def get_weather(
            city: str
    ):
        """
        Retrieve current weather information for a given city.

        IMPORTANT:
        - The 'city' parameter MUST be in English.
        - If the user provides a city name in any other language (e.g., "北京", "Москва"),
          you MUST translate it to English before processing.

        Returns:
            A short text summary of the weather, or an error message if
            the request fails.
        """

        return "good weather"

    llm = CozeLLM(
        tools=[get_weather]
    )
    system_prompt = """
    System Prompt: Family Voice Assistant 'Papaya'

    Role Definition:
    - Identity: A warm and caring family companion named "Papaya".
    - Style: Natural, friendly, and slightly playful, with thoughtful responses.
    - Goal: Provide safe, concise, text-only responses suitable for all ages (children, adults, seniors).

    # Task
    Provide assistance by using the action you have access to when needed.
    """
    log.debug("LLM调用开始")
    async for chunk in llm.query(
            user_prompt="你叫什么名字",
            system_prompt=system_prompt):
        log.debug(chunk)

    log.debug("LLM调用开始")
    async for chunk in llm.query(
            user_prompt="你叫什么名字",
            system_prompt=system_prompt):
        log.debug(chunk)

    for i in range(5):
        log.debug("LLM调用开始")
        async for chunk in llm.query(
                user_prompt="南京明天的天气如何",
                system_prompt=system_prompt):
            log.debug(chunk)


if __name__ == '__main__':
    asyncio.run(main())
