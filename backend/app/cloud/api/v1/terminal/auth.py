# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : auth.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 11:20
"""

import datetime
import secrets
import uuid
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from livekit import api
from pyrate_limiter import Duration, Rate
from starlette.background import BackgroundTasks

from backend.app.cloud.schema.captcha import GetCaptchaDetail
from backend.app.cloud.schema.token import (
    CozeToken,
    CurrentLocation,
    FbaToken,
    GetLoginToken,
    GetNewToken,
    LivekitToken,
    MiniProvisionStatusDetail,
    MiniProvisionTokenDetail,
    OSSToken,
    StsToken,
)
from backend.app.cloud.schema.user import (
    AuthLoginParam,
    DeviceAuthParam,
    GetUserInfoDetail,
    LivekitDeviceParam,
    MiniProgramLoginParam,
    MiniProgramProfileParam,
    MQTTAuthParam,
)
from backend.app.cloud.service.auth_service import auth_service
from backend.app.cloud.service.baby_service import baby_service
from backend.app.cloud.service.resource.storage import StorageService
from backend.common.providers.ali_sms import sms_client
from backend.common.providers.ali_sts import sts_client
from backend.common.context import ctx
from backend.common.exception import errors
from backend.common.response.response_code import CustomErrorCode
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth import DependsDeviceAuth, DependsDeviceOrJwtAuth, verify_device_credentials
from backend.common.security.jwt import DependsJwtAuth, DependsSuperUser
from backend.common.security.jwt import jwt_encode, jwt_decode
from backend.core.conf import settings
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.database.redis import redis_client
from backend.plugin.email.utils.send import send_email
from backend.utils.limiter import RateLimiter
from backend.utils.timezone import timezone

router = APIRouter()
MAC_REGEX = re.compile(r'^(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}$', re.I)


@router.get(
    '/captcha',
    summary='获取验证码',
    dependencies=[DependsDeviceAuth],
)
async def get_terminal_captcha(
        db: CurrentSession,
        background_tasks: BackgroundTasks,
        phone: Annotated[str | None, Query(description='手机号')] = None,
        email: Annotated[str | None, Query(description='邮箱')] = None,
) -> ResponseSchemaModel[GetCaptchaDetail]:
    code = ''.join(str(secrets.randbelow(10)) for _ in range(4))

    if email == "testk11@jiqid.com":  # 测试用
        code = '1234'

    if phone:
        sms_result = await sms_client.send_code(phone, code)
        if not sms_result["success"]:
            raise errors.CustomError(error=CustomErrorCode.PHONE_ERROR, msg=sms_result["status"])
    elif email:
        content = {'code': code, 'expired': int(settings.LOGIN_CAPTCHA_EXPIRE_SECONDS / 60)}
        background_tasks.add_task(send_email, db, email, '验证码', content, 'captcha.html')
    else:
        raise errors.CustomError(error=CustomErrorCode.PHONE_EMAIL_NONE)
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
    dependencies=[],
)
async def terminal_login(
        db: CurrentSessionTransaction,
        auth: AuthLoginParam,
        background_tasks: BackgroundTasks,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[GetLoginToken]:
    data = await auth_service.login(db=db, auth=auth, device=auth_ctx, background_tasks=background_tasks)
    return response_base.success(data=data)


@router.post(
    '/mini/login',
    summary='小程序轻量登录注册',
    dependencies=[],
)
async def mini_login(
        db: CurrentSessionTransaction,
        obj: MiniProgramLoginParam,
        background_tasks: BackgroundTasks,
) -> ResponseSchemaModel[GetLoginToken]:
    data = await auth_service.mini_program_login(
        db=db,
        obj=obj,
        background_tasks=background_tasks,
    )
    return response_base.success(data=data)


@router.post(
    '/mini/profile',
    summary='补充小程序用户信息',
    dependencies=[DependsJwtAuth, ],
)
async def mini_profile(
        request: Request,
        db: CurrentSessionTransaction,
        obj: MiniProgramProfileParam,
) -> ResponseSchemaModel[GetUserInfoDetail]:
    data = await auth_service.update_mini_program_profile(
        db=db,
        user_id=request.user.id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.post(
    '/mini/provision/token',
    summary='创建小程序配网 token',
    dependencies=[DependsJwtAuth, ],
)
async def create_mini_provision_token(
        request: Request,
        db: CurrentSession,
) -> ResponseSchemaModel[MiniProvisionTokenDetail]:
    data = await auth_service.create_mini_provision_token(
        db=db,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.get(
    '/mini/provision/{token}',
    summary='查询小程序配网结果',
    dependencies=[DependsJwtAuth, ],
)
async def get_mini_provision_status(
        request: Request,
        token: Annotated[str, Path(description='配网 token')],
) -> ResponseSchemaModel[MiniProvisionStatusDetail]:
    data = await auth_service.get_mini_provision_status(
        user_id=request.user.id,
        token=token,
    )
    return response_base.success(data=data)


@router.post('/refresh', summary='刷新 token', dependencies=[DependsDeviceAuth])
async def terminal_refresh_token(
        db: CurrentSession,
        refresh_token: Annotated[str, Query(description='刷新 token')],
) -> ResponseSchemaModel[GetNewToken]:
    data = await auth_service.refresh_token(db=db, refresh_token=refresh_token)
    return response_base.success(data=data)


@router.post('/logout', summary='用户登出', dependencies=[DependsDeviceAuth])
async def terminal_logout(request: Request) -> ResponseModel:
    await auth_service.logout(request=request)
    return response_base.success()


@router.post('/mqtt_login', summary='mqtt登录')
async def mqtt_login(
        request: Request,
        auth: MQTTAuthParam,
) -> dict:
    if MAC_REGEX.fullmatch(auth.username):
        try:
            verify_device_credentials(mac=auth.username, did=auth.password)
        except errors.CustomError:
            return {'result': 'deny'}
    else:
        try:
            jwt_decode(token=auth.password)
        except errors.TokenError:
            return {'result': 'deny'}

    return {'result': 'allow', 'is_superuser': False}


@router.post('/sts_token', summary='阿里云STS', dependencies=[DependsSuperUser])
async def sts_token(
        request: Request,
) -> ResponseSchemaModel[StsToken]:
    data = sts_client.assume_role()
    data = StsToken(**data)

    return response_base.success(data=data)


@router.post('/oss_token/{ext}', summary='阿里云OSS', dependencies=[DependsDeviceOrJwtAuth])
async def oss_token(
        ext: Annotated[str, Path(description='文件类型')],
        auth_ctx: object = DependsDeviceOrJwtAuth,
) -> ResponseSchemaModel[OSSToken]:
    if isinstance(auth_ctx, DeviceAuthParam):
        uid = auth_ctx.did
        product = auth_ctx.model
    else:
        owner = getattr(auth_ctx, 'uuid', None)
        if not isinstance(owner, str) or not owner:
            raise errors.AuthorizationError(msg='认证信息无效')
        uid = owner
        product = 'fba'

    storage_service = StorageService(product)
    object_name = storage_service.create_object_name(uid=uid, ext=ext)
    url = storage_service.get_object_url(object_name)
    sign_url = storage_service.get_sign_url(object_name)
    signature = storage_service.generate_signature()
    data = OSSToken(url=url, sign_url=sign_url, signature=signature)

    return response_base.success(data=data)


@router.get('/current_location', summary='获取当前位置信息', dependencies=[DependsDeviceAuth])
async def current_location() -> ResponseSchemaModel[CurrentLocation]:
    location = CurrentLocation(
        city=ctx.city,
        country=ctx.country,
        region=ctx.region,
        ip=ctx.ip,
    )
    return response_base.success(data=location)


@router.post('/coze_token', summary='Coze 授权', dependencies=[DependsDeviceAuth])
async def coze_token(
        db: CurrentSessionTransaction,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[CozeToken]:
    # quota = await device_service.allocate_quota(db=db, did=auth_ctx.did)
    quota = 600

    config = {
        'client_type': 'jwt',
        'coze_www_base': 'https://www.coze.cn',
        'coze_api_base': 'https://api.coze.cn',
        'client_id': settings.COZE_CLIENT_ID,
        'private_key': settings.COZE_PRIVATE_KEY,
        'public_key_id': settings.COZE_PUBLIC_KEY_ID,
    }

    from cozepy import load_oauth_app_from_config

    coze_oauth_app = load_oauth_app_from_config(config)
    oauth_token = coze_oauth_app.get_access_token(ttl=quota)

    token = CozeToken(
        token_type=oauth_token.token_type,
        access_token=oauth_token.access_token,
        expires_in=oauth_token.expires_in,
        ttl=quota,
        bot_id=settings.COZE_BOT_ID,
        tw_bot_id="7637473092688134179",  # 台湾版本音色差异
    )
    return response_base.success(data=token)


@router.post('/livekit_token', summary='livekit 授权', dependencies=[DependsDeviceAuth])
async def livekit_token(
        db: CurrentSessionTransaction,
        obj: LivekitDeviceParam,  # 业务字段（room/name/metadata）
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[LivekitToken]:
    # quota = await device_service.allocate_quota(db=db, did=auth_ctx.did)
    quota = 600

    token = (
        api
        .AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        .with_identity(identity=auth_ctx.did)
        .with_name(name=obj.name)
        .with_metadata(metadata=obj.metadata)
        .with_ttl(ttl=datetime.timedelta(seconds=quota))
        .with_grants(
            api.VideoGrants(room=obj.room, room_join=True, can_publish=True, can_publish_data=True, can_subscribe=True)
        )
        .to_jwt()
    )

    token = LivekitToken(
        url=settings.LIVEKIT_URL,
        token=token,
        ttl=quota,
    )
    return response_base.success(data=token)


@router.post('/fba_token', summary='fba 授权', dependencies=[DependsDeviceAuth])
async def fba_token(
        db: CurrentSessionTransaction,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseSchemaModel[FbaToken]:
    # quota = await device_service.allocate_quota(db=db, did=auth_ctx.did)
    quota = 600

    baby = await baby_service.get_by_device_did(db=db, did=auth_ctx.did)

    now = timezone.now()
    expire_time = now + datetime.timedelta(seconds=quota)
    payload = {
        'mac': auth_ctx.mac, 'did': auth_ctx.did, 'sn': auth_ctx.sn, 'model': auth_ctx.model,
        'baby_id': baby.id if baby is not None else 0,
        'iat': int(timezone.to_utc(now).timestamp()),
        'exp': int(timezone.to_utc(expire_time).timestamp()),
    }

    token = jwt_encode(payload=payload)

    token = FbaToken(
        token=token,
        ttl=quota,
    )
    return response_base.success(data=token)


@router.post('/end_usage', summary='断开会话', dependencies=[DependsDeviceAuth])
async def end_usage(
        db: CurrentSessionTransaction,
        auth_ctx: DeviceAuthParam = DependsDeviceAuth,
) -> ResponseModel:
    # quota = await device_service.end_usage(db=db, did=auth_ctx.did)
    quota = 600

    return response_base.success(data=quota)
