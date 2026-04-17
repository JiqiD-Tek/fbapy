# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : __init__.py.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:12
"""

from fastapi import APIRouter

from backend.app.cloud.api.v1.terminal.app import router as app_router
from backend.app.cloud.api.v1.terminal.auth import router as auth_router
from backend.app.cloud.api.v1.terminal.baby import router as baby_router
from backend.app.cloud.api.v1.terminal.device import router as device_router
from backend.app.cloud.api.v1.terminal.feedback import router as feedback_router
from backend.app.cloud.api.v1.terminal.firmware import router as firmware_router
from backend.app.cloud.api.v1.terminal.tool import router as tool_router
from backend.app.cloud.api.v1.terminal.led import router as led_router
from backend.app.cloud.api.v1.terminal.user import router as user_router

router = APIRouter()

router.include_router(app_router, prefix='/app', tags=['app管理'])
router.include_router(auth_router, prefix='/auth', tags=['用户授权'])
router.include_router(baby_router, prefix='/baby', tags=['宝宝管理'])
router.include_router(feedback_router, prefix='/feedback', tags=['反馈管理'])
router.include_router(device_router, prefix='/device', tags=['设备管理'])
router.include_router(firmware_router, prefix='/firmware', tags=['固件管理'])
router.include_router(tool_router, prefix='/tool', tags=['三方工具'])
router.include_router(led_router, prefix='/led', tags=['灯效'])
router.include_router(user_router, prefix='/user', tags=['用户管理'])
