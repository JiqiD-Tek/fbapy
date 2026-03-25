# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : __init__.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from fastapi import APIRouter

from backend.app.iot.api.v1.cloud.ximalaya import router as ximalaya_router

router = APIRouter(prefix='/resources')

# 云端资源类接口统一从这里汇总，后续可继续挂载更多资源服务。
router.include_router(ximalaya_router, prefix='/ximalaya', tags=['喜马拉雅'])
