# -*- coding: UTF-8 -*-
"""
@Project ：jiqid
@File    ：__init__.py.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/12 10:16
"""
from fastapi import APIRouter

from backend.app.vce.api.v1.coze.audio import router as audio_router
from backend.app.vce.api.v1.coze.chat import router as chat_router

router = APIRouter(prefix='/coze/v1')  # 兼容 coze 请求路径

router.include_router(audio_router, prefix='/audio', tags=['语音服务'])
router.include_router(chat_router, prefix='/chat', tags=['聊天服务'])
