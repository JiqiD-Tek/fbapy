# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : router.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:11
"""
from fastapi import APIRouter

from backend.app.iot.api.v1.k11 import router as k11_router

from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH, tags=['k11'])

v1.include_router(k11_router, prefix='/iot')
