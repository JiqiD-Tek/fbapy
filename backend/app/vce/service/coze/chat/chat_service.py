#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : chat_service.py
# @Created   : 2025/4/10 15:48

import asyncio
from typing import Optional, Dict, Callable

from backend.app.vce.service.coze.service import CozeService

from backend.common.wscore.gateway import connection_gateway
from backend.common.wscore.coze.models import (
    WebsocketsEventType,
    WebsocketsEvent,
    Chat,
    Message,
)
from backend.common.wscore.coze.audio.transcriptions import (
    InputAudioBufferAppendEvent,
    InputAudioBufferCompleteEvent,
)
from backend.common.wscore.coze.chat import (
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
    ConversationAudioTranscriptVadEvent,
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
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        await self._register_speech_callback(uid)  # 注册asr、tts回调

        vad_task = conn.vad_client.reset()
        asr_task = conn.asr_client.stream_start()

        await asyncio.gather(vad_task, asr_task)  # 等待并行任务完成

        async def _process_chat_config() -> None:
            """Process chat configuration updates."""
            if not event.data.chat_config:
                return

            if event.data.chat_config.conversation_id:
                await conn.device_repo.set_fields(conversation_id=event.data.chat_config.conversation_id)  # 设置会话ID

            if event.data.chat_config.parameters:
                await conn.device_repo.loads_dict(state_dict=event.data.chat_config.parameters)  # 加载设备配置

        await _process_chat_config()

        await conn.output_queue.put(ChatUpdatedEvent.model_validate(
            {"data": ChatUpdateEvent.Data.model_validate({})}))

    async def on_input_audio_buffer_append(self, uid: str, event: InputAudioBufferAppendEvent):
        """ 音频数据接收中 """
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        vad_task = conn.vad_client.process_frame(frame=event.data.delta)
        asr_task = conn.asr_client.stream_append(audio_chunk=event.data.delta)

        vad_status, _ = await asyncio.gather(vad_task, asr_task)  # 等待并行任务完成
        if vad_status:
            await conn.output_queue.put(
                ConversationAudioTranscriptVadEvent.model_validate(
                    {"data": ConversationAudioTranscriptVadEvent.Data.model_validate(
                        {"content": conn.vad_client.speech_active})}))

    async def on_input_audio_buffer_complete(self, uid: str, event: InputAudioBufferCompleteEvent):
        """ 音频数据接收完成 """
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        await conn.asr_client.stream_finish()

    async def on_conversation_chat_cancel(self, uid: str, event: ConversationChatCancelEvent):
        """ 对话取消 """
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        await conn.llm_client.close()  # 打断

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
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        async def on_append_text(text: str) -> None:
            """ asr识别回调 """
            await conn.output_queue.put(
                ConversationAudioTranscriptUpdateEvent.model_validate(
                    {"data": ConversationAudioTranscriptUpdateEvent.Data.model_validate({"content": text})}))

        async def on_finish_text(text: str) -> None:
            """ asr识别完成回调 """
            await conn.output_queue.put(ConversationAudioTranscriptCompletedEvent.model_validate(
                {"data": ConversationAudioTranscriptCompletedEvent.Data.model_validate({"content": text})}))

            await self._chatgpt_query(uid, text)  # final_text -> 大模型处理 -> 语音合成

        async def on_audio(delta: bytes | None) -> None:
            """ tts合成语音回调 """
            await conn.tts_client.tts_cache.append_audio_delta(delta)  # 保存音频数据，通过http链接流式访问

            if delta == b"":  # 对话完成，大模型输出完成所有分块
                await conn.output_queue.put(ConversationAudioCompletedEvent.model_validate({}))  # 语音完成
                await conn.output_queue.put(ConversationChatCompletedEvent.model_validate(
                    {"data": Chat.model_validate({"id": "", "conversation_id": ""})}))
                return

            await conn.output_queue.put(
                ConversationAudioDeltaEvent.model_validate({"data": Message.build_assistant_audio(delta)}))  # 语音中

        conn.asr_client.set_callbacks(
            append_cb=on_append_text,
            finish_cb=on_finish_text,
        )  # 语音识别(asr)回调
        conn.tts_client.set_callback(
            callback=on_audio,
        )  # 语音合成(tts)回调

    async def _chatgpt_query(self, uid, text) -> None:
        """ 意图识别 """
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        tts_req_id = await conn.tts_client.tts_cache.create_new_request()  # 初始化语音id
        await conn.output_queue.put(ConversationAudioUrlEvent.model_validate(
            {"data": ConversationAudioUrlEvent.Data.model_validate(
                {"content": f"{conn.uid}.{tts_req_id}"})}))  # token.uuid.tts_req_id

        intention = await conn.llm_client.query_intention(text, device_repo=conn.device_repo)  # 意图识别
        # 1. 闹钟 2. 音乐 3. 控制
        if intention.meta_data:
            await conn.tts_client.query(text=intention.user_prompt, is_final=True)
            await conn.output_queue.put(ConversationMessageCompletedEvent.model_validate(
                {"data": Message.build_assistant_answer(intention.user_prompt, intention.meta_data)}))  # 文本 + 元数据
            return

        # 大模型意图
        await self._chatgpt_query_stream(
            uid=uid, text=text, user_prompt=intention.user_prompt, system_prompt=intention.system_prompt)

    async def _chatgpt_query_stream(self, uid, text, user_prompt, system_prompt) -> None:
        """ 请求大模型 """
        if not (conn := await connection_gateway.get_connection(uid)):
            return

        async def on_text(resp_text: str) -> None:
            """ 大模型生成流式内容 """
            await conn.output_queue.put(ConversationMessageDeltaEvent.model_validate(
                {"data": Message.build_assistant_answer(resp_text)}))  # 流式文本

        async def on_chunk(chunk_text: str, is_final: bool = False) -> None:
            """ 大模型流式内容分段，按段进行TTS """
            await conn.tts_client.query(text=chunk_text, is_final=is_final)  # 分块文本

        async def on_finish(final_text: str) -> None:
            """ 大模型完整流式内容 """
            await conn.output_queue.put(ConversationMessageCompletedEvent.model_validate(
                {"data": Message.build_assistant_answer(final_text)}))  # 完整文本

        try:
            await conn.llm_client.query_stream(
                text=text,
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                on_text=on_text,
                on_chunk=on_chunk,
                on_finish=on_finish,
            )
        except asyncio.CancelledError:  # 聊天打断
            await conn.output_queue.put(ConversationChatCanceledEvent.model_validate({}))


chat_service = ChatService()
