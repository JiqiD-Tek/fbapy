#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : protocol.py
# @Created   : 2025/4/11 17:23
import uuid
from typing import Annotated

from fastapi import WebSocket, APIRouter, Query

from backend.app.vce.service.coze.audio.speech_service import speech_service
from backend.app.vce.service.coze.audio.transcriptions_service import transcriptions_service
from backend.common.response.response_schema import ResponseModel, response_base

router = APIRouter()


@router.websocket("/speech")
async def speech(
        websocket: WebSocket
):
    """websocket TTS"""
    await  speech_service.receive_loop(websocket)


@router.post("/text_to_speech", summary='生成tts语音', description='生成tts语音')
async def text_to_speech(
        text: Annotated[str, Query(description='文本内容')] = "",
        retain: Annotated[bool, Query(description='是否长期保存')] = True
) -> ResponseModel:
    """http TTS"""
    if not text:
        raise KeyError(f"text is empty")

    url = await speech_service.text_to_speech(
        uid=f"{uuid.uuid4()}", text=text, retain=retain
    )
    return response_base.success(data=url)


@router.websocket("/transcriptions")
async def transcriptions(
        websocket: WebSocket
):
    """websocket ASR"""
    await transcriptions_service.receive_loop(websocket)
