# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：stt.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 19:22
"""


class STT:
    """自动语音识别(STT)"""

    def __init__(self, *, language: str = 'zh-CN', **kwargs) -> None:
        super().__init__(**kwargs)

    def set_callbacks(self, append_cb=None, finish_cb=None) -> None:
        """设置识别结果回调函数"""

    async def start(self) -> None:
        """初始化语音流式识别会话"""

    async def push(self, audio_chunk: bytes) -> None:
        """追加音频数据块"""

    async def flush(self) -> None:
        """结束语音识别会话并"""

    async def aclose(self, **kwargs) -> None: ...
