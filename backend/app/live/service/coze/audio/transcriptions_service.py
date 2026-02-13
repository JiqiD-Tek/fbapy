# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：transcriptions_service.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/16 18:19
"""

from collections.abc import Callable

from backend.app.live.agents.net.channel_pool import channel_pool
from backend.app.live.agents.net.coze.audio.transcriptions import (
    InputAudioBufferAppendEvent,
    InputAudioBufferCompleteEvent,
    TranscriptionsMessageCompletedEvent,
    TranscriptionsMessageUpdateEvent,
    TranscriptionsUpdateEvent,
    load_req_event,
)
from backend.app.live.agents.net.coze.models import WebsocketsEvent, WebsocketsEventType
from backend.app.live.service.coze.service import CozeService


class TranscriptionsService(CozeService):
    def load_event(self, message: dict) -> WebsocketsEvent | None:
        """转换成event 对象"""
        event = load_req_event(message)
        return event

    async def on_transcriptions_update(self, uid: str, event: TranscriptionsUpdateEvent) -> None:
        """配置更新"""
        if not (channel := await channel_pool.get_channel(uid)):
            return

        await self._register_speech_callback(uid)  # 注册asr回调

        await channel.assistant.stt.start()

    async def on_input_audio_buffer_append(self, uid: str, event: InputAudioBufferAppendEvent) -> None:
        """音频数据接收中"""
        if not (channel := await channel_pool.get_channel(uid)):
            return

        await channel.assistant.stt.push(audio_chunk=event.data.delta)

    async def on_input_audio_buffer_complete(self, uid: str, event: InputAudioBufferCompleteEvent) -> None:
        """音频数据接收完成"""
        if not (channel := await channel_pool.get_channel(uid)):
            return

        await channel.stt.flush()

    def to_dict(self, origin: dict[WebsocketsEventType, Callable] | None = None):
        res = {
            WebsocketsEventType.CLIENT_ERROR: self.on_client_error,
            # 语音相关
            WebsocketsEventType.TRANSCRIPTIONS_UPDATE: self.on_transcriptions_update,
            WebsocketsEventType.INPUT_AUDIO_BUFFER_APPEND: self.on_input_audio_buffer_append,
            WebsocketsEventType.INPUT_AUDIO_BUFFER_COMPLETE: self.on_input_audio_buffer_complete,
        }

        res.update(origin or {})
        return res

    # -------------------------------------------------------------------------------------------

    async def _register_speech_callback(self, uid: str) -> None:
        """注册语音处理回调（ASR）"""
        if not (channel := await channel_pool.get_channel(uid)):
            return

        async def on_append_text(text: str) -> None:
            await channel.put_nowait(
                TranscriptionsMessageUpdateEvent.model_validate({
                    'data': TranscriptionsMessageUpdateEvent.Data.model_validate({'content': text})
                })
            )

        async def on_finish_text(text: str) -> None:
            await channel.put_nowait(
                TranscriptionsMessageUpdateEvent.model_validate({
                    'data': TranscriptionsMessageUpdateEvent.Data.model_validate({'content': text})
                })
            )
            await channel.put_nowait(TranscriptionsMessageCompletedEvent.model_validate({}))

        channel.assistant.stt.set_callbacks(append_cb=on_append_text, finish_cb=on_finish_text)  # 语音识别(stt)回调


transcriptions_service = TranscriptionsService()
