from fastapi import APIRouter

from backend.app.admin.api.router import v1 as admin_v1
from backend.app.task.api.router import v1 as task_v1
from backend.app.domain.api.router import v1 as domain_v1
from backend.app.vce.api.router import v1 as vce_v1

router = APIRouter()

router.include_router(admin_v1)
router.include_router(task_v1)
router.include_router(domain_v1)
router.include_router(vce_v1)  # vce  智能语音 audio(websocket)、asr、llm、tts


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "Service is healthy"}
