# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : __init__.py.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:12
"""
from fastapi import APIRouter

from backend.app.domain.api.v1.k10.app import router as app_router
from backend.app.domain.api.v1.k10.auth import router as auth_router
from backend.app.domain.api.v1.k10.feedback import router as feedback_router
from backend.app.domain.api.v1.k10.device import router as device_router
from backend.app.domain.api.v1.k10.firmware import router as firmware_router

router = APIRouter(prefix='/k10')

router.include_router(app_router, prefix='/app')
router.include_router(auth_router, prefix='/auth')
router.include_router(feedback_router, prefix='/feedback')
router.include_router(device_router, prefix='/device')
router.include_router(firmware_router, prefix='/firmware')
