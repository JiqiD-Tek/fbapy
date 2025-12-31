# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : vad_client.py
@Author  : guhua@jiqid.com
@Date    : 2025/07/02 13:48
"""

import asyncio
import webrtcvad

from typing import Optional
from dataclasses import dataclass

from backend.common.log import log


@dataclass
class VADState:
    """语音活动检测状态容器

    Attributes:
        speech_active: 是否检测到语音活动
        consecutive_speech_frames: 连续语音帧计数
        consecutive_silence_frames: 连续静音帧计数
    """
    speech_active: bool = False
    consecutive_speech_frames: int = 0
    consecutive_silence_frames: int = 0


class VADClient:
    """优化的语音活动检测客户端，支持端点检测和状态跟踪

    Attributes:
        SAMPLE_RATE: 采样率 (Hz)，默认 16000
        FRAME_DURATION_MS: 帧时长 (ms)，默认 30
        CHANNELS: 声道数，默认 1
        SPEECH_START_THRESHOLD_FRAMES: 语音开始连续帧阈值，默认 5 (150ms)
        SPEECH_END_THRESHOLD_FRAMES: 语音结束连续静音帧阈值，默认 20 (600ms)
    """
    SAMPLE_RATE: int = 16000
    FRAME_DURATION_MS: int = 30
    CHANNELS: int = 1
    SPEECH_START_THRESHOLD_FRAMES: int = 5
    SPEECH_END_THRESHOLD_FRAMES: int = 20

    def __init__(self, uid: Optional[str] = None, aggressiveness: int = 2):
        """
        初始化 VAD 客户端

        Args:
            uid: 客户端唯一标识，默认为 None
            aggressiveness: 检测敏感度 (0-3，3 最严格)，默认 2

        Raises:
            ValueError: 如果 aggressiveness 不在有效范围内
            RuntimeError: 如果 webrtcvad 初始化失败
        """
        if not 0 <= aggressiveness <= 3:
            raise ValueError("Aggressiveness must be between 0 and 3")
        self._uid = uid or ""
        try:
            self._vad = webrtcvad.Vad(aggressiveness)
        except Exception as e:
            log.error(f"Failed to initialize VAD: {e}")
            raise RuntimeError(f"VAD initialization failed: {e}")
        self._lock = asyncio.Lock()
        self._state = VADState()
        self._closed = False

        # 预计算帧属性
        self._frame_size = int(self.SAMPLE_RATE * self.FRAME_DURATION_MS / 1000)
        self._required_bytes = 2 * self._frame_size  # 16-bit PCM, 2 bytes per sample
        log.info(f"VADClient initialized: uid={self._uid}, frame_size={self._frame_size}")

    async def set_uid(self, uid: str):
        pass

    @property
    def speech_active(self) -> bool:
        """是否检测到语音"""
        return self._state.speech_active

    async def process_frame(self, frame: bytes) -> bool:
        """
        处理音频帧并返回是否检测到语音

        Args:
            frame: 16kHz 16-bit 单声道PCM音频帧

        Returns:
            bool: 当前帧是否被判定为语音

        Raises:
            RuntimeError: 客户端已关闭
            ValueError: 音频帧格式无效
        """
        if self._closed:
            raise RuntimeError("VADClient已关闭")

        if len(frame) != self._required_bytes:
            raise ValueError(
                f"无效的音频帧长度！需要 {self._required_bytes} 字节，"
                f"实际得到 {len(frame)} 字节"
            )

        async with self._lock:
            try:
                is_speech = self._vad.is_speech(frame, self.SAMPLE_RATE)
                return self._update_state(is_speech)
            except Exception as e:
                log.error(f"VAD检测失败 [frame_length:{len(frame)}]")
                raise RuntimeError(f"VAD处理失败: {str(e)}") from e

    def _update_state(self, is_speech: bool) -> bool:
        """
        优化版语音状态机更新逻辑 语音帧 -> 静音帧

        参数:
            is_speech: 当前帧是否为语音帧

        返回:
            bool: 语音活动状态是否发生变化 (True表示状态变化)
        """
        if is_speech:  # 语音帧
            self._state.consecutive_silence_frames = 0
            self._state.consecutive_speech_frames += 1
            if (not self._state.speech_active and
                    self._state.consecutive_speech_frames >= self.SPEECH_START_THRESHOLD_FRAMES):  # 达到语音帧阈值才标记为语音开始
                self._state.speech_active = True
                log.debug(f"VAD检测 - **语音开始**")
                return True
        else:  # 静音帧
            self._state.consecutive_speech_frames = 0
            self._state.consecutive_silence_frames += 1
            if (self._state.speech_active and
                    self._state.consecutive_silence_frames >= self.SPEECH_END_THRESHOLD_FRAMES):  # 达到静音帧阈值才标记为语音结束
                self._state.speech_active = False
                log.debug(f"VAD检测 - **语音结束**")
                return True

        return False

    async def close(self) -> None:
        """关闭 VAD 客户端，释放资源"""
        async with self._lock:
            if not self._closed:
                self._closed = True
                self._state = VADState()
                log.info(f"VADClient closed: uid={self._uid}")

    async def reset(self) -> None:
        """重置检测状态（不清除配置）"""
        self._state = VADState()
