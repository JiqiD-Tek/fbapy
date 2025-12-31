# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：doubao.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/23 11:12
"""

from backend.core.conf import settings
from backend.common.openai.llm.models.base import LLM


class Doubao(LLM):
    """ Doubao 大模型 """
    MODEL_NAMES = [
        "doubao-seed-1-6-flash-250615",
        "doubao-1-5-lite-32k-250115",  # 响应时间 ~10ms
        "doubao-1.5-pro-32k-250115",  # 响应时间 ~20ms
    ]
    LITE_MODEL_NAME: str = "doubao-seed-1-6-flash-250615"
    THINK_MODEL_NAME: str = "doubao-seed-1-6-flash-250615"

    def __init__(self, model_name: str):
        super().__init__(
            api_key=settings.DOUBAO_API_KEY.get_secret_value(),
            base_url=settings.DOUBAO_BASE_URL,
            model_name=model_name
        )
