# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：asr.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 19:22
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable


class ASR(ABC):
    """自动语音识别(ASR)系统抽象基类

    职责：
    - 定义ASR系统核心接口规范
    - 确保子类实现必要的语音处理功能
    """

    @abstractmethod
    async def set_uid(self, uid: str) -> None:
        """设置会话唯一标识符

        参数：
            uid: 唯一会话ID，用于跟踪识别会话
        """

    def set_callbacks(self,
                      append_cb: Optional[Callable[[str], None]] = None,
                      finish_cb: Optional[Callable[[str], None]] = None) -> None:
        """设置识别结果回调函数

        参数：
            append_cb: 增量结果回调(partial_result)
                     参数: 当前识别文本(str)
            finish_cb: 最终结果回调(final_result)
                     参数: 完整识别文本(str)
        """

    @abstractmethod
    async def stream_start(self) -> None:
        """初始化语音流式识别会话

        典型操作：
        - 建立网络连接
        - 初始化语音识别引擎
        - 重置会话状态
        """

    @abstractmethod
    async def stream_append(self, audio_chunk: bytes) -> None:
        """追加音频数据块

        参数：
            audio_chunk: 二进制音频数据(PCM/WAV等格式)

        实现要求：
        - 应支持实时流式处理
        - 需处理网络传输延迟
        """

    @abstractmethod
    async def stream_finish(self) -> None:
        """结束语音识别会话并 """
