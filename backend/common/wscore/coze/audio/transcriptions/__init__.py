# -*- coding: UTF-8 -*-
"""
@Project ：jiqid_dev
@File    ：__init__.py.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/16 16:46
"""
import base64
from typing import Dict, Optional

from pydantic import BaseModel, field_serializer

from backend.common.log import log
from backend.common.wscore.coze.models import WebsocketsEvent, WebsocketsEventType, InputAudio


# req
class InputAudioBufferAppendEvent(WebsocketsEvent):
    class Data(BaseModel):
        delta: bytes

        @field_serializer("delta")
        def serialize_delta(self, delta: bytes, _info):
            return base64.b64encode(delta)

    event_type: WebsocketsEventType = WebsocketsEventType.INPUT_AUDIO_BUFFER_APPEND
    data: Data

    def _dump_without_delta(self):
        return {
            "id": self.id,
            "type": self.event_type.value,
            "detail": self.detail,
            "data": {
                "delta_length": len(self.data.delta) if self.data and self.data.delta else 0,
            },
        }


# req
class InputAudioBufferCompleteEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.INPUT_AUDIO_BUFFER_COMPLETE


# req
class TranscriptionsUpdateEvent(WebsocketsEvent):
    class Data(BaseModel):
        input_audio: Optional[InputAudio] = None

    event_type: WebsocketsEventType = WebsocketsEventType.TRANSCRIPTIONS_UPDATE
    data: Data


# resp
class TranscriptionsCreatedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.TRANSCRIPTIONS_CREATED


# resp
class InputAudioBufferCompletedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.INPUT_AUDIO_BUFFER_COMPLETED


# resp
class TranscriptionsMessageUpdateEvent(WebsocketsEvent):
    class Data(BaseModel):
        content: str

    event_type: WebsocketsEventType = WebsocketsEventType.TRANSCRIPTIONS_MESSAGE_UPDATE
    data: Data


# resp
class TranscriptionsMessageCompletedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.TRANSCRIPTIONS_MESSAGE_COMPLETED


# resp
class TranscriptionsVadEvent(WebsocketsEvent):
    class Data(BaseModel):
        active: bool

    event_type: WebsocketsEventType = WebsocketsEventType.TRANSCRIPTIONS_VAD
    data: Data


def load_req_event(message: Dict) -> Optional[WebsocketsEvent]:
    event_id = message.get("id") or ""
    event_type = message.get("event_type") or ""
    detail = WebsocketsEvent.Detail.model_validate(message.get("detail") or {})
    data = message.get("data") or {}

    if event_type == WebsocketsEventType.INPUT_AUDIO_BUFFER_APPEND.value:
        return InputAudioBufferAppendEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": InputAudioBufferAppendEvent.Data.model_validate(
                    {
                        "delta": base64.b64decode(data.get("delta") or "")
                    }
                ),
            }
        )

    if event_type == WebsocketsEventType.TRANSCRIPTIONS_UPDATE.value:
        return TranscriptionsUpdateEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": TranscriptionsUpdateEvent.Data.model_validate(
                    {
                        "input_audio": InputAudio.model_validate(data.get("input_audio") or {})
                    }
                ),
            }
        )

    if event_type == WebsocketsEventType.INPUT_AUDIO_BUFFER_COMPLETE.value:
        return InputAudioBufferCompleteEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    log.warning(f"[v1/audio/transcriptions] unknown event={event_type}, logid={detail.logid}")
    return None


def load_resp_event(message: Dict) -> Optional[WebsocketsEvent]:
    event_id = message.get("id") or ""
    event_type = message.get("event_type") or ""
    detail = WebsocketsEvent.Detail.model_validate(message.get("detail") or {})
    data = message.get("data") or {}

    if event_type == WebsocketsEventType.TRANSCRIPTIONS_CREATED.value:
        return TranscriptionsCreatedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    if event_type == WebsocketsEventType.INPUT_AUDIO_BUFFER_COMPLETED.value:
        return InputAudioBufferCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    if event_type == WebsocketsEventType.TRANSCRIPTIONS_MESSAGE_UPDATE.value:
        return TranscriptionsMessageUpdateEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": TranscriptionsMessageUpdateEvent.Data.model_validate(
                    {
                        "content": data.get("content") or "",
                    }
                ),
            }
        )

    if event_type == WebsocketsEventType.TRANSCRIPTIONS_MESSAGE_COMPLETED.value:
        return TranscriptionsMessageCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    if event_type == WebsocketsEventType.TRANSCRIPTIONS_VAD.value:
        return TranscriptionsVadEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": TranscriptionsVadEvent.Data.model_validate(data),
            }
        )

    log.warning(f"[v1/audio/transcriptions] unknown event={event_type}, logid={detail.logid}")
    return None
