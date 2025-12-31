#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : session.py
# @Created   : 2025/4/29 17:56

import json
import base64

from abc import ABC
from enum import Enum
from typing import Optional, Dict, List, Any

from pydantic import BaseModel, ConfigDict

from backend.common.wscore.coze.exception import CozeAPIError


class WebsocketsEventType(str, Enum):
    # common
    CLIENT_ERROR = "client_error"  # sdk error
    CLOSED = "closed"  # connection closed

    # error
    ERROR = "error"  # received error event

    # v1/audio/speech
    # req
    INPUT_TEXT_BUFFER_APPEND = "input_text_buffer.append"  # send text to server
    INPUT_TEXT_BUFFER_COMPLETE = (
        "input_text_buffer.complete"  # no text to send, after audio all received, can close connection
    )
    SPEECH_UPDATE = "speech.update"  # send speech config to server

    # resp
    # v1/audio/speech
    INPUT_TEXT_BUFFER_COMPLETED = "input_text_buffer.completed"  # received `input_text_buffer.complete` event

    SPEECH_CREATED = "speech.created"  # after speech created
    SPEECH_AUDIO_URL = "speech.audio.url"  # received `speech.update` event
    SPEECH_AUDIO_UPDATE = "speech.audio.update"  # received `speech.update` event
    SPEECH_AUDIO_COMPLETED = "speech.audio.completed"  # all audio received, can close connection

    # v1/audio/transcriptions
    # req
    INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append"  # send audio to server
    INPUT_AUDIO_BUFFER_COMPLETE = (
        "input_audio_buffer.complete"  # no audio to send, after text all received, can close connection
    )
    TRANSCRIPTIONS_UPDATE = "transcriptions.update"  # send transcriptions config to server

    # resp
    INPUT_AUDIO_BUFFER_COMPLETED = "input_audio_buffer.completed"  # received `input_audio_buffer.complete` event

    TRANSCRIPTIONS_CREATED = "transcriptions.created"  # after transcriptions created
    TRANSCRIPTIONS_VAD = "transcriptions.vad"  # after transcriptions vad

    TRANSCRIPTIONS_MESSAGE_UPDATE = "transcriptions.message.update"  # received `transcriptions.update` event
    TRANSCRIPTIONS_MESSAGE_COMPLETED = "transcriptions.message.completed"  # all audio received, can close connection

    # v1/chat
    # req
    # INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append" # send audio to server
    # INPUT_AUDIO_BUFFER_COMPLETE = "input_audio_buffer.complete" # no audio send, start chat
    CHAT_UPDATE = "chat.update"  # send chat config to server
    CONVERSATION_CHAT_SUBMIT_TOOL_OUTPUTS = "conversation.chat.submit_tool_outputs"  # send intention outputs to server
    CONVERSATION_CHAT_CANCEL = "conversation.chat.cancel"  # send cancel chat to server
    CONVERSATION_MESSAGE_CREATE = "conversation.message.create"  # send text or string_object chat to server

    # resp
    CHAT_CREATED = "chat.created"
    CHAT_UPDATED = "chat.updated"
    # INPUT_AUDIO_BUFFER_COMPLETED = "input_audio_buffer.completed" # received `input_audio_buffer.complete` event
    CONVERSATION_CHAT_CREATED = "conversation.chat.created"  # audio ast completed, chat started
    CONVERSATION_CHAT_IN_PROGRESS = "conversation.chat.in_progress"
    CONVERSATION_CHAT_REQUIRES_ACTION = "conversation.chat.requires_action"  # need plugin submit

    CONVERSATION_CHAT_COMPLETED = "conversation.chat.completed"  # all message received, can close connection
    CONVERSATION_CHAT_CANCELED = "conversation.chat.canceled"  # chat canceled

    CONVERSATION_MESSAGE_DELTA = "conversation.message.delta"  # get agent text message update
    CONVERSATION_MESSAGE_COMPLETED = "conversation.message.completed"

    CONVERSATION_AUDIO_TRANSCRIPT_UPDATE = "conversation.audio_transcript.update"
    CONVERSATION_AUDIO_TRANSCRIPT_COMPLETED = "conversation.audio_transcript.completed"
    CONVERSATION_AUDIO_TRANSCRIPT_VAD = "conversation.audio_transcript.vad"

    CONVERSATION_AUDIO_URL = "conversation.audio.url"  # get agent audio message url
    CONVERSATION_AUDIO_DELTA = "conversation.audio.delta"  # get agent audio message update
    CONVERSATION_AUDIO_COMPLETED = "conversation.audio.completed"

    # v1/ctl
    # resp
    CTRL_CREATED = "ctl.created"
    # req
    CTRL_COMPLETED = "ctl.completed"


class CozeModel(BaseModel):
    model_config = ConfigDict(
        protected_namespaces=(),
        arbitrary_types_allowed=True,
    )


class WebsocketsEvent(CozeModel, ABC):
    class Detail(BaseModel):
        logid: Optional[str] = None

    event_type: WebsocketsEventType
    id: Optional[str] = None
    detail: Optional[Detail] = None


class WebsocketsErrorEvent(WebsocketsEvent):
    event_type: WebsocketsEventType = WebsocketsEventType.ERROR
    data: CozeAPIError


class InputAudio(BaseModel):
    format: Optional[str]
    codec: Optional[str]
    sample_rate: Optional[int]
    channel: Optional[int]
    bit_depth: Optional[int]


class OpusConfig(BaseModel):
    bitrate: Optional[int] = None
    use_cbr: Optional[bool] = None
    frame_size_ms: Optional[float] = None


class PCMConfig(BaseModel):
    sample_rate: Optional[int] = None


