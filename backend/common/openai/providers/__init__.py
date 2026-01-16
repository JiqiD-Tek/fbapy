# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : __init__.py.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/16 16:56
"""

from backend.common.log import log
from backend.core.conf import settings

if settings.SPEECH_TYPE == "azure":
    from backend.common.openai.providers.azure_service.manager import (
        azure_manager as open_manager,
        AzureASR as ASR,
        AzureTTS as TTS,
        AzureLLM as LLM,
    )

if settings.SPEECH_TYPE == "coze":
    from backend.common.openai.providers.coze_service.manager import (
        coze_manager as open_manager,
        CozeASR as ASR,
        CozeTTS as TTS,
        CozeLLM as LLM,
    )

log.info(
    f"初始化语音服务 - 提供商: [{settings.SPEECH_TYPE.title()}], "
    f"服务: [asr、tts]"
)
