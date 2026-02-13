# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tts.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 10:26
"""

import asyncio

import azure.cognitiveservices.speech as speechsdk

from azure.cognitiveservices.speech.audio import PushAudioOutputStream, PushAudioOutputStreamCallback

from backend.app.live.agents.core.tts.tts import TTS
from backend.app.live.agents.core.utils import aio
from backend.common.log import log
from backend.core.conf import settings


class AzureTTS(TTS):
    """TTS客户端"""

    def __init__(self, language: str = 'zh-CN', **kwargs) -> None:
        super().__init__(language=language, **kwargs)

        # 创建合成器
        self._synthesizer = _create_speech_synthesizer(language=language)

        # 注册事件回调
        self._synthesizer.synthesis_completed.connect(self._on_synthesis_completed)
        self._synthesizer.synthesis_canceled.connect(self._on_synthesis_canceled)

        self._task = asyncio.create_task(self._run())  # 启动事件循环

    async def _run(self) -> None:
        """事件循环"""

        async def _input_task() -> None:
            async for data in self._input_ch:
                if isinstance(data, self._FlushSentinel):
                    self._tokenizer_stream.flush()
                    continue
                self._tokenizer_stream.push_text(data)

            self._tokenizer_stream.end_input()

        async def _recv_task() -> None:
            async for ev in self._tokenizer_stream:
                result = self._synthesizer.speak_text_async(ev.token).get()
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    try:
                        await self._audio_callback(result.audio_data)
                    except Exception as e:
                        log.error(f'音频回调异常: {e}')
                else:
                    log.error(f'TTS合成失败: {result.reason}')

                if self._tokenizer_stream._current_segment_id != ev.segment_id:
                    log.debug(f'TTS合成结束: {ev}')
                    try:
                        await self._audio_callback(b'')  # 发送空数据表示结束
                    except Exception as e:
                        log.error(f'音频回调异常: {e}')

        tasks = [
            asyncio.create_task(_input_task()),
            asyncio.create_task(_recv_task()),
        ]

        await asyncio.gather(*tasks)

    def set_callback(self, callback=None) -> None:
        """设置音频回调"""
        self._audio_callback = callback

    def _on_synthesis_completed(self, evt: speechsdk.SessionEventArgs) -> None:
        """合成完成回调"""
        log.debug('合成完成回调')

    def _on_synthesis_canceled(self, evt: speechsdk.SessionEventArgs) -> None:
        """合成取消回调"""
        log.warning('合成取消回调')

    async def close(self) -> None:
        """关闭资源"""
        await aio.cancel_and_wait(self._task)

    async def _cleanup(self) -> None:
        """关闭资源"""

        def _cleanup() -> None:
            self._synthesizer.stop_speaking()
            del self._synthesizer

        await asyncio.to_thread(_cleanup)

        await self.tts_cache.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()


def _create_speech_synthesizer(language: str) -> speechsdk.SpeechSynthesizer:
    speech_config = speechsdk.SpeechConfig(
        subscription=settings.AZURE_SPEECH_KEY.get_secret_value(),
        region=settings.AZURE_SPEECH_REGION,
        speech_recognition_language=language,
    )

    stream = PushAudioOutputStream(push_stream_callback=PushAudioOutputStreamCallback())
    audio_config = speechsdk.audio.AudioOutputConfig(stream=stream)
    return speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
