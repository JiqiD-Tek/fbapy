# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tts.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 19:22
"""

from typing import Union

from backend.app.live.agents.core import tokenize
from backend.app.live.agents.core.tts.tts_cache import TTSCache
from backend.app.live.agents.core.utils import aio


class TTS:
    """文本转语音(TTS)"""

    class _FlushSentinel: ...

    def __init__(self, *, language: str = 'zh-CN', **kwargs) -> None:
        super().__init__(**kwargs)
        self._tokenizer_stream = tokenize.basic.SentenceTokenizer().stream(language=language)
        self._input_ch = aio.Chan[Union[str, TTS._FlushSentinel]]()

        self._audio_callback = None  # 音频回调
        self.tts_cache = TTSCache(maxsize=10, ttl=3600)  # 音频缓存

    def set_callback(self, callback=None) -> None:
        """设置音频数据回调函数"""

    def push_text(self, token: str) -> None:
        """推送文本到TTS系统进行合成"""
        self._input_ch.send_nowait(token)

    def flush(self) -> None:
        """Mark the end of the current segment"""
        self._input_ch.send_nowait(self._FlushSentinel())

    async def aclose(self, **kwargs) -> None: ...
