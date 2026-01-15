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

from backend.app.domain.service.secure import secure_service
from backend.common.ali_sms import sms_client
from backend.common.exception import errors
from backend.common.security.jwt import DependsJwtAuth
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.core.conf import settings
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.database.redis import redis_client

from backend.app.domain.schema.captcha import GetCaptchaDetail
from backend.app.domain.schema.token import GetLoginToken, GetNewToken
from backend.app.domain.schema.user import AuthLoginParam, DeviceAuthParam
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
    credentials = secure_service.derive_credentials(mac=obj.username)
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
    credentials = secure_service.derive_credentials(mac=obj.username)
    if obj.password != credentials["did"]:
        raise errors.AuthorizationError(msg='权限不足')

    config = {
        "client_type": "jwt",
        "client_id": "1123822833044",
        "coze_www_base": "https://www.coze.cn",
        "coze_api_base": "https://api.coze.cn",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC+d1Mzm8KMknSV\nDNbUFG1VvFS98FgZ5aFluriKpWQkJnjurxa2ySSmGWbz2q6oHeDgvk829kIlJulv\nIMYEdKg4HcHzhnSGhOYlizoBF3LCns8GI005dFHgWZRfa3ptg48KX56SXOCks7Zs\ndelJJv3XXy5a6qNt+4QhiJRmXkmnHPw6GsdcnDL1kZOGdBNPtG4FYfcdogTRj9U6\n3zfdikLFquggtSTe2VaaSm0pibJ4oXJXEHJX9GrwC4BALwaKDobUJwVK61KXbgaA\nijTRSJJR6bZsZYuBv60DVIpuymxixnbL6tA6d+PgaKjIhpU6HwP9VLuCvgHGeaFG\n7LXR3aIRAgMBAAECggEABgDO6rHj0n9sxrKLnxVF9gngu3FmkQZkF/JZ1QKm8PpN\nq5X/uXE/NPcDcb64eqjMM4dt0PXTtuJkCCQGsNi0qGXpCxkT9bKO+HKExsiWP8dT\nD3FMZjLMo9gX2ApNH7W+T3oAnMIGilpn7s+L7J8Mfl3MBNgfoHH3Q6v6MeAEIpso\nKw21IYjkAUIGF+MGAFX5XylLe6TAmw6qmYt6z+QpoPcNEBEpSHjD0k6+dJlOGomT\nVhNKzjnqZa/0EBCPA3cUaQCKy9vAfvWSbZTE+7bJW7Fv49PfQr2iqB4V7XfMBvVi\n8Paq+ZRiwueSNcYKCgl4FENs7GIlanlADOWZH8VTYwKBgQDnf4euUiy0Zr8nlQI3\nT8xnfQg6d1blHM4zyxseuyGphX62UDc+3NWtbIXUQ1QrlykIteaO+SVfwoIUXeRS\nUsGnxOPI66quNGfsxvhmyrdkGYjjE3kzWYls5KUJK/1z4TwuGdIN3cAS7rMOnx24\nDOyi0nmb2WC8KePhygHTftDbWwKBgQDSoAbZpx0BGq9jKWoGKV9Oo4GEBO3txvt3\nwTVgyM6n8RSN2vwTQwaQg4W5HTXjKZW0TUkX0d47IK/S5gzEuU891OcDLMqgZtDp\nh6eWrWI1GB5ktclO5zGYUOIiJEHpApZMH1oWTAZa6ndaMk1P0fBXtnQcdMJoEHas\nBNkeGP4wAwKBgQCELRmgG4Uw37Vm+TpRsHtJ32bSUw9HM6I8ikwKyNfYfcMyfyx7\n9QT/xwXGg0bMuLsSISHqIjEHsvwoes+BfYTasJ1KO9yxKHTqCVUNA9OgEMBKvvSl\nsAq6JPZh/T7yafi9bbq0dhdT9/w+bfU/AAogkUIkDQKhjN1zLq7KPg8sHwKBgQCb\nRfIG3tXZDI0js1JAPJvQY2WFqASneDvGax8ovKDs2iNm+HtAz/a07uDUOR6S2wNM\nKnWqI8OLH2u/NG1RUbODR8MOaiTu3x1ALAt2X1e5AJDXedRwYKwFOAudU9FrL8cR\nU0OckGtW9ucKDW9FWuWuJAmxOLpg8VIrOl+9entZdQKBgQCbcrrAzWt9Vo4v4bAM\nZ8OMvk6mxDN4OWmkKhR7uosYMm4Y+m2kWp/riVQA8liQIDvSKObgBv4B0WNw6U9W\n5RVKfRCtkJZ9eJAFGJb8Z1+kI5bIdb2pzZ8UjeErrG03463hz61B8ynMafZ3OODd\nAihSTfSW9C37xD/HS6im9awMNQ==\n-----END PRIVATE KEY-----",
        "public_key_id": "7fOXdkLm9jxrfWqcrQwp3ySVKHdltNV14lHJTlFttBk"
    }

    from cozepy import load_oauth_app_from_config
    coze_oauth_app = load_oauth_app_from_config(config)
    oauth_token = coze_oauth_app.get_access_token(ttl=3600)

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
        identity: Annotated[str, Query(description='标识符')],
        name: Annotated[str, Query(description='名称')],
        metadata: Annotated[str, Query(description='元数据')],
        room: Annotated[str, Query(description='房间名')],
        ttl: Annotated[int, Query(description='有效期')] = 3600,
) -> ResponseModel:
    # def _check_user(user_id: str) -> bool:
    #     return True
    #
    # if not _check_user(user_id=request.user.id):
    #     raise errors.AuthorizationError(msg='权限不足')

    token = api.AccessToken(
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    ).with_identity(
        identity=identity).with_name(
        name=name).with_metadata(
        metadata=metadata).with_ttl(
        ttl=datetime.timedelta(seconds=ttl)).with_grants(
        api.VideoGrants(room=room, room_join=True, can_publish=True, can_publish_data=True, can_subscribe=True)
    ).to_jwt()
    return response_base.success(data=token)
