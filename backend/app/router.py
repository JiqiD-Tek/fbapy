from fastapi import APIRouter

from backend.app.admin.api.router import v1 as admin_v1
from backend.app.task.api.router import v1 as task_v1
from backend.app.iot.api.router import v1 as iot_v1
from backend.app.live.api.router import v1 as live_v1

router = APIRouter()

router.include_router(admin_v1)
router.include_router(task_v1)
router.include_router(iot_v1)
router.include_router(live_v1)


@router.get("/health", tags=["Health"])
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "Service is healthy"}
