#!/usr/bin/env python3

from fastapi import APIRouter

from backend.app.live.api.v1.coze import router as coze_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH, tags=['实时'])

v1.include_router(coze_router, prefix='/live')
