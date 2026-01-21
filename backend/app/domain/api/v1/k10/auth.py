# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : auth.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:20
"""
import datetime
import uuid
import secrets
from typing import Annotated
from livekit import api
from fastapi import APIRouter, Depends, Request, Response, Query
from fastapi_limiter.depends import RateLimiter
from starlette.background import BackgroundTasks

from backend.common.security.auth import identity_verifier
from backend.common.ali_sms import sms_client
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import jwt_encode
from backend.core.conf import settings
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.database.redis import redis_client

from backend.app.domain.schema.captcha import GetCaptchaDetail
from backend.app.domain.schema.token import GetLoginToken, GetNewToken
from backend.app.domain.schema.user import AuthLoginParam, DeviceAuthParam, LivekitDeviceAuthParam
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


@router.post(
    '/refresh',
    summary='刷新 token'
)
async def k10_refresh_token(
        db: CurrentSession,
        refresh_token: Annotated[str, Query(description='刷新 token')],
) -> ResponseSchemaModel[GetNewToken]:
    data = await auth_service.refresh_token(db=db, refresh_token=refresh_token)
    return response_base.success(data=data)


@router.post(
    '/logout',
    summary='用户登出'
)
async def k10_logout(
        request: Request
) -> ResponseModel:
    await auth_service.logout(request=request)
    return response_base.success()


@router.post(
    '/mqtt_login',
    summary='mqtt登录',
    # dependencies=[DependsJwtAuth],
)
async def mqtt_login(
        request: Request,
        obj: DeviceAuthParam,
) -> dict:
    credentials = identity_verifier.derive_credentials(mac=obj.username)
    if obj.password != credentials["did"]:
        return {"result": "deny"}

    return {
        "result": "allow",
        "is_superuser": False
    }


@router.post(
    '/coze_token',
    summary='Coze 授权',
    # dependencies=[DependsJwtAuth],
)
async def coze_token(
        request: Request,
        obj: DeviceAuthParam,
) -> ResponseModel:
    ttl = await check(request=request, mac=obj.username, did=obj.password)

    config = {
        "client_type": "jwt",
        "coze_www_base": "https://www.coze.cn",
        "coze_api_base": "https://api.coze.cn",
        "client_id": settings.COZE_CLIENT_ID,
        "private_key": settings.COZE_PRIVATE_KEY,
        "public_key_id": settings.COZE_PUBLIC_KEY_ID,
    }

    from cozepy import load_oauth_app_from_config
    coze_oauth_app = load_oauth_app_from_config(config)
    oauth_token = coze_oauth_app.get_access_token(ttl=ttl)

    data = {
        "token_type": oauth_token.token_type,
        "access_token": oauth_token.access_token,
        "expires_in": oauth_token.expires_in,
    }
    return response_base.success(data=data)


@router.post(
    '/livekit_token',
    summary='livekit 授权',
    # dependencies=[DependsJwtAuth],
)
async def livekit_token(
        request: Request,
        obj: LivekitDeviceAuthParam,
) -> ResponseModel:
    ttl = await check(request=request, mac=obj.username, did=obj.password)

    token = api.AccessToken(
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    ).with_identity(
        identity=obj.password).with_name(
        name=obj.name).with_metadata(
        metadata=obj.metadata).with_ttl(
        ttl=datetime.timedelta(seconds=ttl)).with_grants(
        api.VideoGrants(room=obj.room, room_join=True, can_publish=True, can_publish_data=True, can_subscribe=True)
    ).to_jwt()
    return response_base.success(data=token)


@router.post(
    '/fba_token',
    summary='fba 授权',
    # dependencies=[DependsJwtAuth],
)
async def fba_token(
        request: Request,
        obj: DeviceAuthParam,
) -> ResponseModel:
    ttl = await check(request=request, mac=obj.username, did=obj.password)

    payload = dict(mac=obj.username, did=obj.password, ttl=ttl)
    token = jwt_encode(payload=payload)
    return response_base.success(data=token)


async def check(request, mac, did) -> int:
    """检查设备权限"""
    credentials = identity_verifier.derive_credentials(mac=mac)
    if did != credentials["did"]:
        raise errors.AuthorizationError(msg='权限不足')

    # request.user TODO 获取用户信息付费

    ttl = 600
    return ttl
