# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : __init__.py.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:12
"""

from fastapi import APIRouter

from backend.app.iot.api.v1.k11.app import router as app_router
from backend.app.iot.api.v1.k11.auth import mqtt_router
from backend.app.iot.api.v1.k11.auth import router as auth_router
from backend.app.iot.api.v1.k11.device import router as device_router
from backend.app.iot.api.v1.k11.feedback import router as feedback_router
from backend.app.iot.api.v1.k11.function import router as function_router
from backend.app.iot.api.v1.k11.led import router as led_router
from backend.app.iot.api.v1.k11.user import router as user_router
from backend.common.security.auth import DependsDeviceAuth

router = APIRouter(prefix='/k11')

router.include_router(app_router, prefix='/app', tags=['app管理'], dependencies=[DependsDeviceAuth])
router.include_router(auth_router, prefix='/auth', tags=['用户授权'], dependencies=[DependsDeviceAuth])
router.include_router(mqtt_router, prefix='/auth', tags=['用户授权'])
router.include_router(feedback_router, prefix='/feedback', tags=['反馈管理'], dependencies=[DependsDeviceAuth])
router.include_router(device_router, prefix='/device', tags=['设备管理'], dependencies=[DependsDeviceAuth])
router.include_router(function_router, prefix='/function', tags=['第三方功能'])
router.include_router(led_router, prefix='/led', tags=['灯效'])
router.include_router(user_router, prefix='/user', tags=['用户管理'], dependencies=[DependsDeviceAuth])
