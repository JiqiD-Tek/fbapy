# -*- coding: UTF-8 -*-
"""
@Project ：jiqid_dev
@File    ：__init__.py.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/16 16:47
"""
import base64
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from backend.common.log import log
from backend.common.wscore.coze.audio.transcriptions import (
    InputAudioBufferCompletedEvent,
    InputAudioBufferAppendEvent,
    InputAudioBufferCompleteEvent
)

from backend.common.wscore.coze.models import (
    WebsocketsEvent,
    WebsocketsEventType,
    InputAudio,
    OutputAudio,
    ToolOutput,
    Chat,
    Message,
)


# req
class ChatUpdateEvent(WebsocketsEvent):
    class ChatConfig(BaseModel):
        conversation_id: Optional[str] = None
        user_id: Optional[str] = None
        meta_data: Optional[Dict[str, str]] = None
        custom_variables: Optional[Dict[str, str]] = None
        extra_params: Optional[Dict[str, str]] = None
        auto_save_history: Optional[bool] = None
        parameters: Optional[Dict[str, Any]] = None

    class Data(BaseModel):
        output_audio: Optional[OutputAudio] = None
        input_audio: Optional[InputAudio] = None
        chat_config: Optional["ChatUpdateEvent.ChatConfig"] = None

    event_type: WebsocketsEventType = WebsocketsEventType.CHAT_UPDATE
    data: Data


# req
class ConversationChatSubmitToolOutputsEvent(WebsocketsEvent):
    class Data(BaseModel):
        chat_id: str
        tool_outputs: List[ToolOutput]

    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_CHAT_SUBMIT_TOOL_OUTPUTS
    data: Data


# req
class ConversationChatCancelEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_CHAT_CANCEL


# req
class ConversationMessageCreateEvent(WebsocketsEvent):
    class Data(BaseModel):
        role: str
        content_type: str
        content: str

    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_MESSAGE_CREATE
    data: Data


# resp
class ChatCreatedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CHAT_CREATED


# resp
class ChatUpdatedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CHAT_UPDATED
    data: ChatUpdateEvent.Data


# resp
class ConversationChatCreatedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_CHAT_CREATED
    data: Chat


# resp
class ConversationChatInProgressEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_CHAT_IN_PROGRESS


# resp
class ConversationMessageDeltaEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_MESSAGE_DELTA
    data: Message


# resp
class ConversationAudioTranscriptUpdateEvent(WebsocketsEvent):
    class Data(BaseModel):
        content: str

    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_AUDIO_TRANSCRIPT_UPDATE
    data: Data


# resp
class ConversationAudioTranscriptCompletedEvent(WebsocketsEvent):
    class Data(BaseModel):
        content: str

    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_AUDIO_TRANSCRIPT_COMPLETED
    data: Data


class ConversationAudioTranscriptVadEvent(WebsocketsEvent):
    class Data(BaseModel):
        content: bool

    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_AUDIO_TRANSCRIPT_VAD
    data: Data


# resp
class ConversationMessageCompletedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_MESSAGE_COMPLETED
    data: Message


# resp
class ConversationChatRequiresActionEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_CHAT_REQUIRES_ACTION
    data: Chat


# resp
class ConversationAudioUrlEvent(WebsocketsEvent):
    class Data(BaseModel):
        content: str

    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_AUDIO_URL
    data: Data


# resp
class ConversationAudioDeltaEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_AUDIO_DELTA
    data: Message


# resp
class ConversationAudioCompletedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_AUDIO_COMPLETED


# resp
class ConversationChatCompletedEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_CHAT_COMPLETED
    data: Chat


# resp
class ConversationChatCanceledEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.CONVERSATION_CHAT_CANCELED


def load_req_event(message: Dict) -> Optional[WebsocketsEvent]:
    event_id = message.get("id") or ""
    detail = WebsocketsEvent.Detail.model_validate(message.get("detail") or {})
    event_type = message.get("event_type") or ""
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

    if event_type == WebsocketsEventType.INPUT_AUDIO_BUFFER_COMPLETE.value:
        return InputAudioBufferCompleteEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    if event_type == WebsocketsEventType.CHAT_UPDATE.value:
        return ChatUpdateEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": ChatUpdateEvent.Data.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_CHAT_SUBMIT_TOOL_OUTPUTS.value:
        return ConversationChatSubmitToolOutputsEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": ConversationChatSubmitToolOutputsEvent.Data.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_CHAT_CANCEL.value:
        return ConversationChatCancelEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_MESSAGE_CREATE.value:
        return ConversationMessageCreateEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": ConversationMessageCreateEvent.Data.model_validate(data),
            }
        )

    log.warning(f"[v1/chat] unknown event, type={event_type}, logid={detail.logid}")
    return None


def load_resp_event(message: Dict) -> Optional[WebsocketsEvent]:
    event_id = message.get("id") or ""
    detail = WebsocketsEvent.Detail.model_validate(message.get("detail") or {})
    event_type = message.get("event_type") or ""
    data = message.get("data") or {}

    if event_type == WebsocketsEventType.CHAT_CREATED.value:
        return ChatCreatedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )
    if event_type == WebsocketsEventType.CHAT_UPDATED.value:
        return ChatUpdatedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": ChatUpdateEvent.Data.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.INPUT_AUDIO_BUFFER_COMPLETED.value:
        return InputAudioBufferCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_CHAT_CREATED.value:
        return ConversationChatCreatedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": Chat.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_CHAT_IN_PROGRESS.value:
        return ConversationChatInProgressEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_MESSAGE_DELTA.value:
        return ConversationMessageDeltaEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": Message.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_AUDIO_TRANSCRIPT_UPDATE.value:
        return ConversationAudioTranscriptUpdateEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": ConversationAudioTranscriptUpdateEvent.Data.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_AUDIO_TRANSCRIPT_COMPLETED.value:
        return ConversationAudioTranscriptCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": ConversationAudioTranscriptCompletedEvent.Data.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_AUDIO_TRANSCRIPT_VAD.value:
        return ConversationAudioTranscriptVadEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": ConversationAudioTranscriptVadEvent.Data.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_CHAT_REQUIRES_ACTION.value:
        return ConversationChatRequiresActionEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": Chat.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_MESSAGE_COMPLETED.value:
        return ConversationMessageCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": Message.model_validate(data),
            }
        )

    if event_type == WebsocketsEventType.CONVERSATION_AUDIO_DELTA.value:
        return ConversationAudioUrlEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": ConversationAudioUrlEvent.Data.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_AUDIO_DELTA.value:
        return ConversationAudioDeltaEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": Message.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_AUDIO_COMPLETED.value:
        return ConversationAudioCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_CHAT_COMPLETED.value:
        return ConversationChatCompletedEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
                "data": Chat.model_validate(data),
            }
        )
    if event_type == WebsocketsEventType.CONVERSATION_CHAT_CANCELED.value:
        return ConversationChatCanceledEvent.model_validate(
            {
                "id": event_id,
                "detail": detail,
            }
        )

    log.warning(f"[v1/chat] unknown event, type={event_type}, logid={detail.logid}")
    return None
