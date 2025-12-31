# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：open_manager.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/15 16:35
"""

import asyncio
from typing import Optional

from backend.common.log import log
from backend.core.conf import settings

from backend.common.openai.speech.base.open_manager import SpeechManager
from backend.common.openai.speech.speech_coze.tts_client import TTSClient, create_tts_config
from backend.common.openai.speech.speech_coze.asr_client import ASRClient, create_asr_config


class CozeSpeechManager(SpeechManager):

    async def acquire_asr(self, uid: Optional[str] = None) -> ASRClient:
        try:
            asr = self._asr_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("ASR对象池空, 构建新对象")
            asr = ASRClient(
                url=settings.BYTES_ASR_URL,
                asr_config=self.get_asr_config()
            )

        await asr.set_uid(uid)
        return asr

    async def release_asr(self, client: ASRClient) -> None:
        try:
            self._asr_pool.put_nowait(client)
        except asyncio.QueueFull:
            log.warning("ASR对象池满, 销毁对象")
            await self._force_close(client=client, reason="ASR 释放")

    async def acquire_tts(self, uid: Optional[str] = None, encoding: str = settings.SPEECH_ENCODING) -> TTSClient:
        try:
            tts = self._tts_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("TTS对象池空, 构建新对象")
            tts = TTSClient(
                url=settings.BYTES_TTS_URL,
                tts_config=self.get_tts_config(encoding=encoding)
            )

        await tts.set_uid(uid)
        return tts

    async def release_tts(self, client: TTSClient) -> None:
        try:
            client.stop_speaking()  # 停止播放
            client.set_callback(None)
            self._tts_pool.put_nowait(client)
        except asyncio.QueueFull:
            log.warning("TTS对象池满, 销毁对象")
            await self._force_close(client=client, reason="TTS 释放")

    @classmethod
    def get_tts_config(cls, icl=settings.BYTES_ICL_STATUS, encoding: str = "wav"):
        return create_tts_config(
            appid=settings.BYTES_TTS_APPID,
            token=settings.BYTES_TTS_TOKEN,
            encoding="pcm" if encoding == "wav" else "mp3",
            **{
                'cluster': settings.BYTES_ICL_CLUSTER if icl else settings.BYTES_TTS_CLUSTER,
                'voice_type': settings.BYTES_ICL_VOICE_TYPE if icl else settings.BYTES_TTS_VOICE_TYPE,
            }
        )

    @classmethod
    def get_asr_config(cls):
        return create_asr_config(
            appid=settings.BYTES_ASR_APPID,
            cluster=settings.BYTES_ASR_CLUSTER,
            token=settings.BYTES_ASR_TOKEN,
            language=settings.BYTES_ASR_LANGUAGE,
        )


open_speech_manager = CozeSpeechManager()
