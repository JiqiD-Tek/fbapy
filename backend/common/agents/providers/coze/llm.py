# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：llm.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/23 11:12
"""
import httpx
from typing import Optional

from openai import AsyncOpenAI

from backend.core.conf import settings
from backend.common.agents.core.llm.llm import LLM


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
