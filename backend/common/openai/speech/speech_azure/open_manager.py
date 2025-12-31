# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：open_manager.py
@Author  ：guhua@jiqid.com
@Date    ：2025/06/12 10:26
"""

import asyncio
from typing import Optional

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import SpeechConfig

from backend.core.conf import settings
from backend.common.log import log

from backend.common.openai.speech.base.open_manager import SpeechManager
from backend.common.openai.speech.speech_azure.asr_client import ASRClient
from backend.common.openai.speech.speech_azure.tts_client import TTSClient


class AzureSpeechManager(SpeechManager):

    async def acquire_asr(self, uid: Optional[str] = None) -> ASRClient:
        try:
            asr = self._asr_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("ASR对象池空, 构建新对象")
            asr = ASRClient(await self.get_config())

        await asr.set_uid(uid)
        return asr

    async def release_asr(self, client: ASRClient) -> None:
        try:
            client.stop_recognition()  # 停止识别
            self._asr_pool.put_nowait(client)
        except asyncio.QueueFull:
            log.warning("ASR对象池满, 销毁对象")
            await self._force_close(client=client, reason="ASR 释放")

    async def acquire_tts(self, uid: Optional[str] = None, encoding: str = settings.SPEECH_ENCODING) -> TTSClient:
        try:
            tts = self._tts_pool.get_nowait()
        except asyncio.QueueEmpty:
            log.warning("TTS对象池空, 构建新对象")
            tts = TTSClient(await self.get_config(encoding=encoding))

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
    async def get_config(cls, encoding: str = "wav") -> SpeechConfig:
        speech_config = SpeechConfig(
            subscription=settings.AZURE_SPEECH_KEY.get_secret_value(),
            region=settings.AZURE_SERVICE_REGION,
            speech_recognition_language=settings.AZURE_SPEECH_RECOGNITION_LANGUAGE,
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


open_speech_manager = AzureSpeechManager()
