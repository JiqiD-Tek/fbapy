# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tts.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 19:22
"""
from abc import ABC, abstractmethod
from typing import Callable, Optional


class TTS(ABC):
    """文本转语音(TTS)系统抽象基类

    职责：
    - 定义TTS系统核心接口规范
    - 提供同步/异步语音合成能力
    - 支持流式音频输出
    """

    @abstractmethod
    def set_callback(
            self,
            callback: Optional[Callable[[bytes], None]] = None
    ) -> None:
        """设置音频数据回调函数

        参数：
            ext: 音频数据回调函数
                     - 接收参数: 音频数据块(bytes)或None(流结束标志)
                     - 返回值: 任意(通常忽略)
        回调触发场景：
        - 实时流式合成时逐块返回音频
        - 合成结束时返回None作为终止信号
        """

    @abstractmethod
    async def query(self, text: str, is_final: bool = False) -> Optional[bytes]:
        """同步合成文本并返回完整音频数据

        参数：
            text: 待合成文本
            is_final: 标识是否为文本流的最后一段
                     - True时应当立即刷新合成缓冲区
        返回：
            合成后的完整音频数据(bytes)或None
        典型用途：
        - 需要直接获取音频数据的场景
        - 配合is_final处理分段文本合成
        """
