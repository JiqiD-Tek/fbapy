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

from backend.common.wscore.coze.models import WebsocketsEvent, WebsocketsEventType, OutputAudio


# req
class InputTextBufferAppendEvent(WebsocketsEvent):
    class Data(BaseModel):
        delta: str

    event_type: WebsocketsEventType = WebsocketsEventType.INPUT_TEXT_BUFFER_APPEND
    data: Data


# req
class InputTextBufferCompleteEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.INPUT_TEXT_BUFFER_COMPLETE


# req
class SpeechUpdateEvent(WebsocketsEvent):
    class Data(BaseModel):
        output_audio: Optional[OutputAudio] = None

    event_type: WebsocketsEventType = WebsocketsEventType.SPEECH_UPDATE
    data: Data


# resp
class SpeechCreatedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.SPEECH_CREATED


# resp
class InputTextBufferCompletedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.INPUT_TEXT_BUFFER_COMPLETED


# resp
class SpeechAudioUrlEvent(WebsocketsEvent):
    class Data(BaseModel):
        content: str

    event_type: WebsocketsEventType = WebsocketsEventType.SPEECH_AUDIO_URL
    data: Data


# resp
class SpeechAudioUpdateEvent(WebsocketsEvent):
    class Data(BaseModel):
        delta: bytes

        @field_serializer("delta")
        def serialize_delta(self, delta: bytes, _info):
            return base64.b64encode(delta)

    event_type: WebsocketsEventType = WebsocketsEventType.SPEECH_AUDIO_UPDATE
    data: Data


# resp
class SpeechAudioCompletedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.SPEECH_AUDIO_COMPLETED


def load_req_event(message: Dict) -> Optional[WebsocketsEvent]:
    event_id = message.get("id") or ""
    event_type = message.get("event_type") or ""
    detail = WebsocketsEvent.Detail.model_validate(message.get("detail") or {})
    data = message.get("data") or {}

    if event_type == WebsocketsEventType.INPUT_TEXT_BUFFER_APPEND.value:
        return InputTextBufferAppendEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": InputTextBufferAppendEvent.Data.model_validate(
                    {
                        "delta": data.get("delta"),
                    }
                ),
            }
        )

    if event_type == WebsocketsEventType.INPUT_TEXT_BUFFER_COMPLETE.value:
        return InputTextBufferCompleteEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    if event_type == WebsocketsEventType.SPEECH_UPDATE.value:
        output_audio = data.get("output_audio")
        if output_audio is None:
            raise ValueError("Missing 'output_audio' in event data")
        return SpeechUpdateEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": SpeechUpdateEvent.Data.model_validate(
                    {
                        "output_audio": OutputAudio.model_validate(output_audio),
                    }
                )
            }
        )

    log.warning(f"[v1/audio/speech] unknown event, type={event_type}, logid={detail.logid}")
    return None


def load_resp_event(message: Dict) -> Optional[WebsocketsEvent]:
    event_id = message.get("id") or ""
    detail = WebsocketsEvent.Detail.model_validate(message.get("detail") or {})
    event_type = message.get("event_type") or ""
    data = message.get("data") or {}

    if event_type == WebsocketsEventType.SPEECH_CREATED.value:
        return SpeechCreatedEvent.model_validate({"id": event_id, "detail": detail})

    if event_type == WebsocketsEventType.INPUT_TEXT_BUFFER_COMPLETED.value:
        return InputTextBufferCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    if event_type == WebsocketsEventType.SPEECH_AUDIO_URL.value:
        return SpeechAudioUrlEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": SpeechAudioUrlEvent.Data.model_validate(data),
            }
        )

    if event_type == WebsocketsEventType.SPEECH_AUDIO_UPDATE.value:
        delta_base64 = data.get("delta")
        if delta_base64 is None:
            raise ValueError("Missing 'delta' in event data")
        return SpeechAudioUpdateEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": SpeechAudioUpdateEvent.Data.model_validate(
                    {
                        "delta": base64.b64decode(delta_base64),
                    }
                ),
            }
        )

    if event_type == WebsocketsEventType.SPEECH_AUDIO_COMPLETED.value:
        return SpeechAudioCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    log.warning(f"[v1/audio/speech] unknown event, type={event_type}, logid={detail.logid}")
    return None
