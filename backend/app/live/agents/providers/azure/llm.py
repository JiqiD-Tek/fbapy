# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：azure.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/23 11:13
"""
import httpx
from typing import Optional

from openai import AsyncAzureOpenAI

from backend.core.conf import settings
from backend.app.live.agents.core.llm.llm import LLM


class AzureLLM(LLM):
    """ Azure 大模型 """
    LITE_MODEL_NAME: str = "gpt-4o-mini"
    THINK_MODEL_NAME: str = "gpt-4o-mini"

    def __init__(self, model_name: str = "gpt-4o-mini", tools=None):
        super().__init__(model_name=model_name, tools=tools)
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.subscription_key = settings.AZURE_OPENAI_SUBSCRIPTION_KEY.get_secret_value()
        self.api_version = settings.AZURE_OPENAI_API_VERSION

        self.async_client: Optional[AsyncAzureOpenAI] = AsyncAzureOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
            api_key=self.subscription_key,
            http_client=httpx.AsyncClient(
                timeout=httpx.Timeout(connect=15.0, read=5.0, write=5.0, pool=5.0),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=50, max_keepalive_connections=50, keepalive_expiry=120
                ),
            )
        )
