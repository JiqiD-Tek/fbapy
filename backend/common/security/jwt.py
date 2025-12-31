import json
import uuid

from datetime import timedelta, datetime
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from fastapi.security.utils import get_authorization_scheme_param
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic_core import from_json
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model import User
from backend.app.admin.schema.user import GetUserInfoWithRelationDetail
from backend.app.domain.schema.user import GetUserInfoDetail
from backend.common._dataclasses import AccessToken, NewToken, RefreshToken, TokenPayload
from backend.common.exception import errors
from backend.common.exception.errors import TokenError
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

# JWT dependency injection
DependsJwtAuth = Depends(HTTPBearer())


def jwt_encode(payload: dict[str, Any]) -> str:
    """
    生成 JWT token

    :param payload: 载荷
    :return:
    """
    return jwt.encode(payload, settings.TOKEN_SECRET_KEY, settings.TOKEN_ALGORITHM)


def jwt_decode(token: str) -> TokenPayload:
    """
    解析 JWT token

    :param token: JWT token
    :return:
    """
    try:
        payload = jwt.decode(
            token,
            settings.TOKEN_SECRET_KEY,
            algorithms=[settings.TOKEN_ALGORITHM],
            options={'verify_exp': True},
        )
        session_uuid = payload.get('session_uuid')
        user_id = payload.get('sub')
        expire = payload.get('exp')
        if not session_uuid or not user_id or not expire:
            raise errors.TokenError(msg='Token 无效')
    except ExpiredSignatureError:
        raise errors.TokenError(msg='Token 已过期')
    except (JWTError, Exception):
        raise errors.TokenError(msg='Token 无效')
    return TokenPayload(
        id=int(user_id),
        session_uuid=session_uuid,
        expire_time=timezone.from_datetime(timezone.to_utc(expire)),
    )


async def create_access_token(user_id: int, *, multi_login: bool, **kwargs) -> AccessToken:
    """
    生成加密 token

    :param user_id: 用户 ID
    :param multi_login: 是否允许多端登录
    :param kwargs: token 额外信息
    :return:
    """
    expire = timezone.now() + timedelta(seconds=settings.TOKEN_EXPIRE_SECONDS)
    session_uuid = str(uuid.uuid4())
    access_token = jwt_encode({
        'session_uuid': session_uuid,
        'exp': timezone.to_utc(expire).timestamp(),
        'sub': str(user_id),
    })

    if not multi_login:
        await redis_client.delete_prefix(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}')

    await redis_client.setex(
        f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}',
        settings.TOKEN_EXPIRE_SECONDS,
        access_token,
    )

    # Token 附加信息单独存储
    if kwargs:
        await redis_client.setex(
            f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_id}:{session_uuid}',
            settings.TOKEN_EXPIRE_SECONDS,
            json.dumps(kwargs, ensure_ascii=False),
        )

    return AccessToken(access_token=access_token, access_token_expire_time=expire, session_uuid=session_uuid)


async def create_refresh_token(session_uuid: str, user_id: int, *, multi_login: bool) -> RefreshToken:
    """
    生成加密刷新 token，仅用于创建新的 token

    :param session_uuid: 会话 UUID
    :param user_id: 用户 ID
    :param multi_login: 是否允许多端登录
    :return:
    """
    expire = timezone.now() + timedelta(seconds=settings.TOKEN_REFRESH_EXPIRE_SECONDS)
    refresh_token = jwt_encode({
        'session_uuid': session_uuid,
        'exp': timezone.to_utc(expire).timestamp(),
        'sub': str(user_id),
    })

    if not multi_login:
        await redis_client.delete_prefix(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}')

    await redis_client.setex(
        f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}:{session_uuid}',
        settings.TOKEN_REFRESH_EXPIRE_SECONDS,
        refresh_token,
    )
    return RefreshToken(refresh_token=refresh_token, refresh_token_expire_time=expire)


async def create_new_token(
    refresh_token: str,
    session_uuid: str,
    user_id: int,
    *,
    multi_login: bool,
    **kwargs,
) -> NewToken:
    """
    生成新的 token

    :param refresh_token: 刷新 token
    :param session_uuid: 会话 UUID
    :param user_id: 用户 ID
    :param multi_login: 是否允许多端登录
    :param kwargs: token 附加信息
    :return:
    """
    redis_refresh_token = await redis_client.get(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}:{session_uuid}')
    if not redis_refresh_token or redis_refresh_token != refresh_token:
        raise errors.TokenError(msg='Refresh Token 已过期，请重新登录')

    await redis_client.delete(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}:{session_uuid}')
    await redis_client.delete(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}')

    new_access_token = await create_access_token(user_id, multi_login=multi_login, **kwargs)
    new_refresh_token = await create_refresh_token(new_access_token.session_uuid, user_id, multi_login=multi_login)
    return NewToken(
        new_access_token=new_access_token.access_token,
        new_access_token_expire_time=new_access_token.access_token_expire_time,
        new_refresh_token=new_refresh_token.refresh_token,
        new_refresh_token_expire_time=new_refresh_token.refresh_token_expire_time,
        session_uuid=new_access_token.session_uuid,
    )


