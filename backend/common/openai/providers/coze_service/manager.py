# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：manager.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/15 16:35
"""

import asyncio
from typing import Optional

from backend.common.log import log

from backend.core.conf import settings

from backend.common.openai.base.manager import BaseManager
from backend.common.openai.providers.coze_service.tts import CozeTTS, create_tts_config
from backend.common.openai.providers.coze_service.asr import CozeASR, create_asr_config
from backend.common.openai.providers.coze_service.llm import CozeLLM


class CozeManager(BaseManager):

    async def acquire_asr(self, uid: Optional[str] = None) -> CozeASR:
        try:
            asr = self._asr_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("ASR对象池空, 构建新对象")
            asr = CozeASR(
                url=settings.BYTES_ASR_URL,
                asr_config=self.get_asr_config()
            )

        await asr.set_uid(uid)
        return asr

    async def release_asr(self, client: CozeASR) -> None:
        try:
            self._asr_pool.put_nowait(client)
        except asyncio.QueueFull:
            log.warning("ASR对象池满, 销毁对象")
            await self._force_close(client=client, reason="ASR 释放")

    async def acquire_tts(self, uid: Optional[str] = None, encoding: str = settings.SPEECH_ENCODING) -> CozeTTS:
        try:
            tts = self._tts_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("TTS对象池空, 构建新对象")
            tts = CozeTTS(
                url=settings.BYTES_TTS_URL,
                tts_config=self.get_tts_config(encoding=encoding)
            )

        await tts.set_uid(uid)
        return tts

    async def release_tts(self, client: CozeTTS) -> None:
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
    def get_asr_config(cls, language: str = "zh-CN"):
        return create_asr_config(
            appid=settings.BYTES_ASR_APPID,
            cluster=settings.BYTES_ASR_CLUSTER,
            token=settings.BYTES_ASR_TOKEN,
            language=language,
        )

    async def acquire_llm(self, uid: Optional[str] = None):
        """获取LLM客户端（默认实现）"""
        try:
            llm = self._llm_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("LLM对象池空, 构建新对象")
            llm = CozeLLM(CozeLLM.LITE_MODEL_NAME)

        return llm

    async def release_llm(self, client: "CozeLLM") -> None:
        """释放LLM客户端（默认实现）"""
        try:
            await client.close()
            self._llm_pool.put_nowait(client)
        except asyncio.QueueFull:
            log.warning("LLM对象池满, 销毁对象")
            await self._force_close(client=client, reason="LLM 释放")


coze_manager = CozeManager()
