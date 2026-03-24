from fastapi import APIRouter

from backend.app.led.api.v1 import router as led_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH, tags=['led'])

v1.include_router(led_router, prefix='/led')
