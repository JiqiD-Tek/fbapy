# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：azure_service.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/23 11:13
"""
import asyncio
from typing import Optional

import httpx
from openai import AsyncAzureOpenAI

from backend.common.log import log
from backend.core.conf import settings
from backend.common.openai.providers.base_service.llm import LLM


class AzureLLM(LLM):
    """ Azure 大模型 """
    MODEL_NAMES = [
        "gpt-4o-mini",  # 最快
    ]
    LITE_MODEL_NAME: str = "gpt-4o-mini"
    THINK_MODEL_NAME: str = "gpt-4o-mini"

    def __init__(self, model_name: str = "gpt-4o-mini"):
        super().__init__(model_name=model_name)
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.subscription_key = settings.AZURE_OPENAI_SUBSCRIPTION_KEY.get_secret_value()
        self.api_version = settings.AZURE_OPENAI_API_VERSION

        self._async_client: Optional[AsyncAzureOpenAI] = None

    @property
    def async_client(self):
        if self._async_client is None:
            log.debug("初始化 大模型客户端(异步)")
            self._async_client = AsyncAzureOpenAI(
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
        return self._async_client


async def main():
    llm = AzureLLM(model_name="gpt-4o-mini")
    text = "你好"
    rv = await llm.query(text=text)
    log.debug(rv)


if __name__ == '__main__':
    asyncio.run(main())