class OutputAudio(BaseModel):
    codec: Optional[str]
    pcm_config: Optional[PCMConfig] = None
    opus_config: Optional[OpusConfig] = None
    speech_rate: Optional[int] = None
    voice_id: Optional[str] = None


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageType(str, Enum):
    UNKNOWN = ""
    QUESTION = "question"
    ANSWER = "answer"
    FUNCTION_CALL = "function_call"
    TOOL_OUTPUT = "tool_output"
    TOOL_RESPONSE = "tool_response"
    FOLLOW_UP = "follow_up"
    VERBOSE = "verbose"


class MessageContentType(str, Enum):
    TEXT = "text"
    OBJECT_STRING = "object_string"
    CARD = "card"
    AUDIO = "audio"


class MessageObjectStringType(str, Enum):
    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    AUDIO = "audio"


class MessageObjectString(CozeModel):
    type: MessageObjectStringType
    text: Optional[str] = None
    file_id: Optional[str] = None
    file_url: Optional[str] = None

    @staticmethod
    def build_text(text: str):
        return MessageObjectString(type=MessageObjectStringType.TEXT, text=text)

    @staticmethod
    def build_image(file_id: Optional[str] = None, file_url: Optional[str] = None):
        if not file_id and not file_url:
            raise ValueError("file_id or file_url must be specified")

        return MessageObjectString(type=MessageObjectStringType.IMAGE, file_id=file_id, file_url=file_url)

    @staticmethod
    def build_file(file_id: Optional[str] = None, file_url: Optional[str] = None):
        if not file_id and not file_url:
            raise ValueError("file_id or file_url must be specified")

        return MessageObjectString(type=MessageObjectStringType.FILE, file_id=file_id, file_url=file_url)

    @staticmethod
    def build_audio(file_id: Optional[str] = None, file_url: Optional[str] = None):
        if not file_id and not file_url:
            raise ValueError("file_id or file_url must be specified")

        return MessageObjectString(type=MessageObjectStringType.AUDIO, file_id=file_id, file_url=file_url)


class InsertedMessage(CozeModel):
    id: str  # Inserted message id


class Message(CozeModel):
    role: MessageRole
    type: MessageType = MessageType.UNKNOWN
    content: str
    content_type: MessageContentType
    meta_data: Optional[Dict[str, Any]] = None

    id: Optional[str] = None
    conversation_id: Optional[str] = None
    section_id: Optional[str] = None
    bot_id: Optional[str] = None
    chat_id: Optional[str] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None
    reasoning_content: Optional[str] = None

    @staticmethod
    def build_user_question_text(content: str = "", meta_data: Optional[Dict[str, Any]] = None) -> "Message":
        return Message(
            role=MessageRole.USER,
            type=MessageType.QUESTION,
            content=content,
            content_type=MessageContentType.TEXT,
            meta_data=meta_data,
        )

    @staticmethod
    def build_user_question_objects(
            objects: List[MessageObjectString], meta_data: Optional[Dict[str, Any]] = None
    ) -> "Message":
        return Message(
            role=MessageRole.USER,
            type=MessageType.QUESTION,
            content=json.dumps([obj.model_dump() for obj in objects]),
            content_type=MessageContentType.OBJECT_STRING,
            meta_data=meta_data,
        )

    @staticmethod
    def build_assistant_answer(content: str = "", meta_data: Optional[Dict[str, Any]] = None) -> "Message":
        return Message(
            role=MessageRole.ASSISTANT,
            type=MessageType.ANSWER,
            content=content,
            content_type=MessageContentType.TEXT,
            meta_data=meta_data,
        )

    @staticmethod
    def build_assistant_audio(content: bytes = b"", meta_data: Optional[Dict[str, Any]] = None) -> "Message":
        return Message(
            role=MessageRole.ASSISTANT,
            type=MessageType.ANSWER,
            content=base64.b64encode(content).decode("utf-8"),
            content_type=MessageContentType.AUDIO,
            meta_data=meta_data,
        )

    def get_audio(self) -> Optional[bytes]:
        if self.content_type == MessageContentType.AUDIO:
            return base64.b64decode(self.content)
        return b""


class ToolOutput(CozeModel):
    tool_call_id: str
    output: str


class ChatStatus(str, Enum):
    UNKNOWN = ""
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_ACTION = "requires_action"
    CANCELED = "canceled"


class ChatError(CozeModel):
    code: int = 0
    msg: str = ""


class ChatRequiredActionType(str, Enum):
    UNKNOWN = ""
    SUBMIT_TOOL_OUTPUTS = "submit_tool_outputs"


class ChatToolCallType(str, Enum):
    FUNCTION = "function"
    REPLY_MESSAGE = "reply_message"


class ChatToolCallFunction(CozeModel):
    name: str
    arguments: str


class ChatToolCall(CozeModel):
    id: str
    type: ChatToolCallType
    function: Optional[ChatToolCallFunction] = None


class ChatSubmitToolOutputs(CozeModel):
    tool_calls: List[ChatToolCall]


class ChatRequiredAction(CozeModel):
    type: ChatRequiredActionType
    submit_tool_outputs: Optional[ChatSubmitToolOutputs] = None


class ChatUsage(CozeModel):
    token_count: int = 0
    output_count: int = 0
    input_count: int = 0


class Chat(CozeModel):
    id: str
    conversation_id: str
    bot_id: Optional[str] = None
    created_at: Optional[int] = None
    completed_at: Optional[int] = None
    failed_at: Optional[int] = None
    meta_data: Optional[Dict[str, str]] = None
    last_error: Optional[ChatError] = None
    status: ChatStatus = ChatStatus.UNKNOWN
    required_action: Optional[ChatRequiredAction] = None
    usage: Optional[ChatUsage] = None
    inserted_additional_messages: Optional[List[InsertedMessage]] = None
