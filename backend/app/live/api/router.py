#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import APIRouter
from backend.core.conf import settings

from backend.app.live.api.v1.coze import router as coze_router

v1 = APIRouter(prefix=f'{settings.FASTAPI_API_V1_PATH}/live', tags=['live'])

v1.include_router(coze_router)
