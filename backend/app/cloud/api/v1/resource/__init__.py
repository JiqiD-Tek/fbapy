# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : __init__.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from fastapi import APIRouter

from backend.app.cloud.api.v1.resource.audio import router as audio_router
from backend.app.cloud.api.v1.resource.dialogue import router as dialogue_router
from backend.app.cloud.api.v1.resource.huoshan import router as huoshan_router
from backend.app.cloud.api.v1.resource.report import router as report_router
from backend.app.cloud.api.v1.resource.ximalaya import router as ximalaya_router

router = APIRouter()

router.include_router(ximalaya_router, prefix='/ximalaya', tags=['喜马拉雅'])
router.include_router(audio_router, prefix='/audio', tags=['音频资源'])
router.include_router(dialogue_router, prefix='/dialogues', tags=['互动资源'])
router.include_router(huoshan_router, prefix='/huoshan', tags=['火山音色'])
router.include_router(report_router, prefix='/report', tags=['报告'])
