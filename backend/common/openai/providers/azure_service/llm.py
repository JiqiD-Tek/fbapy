# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：azure_service.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/23 11:13
"""
import asyncio

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

    @property
    def async_client(self):
        if self._async_client is None:
            log.debug("初始化 大模型客户端(异步)")
            self._async_client = AsyncAzureOpenAI(
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
                api_key=self.subscription_key,
                http_client=self._http_client,
            )
        return self._async_client


async def main():
    llm = AzureLLM(model_name="gpt-4o-mini")
    text = "你好"
    rv = await llm.query(text=text)
    log.debug(rv)


if __name__ == '__main__':
    asyncio.run(main())
