# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：__init__.py.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""

from backend.core.conf import settings

from backend.common.openai.llm.intention.recognizer.recognizer_en import recognizer_en
from backend.common.openai.llm.intention.recognizer.recognizer_es import recognizer_es
from backend.common.openai.llm.intention.recognizer.recognizer_zh import recognizer_zh

recognizer = {
    "zh-CN": recognizer_zh,  # 中文
    "en-US": recognizer_en,  # 英语
    "es-ES": recognizer_es,  # 西班牙语
}.get(settings.LLM_LANGUAGE, recognizer_zh)
