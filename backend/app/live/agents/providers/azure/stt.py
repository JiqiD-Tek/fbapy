# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：stt.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 10:26
"""

import asyncio
from collections.abc import Callable
from typing import Any, Optional
import azure.cognitiveservices.speech as speechsdk

from backend.app.live.agents.core.stt.stt import STT
from backend.common.log import log
from backend.core.conf import settings


class AzureSTT(STT):
    """语音识别客户端"""

    def __init__(self, language: str = 'zh-CN', **kwargs) -> None:
        super().__init__(language=language, **kwargs)
        self._language = language

        self._stream: speechsdk.audio.PushAudioInputStream | None = None
        self._recognizer: speechsdk.SpeechRecognizer | None = None

        self._speaking = False

        # 回调
        self._append_callback = None
        self._finish_callback = None

        self.loop: asyncio.AbstractEventLoop | None = None

    def set_callbacks(self, append_cb: Optional[Callable] = None, finish_cb: Optional[Callable] = None) -> None:
        """设置回调函数"""
        self._append_callback = append_cb
        self._finish_callback = finish_cb

    async def start(self) -> None:
        """启动语音识别流"""
        self.loop = asyncio.get_running_loop()

        self._stream = speechsdk.audio.PushAudioInputStream()
        self._recognizer = _create_speech_recognizer(stream=self._stream, language=self._language)

        self._recognizer.recognizing.connect(self._on_recognizing)
        self._recognizer.recognized.connect(self._on_recognized)
        self._recognizer.speech_start_detected.connect(self._on_speech_start)
        self._recognizer.speech_end_detected.connect(self._on_speech_end)
        self._recognizer.session_started.connect(self._on_session_started)
        self._recognizer.session_stopped.connect(self._on_session_stopped)
        self._recognizer.canceled.connect(self._on_canceled)

        self._recognizer.start_continuous_recognition()

    def _on_recognizing(self, evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        """识别中回调"""
        log.debug(f'识别中回调: {evt.result.text}')
        if not self.loop:
            log.error('loop is None')
            return

        if self._append_callback:

            def invoke() -> None:
                try:
                    coro = self._append_callback(evt.result.text)
                    if asyncio.iscoroutine(coro):
                        asyncio.create_task(coro)
                except Exception as e:
                    log.error(f'识别中回调: {e}')

            self.loop.call_soon_threadsafe(invoke)

    def _on_recognized(self, evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        """识别结果回调"""
        log.debug(f'识别结果回调: {evt.result.text}')
        if not self.loop:
            log.error('loop is None')
            return

        if self._finish_callback:

            def invoke() -> None:
                try:
                    coro = self._finish_callback(evt.result.text)
                    if asyncio.iscoroutine(coro):
                        asyncio.create_task(coro)
                except Exception as e:
                    log.error(f'识别结果回调: {e}')

            self.loop.call_soon_threadsafe(invoke)

    def _on_speech_start(self, evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        """会话开始回调"""
        log.debug(f'会话开始回调: {evt.result.text}')
        if self._speaking:
            return

        self._speaking = True

    def _on_speech_end(self, evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        """会话结束回调"""
        log.debug(f'会话结束回调: {evt.result.text}')
        if not self._speaking:
            return

        self._speaking = False

    def _on_session_started(self, evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        """会话开始回调"""
        log.debug(f'会话开始回调: {evt.result.text}')

    def _on_session_stopped(self, evt) -> None:
        """会话停止回调"""
        log.debug(f'会话停止回调: {evt.result.text}')

    def _on_canceled(self, evt) -> None:
        """识别取消回调"""
        log.warning(f'识别被取消: {evt.reason}')
        if evt.reason == speechsdk.CancellationReason.Error:
            log.error(f'错误详情: {evt.error_details}')

    async def push(self, audio_chunk: bytes) -> None:
        """追加音频数据"""
        self._stream.write(audio_chunk)

    async def flush(self) -> None:
        """结束识别"""
        self._stream.close()

        def _cleanup() -> None:
            self._recognizer.stop_continuous_recognition()
            del self._recognizer

        await asyncio.to_thread(_cleanup)

    async def _cleanup(self) -> None:
        """清理资源"""
        await self.flush()

    async def aclose(self) -> None:
        """清理资源"""
        await self._cleanup()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._cleanup()


def _create_speech_recognizer(*, stream: speechsdk.audio.AudioInputStream, language: str) -> speechsdk.SpeechRecognizer:
    speech_config = speechsdk.SpeechConfig(
        subscription=settings.AZURE_SPEECH_KEY.get_secret_value(),
        region=settings.AZURE_SPEECH_REGION,
        speech_recognition_language=language,
    )

    # speech_config.set_property(
    #     speechsdk.enums.PropertyId.Speech_SegmentationSilenceTimeoutMs,
    #     str(3000)  # 3秒静默就结束当前句子
    # )

    audio_config = speechsdk.audio.AudioConfig(stream=stream)
    return speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
