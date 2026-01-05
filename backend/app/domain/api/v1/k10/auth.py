# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : auth.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:20
"""
import uuid
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, Query
from fastapi_limiter.depends import RateLimiter
from starlette.background import BackgroundTasks

from backend.common.ali_sms import sms_client
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.core.conf import settings
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.database.redis import redis_client

from backend.app.domain.schema.captcha import GetCaptchaDetail
from backend.app.domain.schema.token import GetLoginToken, GetNewToken
from backend.app.domain.schema.user import AuthLoginParam
from backend.app.domain.service.auth import auth_service
from backend.plugin.email.utils.send import send_email

router = APIRouter()


@router.get(
    '/captcha',
    summary='获取验证码',
    dependencies=[Depends(RateLimiter(times=5, seconds=10))],
)
async def k10_get_captcha(
        db: CurrentSession,
        background_tasks: BackgroundTasks,
        phone: Annotated[str | None, Query(description='手机号')] = None,
        email: Annotated[str | None, Query(description='邮箱')] = None,
) -> ResponseSchemaModel[GetCaptchaDetail]:
    code = ''.join(str(secrets.randbelow(10)) for _ in range(4))

    if phone:
        background_tasks.add_task(sms_client.send_code, phone, code)
    elif email:
        content = {'code': code, 'expired': int(settings.LOGIN_CAPTCHA_EXPIRE_SECONDS / 60)}
        background_tasks.add_task(send_email, db, email, '验证码', content, 'captcha.html')
    else:
        raise errors.NotFoundError(msg='请提供手机号或邮箱')
    captcha_uuid = str(uuid.uuid4())

    await redis_client.set(
        f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{captcha_uuid}',
        code,
        ex=settings.LOGIN_CAPTCHA_EXPIRE_SECONDS,
    )
    data = GetCaptchaDetail(
        is_enabled=settings.LOGIN_CAPTCHA_ENABLED,
        expire_seconds=settings.LOGIN_CAPTCHA_EXPIRE_SECONDS,
        uuid=captcha_uuid,
    )

    return response_base.success(data=data)


@router.post(
    '/login',
    summary='用户登录',
    dependencies=[Depends(RateLimiter(times=5, minutes=1))],
)
async def k10_login(
        db: CurrentSessionTransaction,
        response: Response,
        obj: AuthLoginParam,
        background_tasks: BackgroundTasks,
) -> ResponseSchemaModel[GetLoginToken]:
    data = await auth_service.login(db=db, response=response, obj=obj, background_tasks=background_tasks)
    return response_base.success(data=data)


@router.post('/refresh', summary='刷新 token')
async def k10_refresh_token(db: CurrentSession, request: Request) -> ResponseSchemaModel[GetNewToken]:
    data = await auth_service.refresh_token(db=db, request=request)
    return response_base.success(data=data)


@router.post('/logout', summary='用户登出')
async def k10_logout(request: Request, response: Response) -> ResponseModel:
    await auth_service.logout(request=request, response=response)
    return response_base.success()