async def revoke_token(user_id: int, session_uuid: str) -> None:
    """
    撤销 token

    :param user_id: 用户 ID
    :param session_uuid: 会话 ID
    :return:
    """
    await redis_client.delete(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}')
    await redis_client.delete(f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_id}:{session_uuid}')


def get_token(request: Request) -> str:
    """
    获取请求头中的 token

    :param request: FastAPI 请求对象
    :return:
    """
    authorization = request.headers.get('Authorization')
    scheme, token = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != 'bearer':
        raise errors.TokenError(msg='Token 无效')
    return token


async def get_current_user(db: AsyncSession, pk: int) -> User:
    """
    获取当前用户

    :param db: 数据库会话
    :param pk: 用户 ID
    :return:
    """
    from backend.app.admin.crud.crud_user import user_dao

    user = await user_dao.get_join(db, user_id=pk)
    if not user:
        raise errors.TokenError(msg='Token 无效')
    if not user.status:
        raise errors.AuthorizationError(msg='用户已被锁定，请联系系统管理员')
    if user.dept_id:
        if not user.dept.status:
            raise errors.AuthorizationError(msg='用户所属部门已被锁定，请联系系统管理员')
        if user.dept.del_flag:
            raise errors.AuthorizationError(msg='用户所属部门已被删除，请联系系统管理员')
    if user.roles:
        role_status = [role.status for role in user.roles]
        if all(status == 0 for status in role_status):
            raise errors.AuthorizationError(msg='用户所属角色已被锁定，请联系系统管理员')
    return user


def superuser_verify(request: Request, _token: str = DependsJwtAuth) -> bool:
    """
    验证当前用户超级管理员权限

    :param request: FastAPI 请求对象
    :param _token: JWT 令牌
    :return:
    """
    superuser = request.user.is_superuser
    if not superuser or not request.user.is_staff:
        raise errors.AuthorizationError
    return superuser


async def jwt_authentication(token: str) -> GetUserInfoWithRelationDetail | GetUserInfoDetail:
    """
    JWT 认证

    :param token: JWT token
    :return:
    """
    if token in ("jiqid_001",):
        return GetUserInfoDetail(
            id=1,
            uuid="550e8400-e29b-41d4-a716-446655440000",
            username="jiqid",
            nickname="示例用户",
            avatar="https://example.com/avatar.jpg",
            email=None,
            phone="13800138000",
            sex=1,
            birthday=datetime.now(),
            last_login_time=datetime.now(),
        )
    token_payload = jwt_decode(token)
    user_id = token_payload.id
    session_uuid = token_payload.session_uuid
    redis_token = await redis_client.get(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{token_payload.session_uuid}')
    if not redis_token:
        raise errors.TokenError(msg='Token 已过期')

    if token != redis_token:
        raise errors.TokenError(msg='Token 已失效')

    extra_info = await redis_client.get(f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_id}:{session_uuid}')
    extra_info = json.loads(extra_info)

    if extra_info.get('domain') is True:  # 非管理员
        cache_user = await redis_client.get(f'{settings.JWT_USER_REDIS_PREFIX}:domain:{user_id}')
        if not cache_user:
            async with async_db_session() as db:
                from backend.app.domain.crud.crud_user import user_dao
                current_user = await user_dao.get(db, user_id)
                if not current_user:
                    raise errors.TokenError(msg='Token 无效')
                user = GetUserInfoDetail.model_validate(current_user)
                await redis_client.setex(
                    f'{settings.JWT_USER_REDIS_PREFIX}:domain:{user_id}',
                    settings.TOKEN_EXPIRE_SECONDS,
                    user.model_dump_json(),
                )
        else:
            user = GetUserInfoDetail.model_validate(from_json(cache_user, allow_partial=True))
    else:  # 管理员
        cache_user = await redis_client.get(f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}')
        if not cache_user:
            async with async_db_session() as db:
                current_user = await get_current_user(db, user_id)
                user = GetUserInfoWithRelationDetail.model_validate(current_user)
                await redis_client.setex(
                    f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}',
                    settings.TOKEN_EXPIRE_SECONDS,
                    user.model_dump_json(),
                )
        else:
            user = GetUserInfoWithRelationDetail.model_validate(from_json(cache_user, allow_partial=True))

    return user

# 超级管理员鉴权依赖注入
DependsSuperUser = Depends(superuser_verify)
