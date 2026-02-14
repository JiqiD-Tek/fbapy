#!/usr/bin/env python
# @Author    : guhua@jiqid.com
# @File      : chat_service.py
# @Created   : 2025/4/10 15:48
import asyncio
import io
import wave

from collections.abc import Callable

from backend.app.live.agents.net.channel_pool import channel_pool
from backend.app.live.agents.net.coze.audio.speech import (
    InputTextBufferAppendEvent,
    InputTextBufferCompleteEvent,
    SpeechAudioCompletedEvent,
    SpeechAudioUpdateEvent,
    SpeechAudioUrlEvent,
    SpeechUpdateEvent,
    load_req_event,
)
from backend.app.live.agents.net.coze.models import WebsocketsEvent, WebsocketsEventType
from backend.app.live.agents.providers.coze.tts import CozeTTS as TTS
from backend.app.live.service.coze.service import CozeService
from backend.common.ali_oss import oss_client
from backend.common.exception import errors
from backend.core.conf import settings


class SpeechService(CozeService):
    async def text_to_speech(
        self, uid: str, text: str, retain: bool = True, encoding: str = settings.SPEECH_ENCODING
    ) -> str:
        """文字转语音"""
        raw_data = bytearray()  # 使用bytearray提高性能
        completion_event = asyncio.Event()

        async def audio_callback(data: bytes | None) -> None:
            """音频数据回调函数"""
            if data == b'':
                completion_event.set()
            else:
                raw_data.extend(data)

        tts = TTS()
        tts.set_callback(audio_callback)
        tts.push_text(text)
        tts.flush()
        try:
            await asyncio.wait_for(completion_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            raise errors.ServerError(msg='TTS转换超时')
        finally:
            await tts.aclose()  # 释放tts资源

        if encoding.lower() == 'wav':
            audio_data = self._pcm_to_wav(
                bytes(raw_data), sample_rate=24000, sample_width=2, channels=1
            )  # TODO 从配置中获取
        else:
            audio_data = bytes(raw_data)

        source = 'text_to_speech' if retain else 'text_to_speech_temp'
        url = await oss_client.upload_bytes(
            key=f'{source}/{uid}.{encoding}',
            data=audio_data,
        )
        return url

    def load_event(self, message: dict) -> WebsocketsEvent | None:
        """转换成event 对象"""
        event = load_req_event(message)
        return event

    async def on_speech_update(self, uid: str, event: SpeechUpdateEvent) -> None:
        """配置更新"""
        if not (channel := await channel_pool.get_channel(uid)):
            return

        await self._register_speech_callback(uid)  # 注册tts回调

        tts_req_id = await channel.assistant.tts.tts_cache.create_new_request()  # 初始化语音id
        await channel.put_nowait(
            SpeechAudioUrlEvent.model_validate({
                'data': SpeechAudioUrlEvent.Data.model_validate({'content': f'{channel.uid}.{tts_req_id}'})
            })
        )  # 音频播放token

    async def on_input_text_buffer_append(self, uid: str, event: InputTextBufferAppendEvent) -> None:
        """文本内容接受中"""
        if not (channel := await channel_pool.get_channel(uid)):
            return

        await channel.assistant.tts.push_text(token=event.data.delta)

    async def on_input_text_buffer_complete(self, uid: str, event: InputTextBufferCompleteEvent) -> None:
        """文本内容接受完成"""
        if not (channel := await channel_pool.get_channel(uid)):
            return

        await channel.assistant.tts.flush()

    def to_dict(
        self, origin: dict[WebsocketsEventType, Callable] | None = None
    ) -> dict[WebsocketsEventType, Callable] | None:
        res = {
            WebsocketsEventType.CLIENT_ERROR: self.on_client_error,
            # 语音相关
            WebsocketsEventType.SPEECH_UPDATE: self.on_speech_update,
            WebsocketsEventType.INPUT_TEXT_BUFFER_APPEND: self.on_input_text_buffer_append,
            WebsocketsEventType.INPUT_TEXT_BUFFER_COMPLETE: self.on_input_text_buffer_complete,
        }

        res.update(origin or {})
        return res

    # -------------------------------------------------------------------------------------------

    async def _register_speech_callback(self, uid: str) -> None:
        """注册语音处理回调（TTS）"""
        if not (channel := await channel_pool.get_channel(uid)):
            return

        async def on_audio(delta: bytes | None) -> None:
            await channel.tts.tts_cache.append_audio_delta(delta)  # 保存音频数据，通过http链接流式访问

            if delta == b'':
                await channel.put_nowait(SpeechAudioCompletedEvent.model_validate({}))  # 音频完成
                return

            await channel.put_nowait(
                SpeechAudioUpdateEvent.model_validate({
                    'data': SpeechAudioUpdateEvent.Data.model_validate({'delta': delta})
                })
            )  # 音频更新

        channel.tts.set_callback(callback=on_audio)  # 语音合成(tts)回调

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate=16000, sample_width=2, channels=1) -> bytes:
        """PCM转WAV"""
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_data)

            return wav_buffer.getvalue()


speech_service = SpeechService()
