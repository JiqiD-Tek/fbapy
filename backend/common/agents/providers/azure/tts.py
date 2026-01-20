# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tts.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 10:26
"""

import asyncio
from typing import Optional

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech.audio import PushAudioOutputStream, PushAudioOutputStreamCallback

from backend.common.log import log
from backend.common.agents.providers.base.tts import TTS
from backend.common.agents.providers.base.tts_cache import TTSCache
from backend.core.conf import settings


class AzureTTS(TTS):
    """TTS客户端"""

    def __init__(self):
        # 创建合成器
        self._synthesizer = _create_speech_synthesizer()

        # 注册事件回调
        self._synthesizer.synthesis_completed.connect(self._on_synthesis_completed)
        self._synthesizer.synthesis_canceled.connect(self._on_synthesis_canceled)

        # 音频回调
        self._audio_callback = None

        # 音频缓存系统
        self._tts_cache = TTSCache(maxsize=10, ttl=3600)

        # 事件循环引用
        self.loop = asyncio.get_event_loop()

    @property
    def tts_cache(self) -> Optional[TTSCache]:
        return self._tts_cache

    def set_callback(self, callback=None):
        """设置音频回调"""
        self._audio_callback = callback

    async def query(self, text: str, is_final: bool = False) -> None:
        log.debug(f"提交TTS query合成请求: [text={text} | size={len(text)} | is_final={is_final}]")

        def _synthesize():
            # 同步合成
            result = self._synthesizer.speak_text_async(text).get()
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                try:
                    log.debug(f"TTS合成完成: audio_size={len(result.audio_data)}]")
                    coro = self._audio_callback(result.audio_data)
                    if asyncio.iscoroutine(coro):
                        asyncio.create_task(coro)
                except Exception as e:
                    log.error(f"音频回调异常: {e}")
            else:
                log.error(f"TTS合成失败: {result.reason}")

            if is_final:
                coro = self._audio_callback(b'')
                if asyncio.iscoroutine(coro):
                    asyncio.create_task(coro)

        self.loop.call_soon_threadsafe(_synthesize)

    def _on_synthesis_completed(self, evt: speechsdk.SessionEventArgs):
        """合成完成回调"""
        log.debug("合成完成回调")

    def _on_synthesis_canceled(self, evt: speechsdk.SessionEventArgs):
        """合成取消回调"""
        log.warning("合成取消回调")

    async def _cleanup(self):
        """关闭资源"""

        def _cleanup() -> None:
            self._synthesizer.stop_speaking()
            del self._synthesizer

        await asyncio.to_thread(_cleanup)

        await self._tts_cache.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()


def _create_speech_synthesizer() -> speechsdk.SpeechSynthesizer:
    speech_config = speechsdk.SpeechConfig(
        subscription=settings.AZURE_SPEECH_KEY.get_secret_value(),
        region=settings.AZURE_SPEECH_REGION,
        speech_recognition_language="zh-CN",
    )

    stream = PushAudioOutputStream(push_stream_callback=PushAudioOutputStreamCallback())
    audio_config = speechsdk.audio.AudioOutputConfig(stream=stream)
    return speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config,
    )
