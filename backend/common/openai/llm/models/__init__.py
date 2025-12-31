# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：__init__.py.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/13 16:42
"""

from typing import Union
from functools import lru_cache

from backend.common.log import log
from backend.common.openai.llm.models.azure import Azure
from backend.common.openai.llm.models.doubao import Doubao
from backend.core.conf import settings

# 模型映射表
MODEL_PROVIDERS = {
    **{name: Azure for name in Azure.MODEL_NAMES},
    **{name: Doubao for name in Doubao.MODEL_NAMES},
}


@lru_cache
def get_llm(model_name: str = settings.LLM_MODEL_NAME) -> Union[Azure, Doubao,]:
    """获取指定名称的大语言模型实例

    Args:
        model_name: 要获取的模型名称，默认为配置中的模型

    Returns:
        对应模型的实例

    Raises:
        ValueError: 当模型名称无效时抛出
    """
    if model_provider := MODEL_PROVIDERS.get(model_name):
        log.info(
            f"初始化大模型 - "
            f"文本大模型: [{model_name}], "
            f"意图大模型: [{model_provider.LITE_MODEL_NAME}], "
            f"提供商: [{model_provider.__name__}], "
            f"语言: [{settings.LLM_LANGUAGE}]"
        )
        return model_provider(model_name=model_name)

    raise ValueError(
        f"无效的模型名称: {model_name}. "
        f"可用模型: {list(MODEL_PROVIDERS.keys())}"
    )


llm = get_llm()
