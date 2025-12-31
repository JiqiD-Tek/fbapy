# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：transcriptions_service.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/16 18:19
"""

from typing import Optional, Dict, Callable

from backend.app.vce.service.coze.service import CozeService

from backend.common.wscore.gateway import connection_gateway
from backend.common.wscore.coze.models import (
    WebsocketsEventType,
    WebsocketsEvent
)
from backend.common.wscore.coze.audio.transcriptions import (
    load_req_event,
    InputAudioBufferAppendEvent,
    InputAudioBufferCompleteEvent,
    TranscriptionsUpdateEvent,
    TranscriptionsMessageUpdateEvent,
    TranscriptionsMessageCompletedEvent,
    TranscriptionsVadEvent,
)


class TranscriptionsService(CozeService):

    def load_event(self, message: dict) -> Optional[WebsocketsEvent]:
        """ 转换成event 对象 """
        event = load_req_event(message)
        return event

    async def on_transcriptions_update(self, uid: str, event: TranscriptionsUpdateEvent):
        """ 配置更新 """
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        await self._register_speech_callback(uid)  # 注册asr回调

        await conn.asr_client.stream_start()

    async def on_input_audio_buffer_append(self, uid: str, event: InputAudioBufferAppendEvent):
        """ 音频数据接收中 """
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        status = await conn.vad_client.process_frame(frame=event.data.delta)
        if status:
            await conn.output_queue.put(
                TranscriptionsVadEvent.model_validate(
                    {"data": TranscriptionsVadEvent.Data.model_validate({"content": conn.vad_client.speech_active})}))

        await conn.asr_client.stream_append(audio_chunk=event.data.delta)

    async def on_input_audio_buffer_complete(self, uid: str, event: InputAudioBufferCompleteEvent):
        """ 音频数据接收完成 """
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        await conn.asr_client.stream_finish()

    def to_dict(self, origin: Optional[Dict[WebsocketsEventType, Callable]] = None):
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
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        async def on_append_text(text: str):
            await conn.output_queue.put(
                TranscriptionsMessageUpdateEvent.model_validate(
                    {"data": TranscriptionsMessageUpdateEvent.Data.model_validate({"content": text})}))

        async def on_finish_text(text: str):
            await conn.output_queue.put(
                TranscriptionsMessageUpdateEvent.model_validate(
                    {"data": TranscriptionsMessageUpdateEvent.Data.model_validate({"content": text})}))
            await conn.output_queue.put(TranscriptionsMessageCompletedEvent.model_validate({}))

        conn.asr_client.set_callbacks(
            append_cb=on_append_text,
            finish_cb=on_finish_text
        )  # 语音识别(asr)回调


transcriptions_service = TranscriptionsService()
