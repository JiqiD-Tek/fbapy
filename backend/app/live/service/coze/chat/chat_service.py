#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : chat_service.py
# @Created   : 2025/4/10 15:48

import asyncio
from typing import Optional, Dict, Callable

from backend.app.live.service.coze.service import CozeService

from backend.app.live.agents.assistant import Assistant
from backend.app.live.agents.net.channel_gateway import channel_gateway
from backend.app.live.agents.net.coze.models import (
    WebsocketsEventType,
    WebsocketsEvent,
    Chat,
    Message,
)
from backend.app.live.agents.net.coze.audio.transcriptions import (
    InputAudioBufferAppendEvent,
    InputAudioBufferCompleteEvent,
)
from backend.app.live.agents.net.coze.chat import (
    load_req_event,
    ChatUpdateEvent,
    ChatUpdatedEvent,
    ConversationChatSubmitToolOutputsEvent,
    ConversationChatCancelEvent,
    ConversationMessageCreateEvent,
    ConversationAudioUrlEvent,
    ConversationAudioDeltaEvent,
    ConversationAudioCompletedEvent,
    ConversationChatCanceledEvent,
    ConversationAudioTranscriptUpdateEvent,
    ConversationAudioTranscriptCompletedEvent,
    ConversationMessageCompletedEvent,
    ConversationMessageDeltaEvent,
    ConversationChatCompletedEvent,
)


class ChatService(CozeService):

    def load_event(self, message: dict) -> Optional[WebsocketsEvent]:
        """ 转换成event 对象 """
        event = load_req_event(message)
        return event

    async def on_chat_update(self, uid: str, event: ChatUpdateEvent):
        """ 配置更新 """
        if not (channel := await channel_gateway.get_channel(uid)):
            return

        channel.assistant = Assistant(uid=uid, chat_config=event.data.chat_config)

        await self._register_speech_callback(uid)
        await channel.assistant.stt.start()  # 启动asr

        await channel.put_nowait(ChatUpdatedEvent.model_validate({"data": ChatUpdateEvent.Data.model_validate({})}))

    async def on_input_audio_buffer_append(self, uid: str, event: InputAudioBufferAppendEvent):
        """ 音频数据接收中 """
        if not (channel := await channel_gateway.get_channel(uid)):
            return

        await channel.assistant.stt.push(audio_chunk=event.data.delta)

    async def on_input_audio_buffer_complete(self, uid: str, event: InputAudioBufferCompleteEvent):
        """ 音频数据接收完成 """
        if not (channel := await channel_gateway.get_channel(uid)):
            return

        await channel.assistant.stt.flush()

    async def on_conversation_chat_cancel(self, uid: str, event: ConversationChatCancelEvent):
        """ 对话取消 """
        if not (channel := await channel_gateway.get_channel(uid)):
            return

        await channel.assistant.aclose()  # 打断

    async def on_conversation_chat_submit_tool_outputs(self, uid: str, event: ConversationChatSubmitToolOutputsEvent):
        """ 调用工具 """

    async def on_conversation_message_create(self, uid: str, event: ConversationMessageCreateEvent):
        """ 对话消息 """

    def to_dict(
            self, origin: Optional[Dict[WebsocketsEventType, Callable]] = None
    ) -> Optional[Dict[WebsocketsEventType, Callable]]:
        res = {
            WebsocketsEventType.CLIENT_ERROR: self.on_client_error,

            # 对话相关
            WebsocketsEventType.CHAT_UPDATE: self.on_chat_update,
            WebsocketsEventType.INPUT_AUDIO_BUFFER_APPEND: self.on_input_audio_buffer_append,
            WebsocketsEventType.INPUT_AUDIO_BUFFER_COMPLETE: self.on_input_audio_buffer_complete,
            WebsocketsEventType.CONVERSATION_CHAT_CANCEL: self.on_conversation_chat_cancel,

            WebsocketsEventType.CONVERSATION_CHAT_SUBMIT_TOOL_OUTPUTS: self.on_conversation_chat_submit_tool_outputs,
            WebsocketsEventType.CONVERSATION_MESSAGE_CREATE: self.on_conversation_message_create,
        }

        res.update(origin or {})
        return res

    # -------------------------------------------------------------------------------------------

    async def _register_speech_callback(self, uid: str) -> None:
        """注册语音处理回调（ASR+TTS）"""
        if not (channel := await channel_gateway.get_channel(uid)):
            return

        async def on_append_text(text: str) -> None:
            """ asr识别回调 """
            await channel.put_nowait(
                ConversationAudioTranscriptUpdateEvent.model_validate(
                    {"data": ConversationAudioTranscriptUpdateEvent.Data.model_validate({"content": text})}))

        async def on_finish_text(text: str) -> None:
            """ asr识别完成回调 """
            await channel.put_nowait(ConversationAudioTranscriptCompletedEvent.model_validate(
                {"data": ConversationAudioTranscriptCompletedEvent.Data.model_validate({"content": text})}))

            await self._chatgpt_query(uid, text)  # final_text -> 大模型处理 -> 语音合成

        async def on_audio(delta: bytes | None) -> None:
            """ tts合成语音回调 """
            await channel.assistant.tts.tts_cache.append_audio_delta(delta)  # 保存音频数据，通过http链接流式访问

            if delta == b'':  # 大模型处理完成
                await channel.put_nowait(ConversationAudioCompletedEvent.model_validate({}))  # 语音完成
                await channel.put_nowait(ConversationChatCompletedEvent.model_validate(
                    {"data": Chat.model_validate({"id": "", "conversation_id": ""})}))
                return

            await channel.put_nowait(
                ConversationAudioDeltaEvent.model_validate({"data": Message.build_assistant_audio(delta)}))  # 语音中

        channel.assistant.stt.set_callbacks(append_cb=on_append_text, finish_cb=on_finish_text)  # 语音识别(stt)回调
        channel.assistant.tts.set_callback(callback=on_audio)  # 语音合成(tts)回调

    async def _chatgpt_query(self, uid, text) -> None:
        """ 意图识别 """
        if not (channel := await channel_gateway.get_channel(uid)):
            return

        tts_req_id = await channel.assistant.tts.tts_cache.create_new_request()  # 初始化语音id
        await channel.put_nowait(ConversationAudioUrlEvent.model_validate(
            {"data": ConversationAudioUrlEvent.Data.model_validate(
                {"content": f"{channel.uid}.{tts_req_id}"})}))  # token.uuid.tts_req_id

        async def on_token(token_text: str) -> None:
            """ 大模型生成流式内容 """
            await channel.put_nowait(ConversationMessageDeltaEvent.model_validate(
                {"data": Message.build_assistant_answer(token_text)}))  # 流式文本

        async def on_finish(final_text: str) -> None:
            """ 大模型完整流式内容 """
            await channel.put_nowait(ConversationMessageCompletedEvent.model_validate(
                {"data": Message.build_assistant_answer(final_text)}))  # 完整文本

        try:
            await channel.assistant.chat(user_input=text, on_token=on_token, on_finish=on_finish)
        except asyncio.CancelledError:  # 聊天打断
            await channel.put_nowait(ConversationChatCanceledEvent.model_validate({}))


chat_service = ChatService()
