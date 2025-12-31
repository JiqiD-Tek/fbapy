# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：__init__.py.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 10:08
"""

from backend.common.log import log
from backend.core.conf import settings

from backend.common.openai.llm.llm_client import LLMClient
from backend.common.openai.speech.base.vad_client import VADClient

if settings.SPEECH_TYPE == "azure":
    from backend.common.openai.speech.speech_azure.open_manager import (
        open_speech_manager,
        ASRClient,
        TTSClient,
    )

if settings.SPEECH_TYPE == "coze":
    from backend.common.openai.speech.speech_coze.open_manager import (
        open_speech_manager,
        ASRClient,
        TTSClient,
    )

log.info(
    f"初始化语音服务 - 提供商: [{settings.SPEECH_TYPE.title()}], "
    f"服务: [asr、tts]"
)
