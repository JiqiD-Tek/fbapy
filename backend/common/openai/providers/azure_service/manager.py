# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：manager.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 10:26
"""

import asyncio
from typing import Optional

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import SpeechConfig

from backend.core.conf import settings
from backend.common.log import log

from backend.common.openai.base.manager import BaseManager
from backend.common.openai.providers.azure_service.asr import AzureASR
from backend.common.openai.providers.azure_service.tts import AzureTTS
from backend.common.openai.providers.azure_service.llm import AzureLLM


class AzureManager(BaseManager):

    async def acquire_asr(self, uid: Optional[str] = None) -> AzureASR:
        try:
            asr = self._asr_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("ASR对象池空, 构建新对象")
            asr = AzureASR(await self.get_config())

        await asr.set_uid(uid)
        return asr

    async def release_asr(self, client: AzureASR) -> None:
        try:
            client.stop_recognition()  # 停止识别
            self._asr_pool.put_nowait(client)
        except asyncio.QueueFull:
            log.warning("ASR对象池满, 销毁对象")
            await self._force_close(client=client, reason="ASR 释放")

    async def acquire_tts(self, uid: Optional[str] = None, encoding: str = settings.SPEECH_ENCODING) -> AzureTTS:
        try:
            tts = self._tts_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("TTS对象池空, 构建新对象")
            tts = AzureTTS(await self.get_config(encoding=encoding))

        await tts.set_uid(uid)
        return tts

    async def release_tts(self, client: AzureTTS) -> None:
        try:
            client.stop_speaking()  # 停止播放
            client.set_callback(None)
            self._tts_pool.put_nowait(client)
        except asyncio.QueueFull:
            log.warning("TTS对象池满, 销毁对象")
            await self._force_close(client=client, reason="TTS 释放")

    @classmethod
    async def get_config(cls, encoding: str = "wav", language: str = 'zh-CN') -> SpeechConfig:
        speech_config = SpeechConfig(
            subscription=settings.AZURE_SPEECH_KEY.get_secret_value(),
            region=settings.AZURE_SPEECH_REGION,
            speech_recognition_language=language,
        )

        if encoding == "mp3":
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3  # 音频格式 mp3
            )
        if encoding == "wav":
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm  # 音频格式 pcm
            )

        return speech_config

    async def acquire_llm(self, uid: Optional[str] = None):
        """获取LLM客户端（默认实现）"""
        try:
            llm = self._llm_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("LLM对象池空, 构建新对象")
            llm = AzureLLM(AzureLLM.LITE_MODEL_NAME)

        return llm

    async def release_llm(self, client: "AzureLLM") -> None:
        """释放LLM客户端（默认实现）"""
        try:
            await client.close()
            self._llm_pool.put_nowait(client)
        except asyncio.QueueFull:
            log.warning("LLM对象池满, 销毁对象")
            await self._force_close(client=client, reason="LLM 释放")


azure_manager = AzureManager()
