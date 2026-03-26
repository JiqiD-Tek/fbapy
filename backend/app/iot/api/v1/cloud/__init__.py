# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : __init__.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from fastapi import APIRouter

from backend.app.iot.api.v1.cloud.audio import router as audio_router
from backend.app.iot.api.v1.cloud.ximalaya import router as ximalaya_router

router = APIRouter(prefix='/resources')

router.include_router(ximalaya_router, prefix='/ximalaya', tags=['喜马拉雅'])
router.include_router(audio_router, prefix='/audio', tags=['音频资源'])
