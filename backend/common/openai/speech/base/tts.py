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
    async def set_uid(self, uid: str) -> None:
        """设置会话唯一标识符

        参数：
            uid: 唯一会话ID，用于跟踪合成任务
        典型用途：
        - 多路音频流区分
        - 日志追踪
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
    async def submit(self, text: str) -> None:
        """提交文本进行异步合成(非阻塞模式)

        参数：
            text: 待合成文本
        典型特征：
        - 立即返回不等待合成完成
        - 通过set_callback设置的函数接收结果
        - 适合实时流式场景
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
