from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask, BackgroundTasks

from backend.app.domain.crud.crud_device import device_dao
from backend.app.domain.schema.device import CreateDeviceParam
from backend.app.domain.service.secure import secure_service
from backend.common.context import ctx
from backend.common.enums import LoginLogStatusType
from backend.common.exception import errors
from backend.common.i18n import t
from backend.common.log import log
from backend.common.response.response_code import CustomErrorCode
from backend.common.security.jwt import (
    create_access_token,
    create_new_token,
    create_refresh_token,
    get_token,
    jwt_decode,
)
from backend.core.conf import settings
from backend.database.db import uuid4_str
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

from backend.app.admin.service.login_log_service import login_log_service

from backend.app.domain.crud.crud_user import user_dao
from backend.app.domain.schema.token import GetLoginToken, GetNewToken
from backend.app.domain.schema.user import AuthLoginParam, CreateUserParam

from backend.app.domain.model.user import User


class AuthService:
    """认证服务类"""

    async def _register_device(self, db: AsyncSession, user: User, obj: AuthLoginParam):
        valid = secure_service.verify(**obj.device.model_dump())
        if not valid:
            raise errors.RequestError(msg=t('error.device.invalid'))

        device = await device_dao.get_by_user_id(db, user.id)
        if device:
            return

        device_param = CreateDeviceParam(
            name="", hardware="", firmware="",
            model=obj.device.model, sn=obj.device.sn, mac=obj.device.mac, did=obj.device.did, user_id=user.id
        )
        await device_dao.create(db, device_param)

    async def _register(self, db: AsyncSession, obj: AuthLoginParam) -> User:
        user = await user_dao.get_by_phone(db, obj.phone)
        if user:
            await self._register_device(db, user, obj)
            return user

        user_param = CreateUserParam(
            nickname=None, email=None, avatar=None, sex=None, birthday=None,
            phone=obj.phone,
        )
        user = await user_dao.create(db, user_param)
        await self._register_device(db, user, obj)
        return user

    async def login(
            self,
            *,
            db: AsyncSession,
            response: Response,
            obj: AuthLoginParam,
            background_tasks: BackgroundTasks,
    ) -> GetLoginToken:
        """
        用户登录

        :param db: 数据库会话
        :param response: 响应对象
        :param obj: 登录参数
        :param background_tasks: 后台任务
        :return:
        """
        user = None
        try:
            if settings.LOGIN_CAPTCHA_ENABLED:
                if not obj.uuid or not obj.captcha:
                    raise errors.RequestError(msg=t('error.captcha.invalid'))
                captcha_code = await redis_client.get(f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{obj.uuid}')
                if not captcha_code:
                    raise errors.RequestError(msg=t('error.captcha.expired'))
                if captcha_code.lower() != obj.captcha.lower():
                    raise errors.CustomError(error=CustomErrorCode.CAPTCHA_ERROR)
                await redis_client.delete(f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{obj.uuid}')

            user = await user_dao.get_by_phone(db, obj.phone)
            if not user:
                user = await self._register(db, obj)

            await user_dao.update_login_time(db, obj.phone)
            await db.refresh(user)
            access_token_data = await create_access_token(
                user.id,
                multi_login=True,
                # extra info
                username=user.username,
                nickname=user.nickname,
                last_login_time=timezone.to_str(user.last_login_time),
                ip=ctx.ip,
                os=ctx.os,
                browser=ctx.browser,
                device=ctx.device,
                domain=True,
            )
            refresh_token_data = await create_refresh_token(
                access_token_data.session_uuid,
                user.id,
                multi_login=True,
            )
            response.set_cookie(
                key=settings.COOKIE_REFRESH_TOKEN_KEY,
                value=refresh_token_data.refresh_token,
                max_age=settings.COOKIE_REFRESH_TOKEN_EXPIRE_SECONDS,
                expires=timezone.to_utc(refresh_token_data.refresh_token_expire_time),
                httponly=True,
            )
        except errors.NotFoundError as e:
            log.error('登陆错误: 用户名不存在')
            raise errors.NotFoundError(msg=e.msg)
        except (errors.RequestError, errors.CustomError) as e:
            log.error(f'登陆错误: {e}')
            task = BackgroundTask(
                login_log_service.create,
                db=db,
                user_uuid=user.uuid if user else uuid4_str(),
                username=user.username if user else obj.phone,
                login_time=timezone.now(),
                status=LoginLogStatusType.fail.value,
                msg=e.msg,
            )
            raise errors.RequestError(code=e.code, msg=e.msg, background=task)
        except Exception as e:
            log.error(f'登陆错误: {e}')
            raise
        else:
            background_tasks.add_task(
                login_log_service.create,
                db=db,
                user_uuid=user.uuid,
                username=user.username,
                login_time=timezone.now(),
                status=LoginLogStatusType.success.value,
                msg=t('success.login.success'),
            )
            data = GetLoginToken(
                access_token=access_token_data.access_token,
                access_token_expire_time=access_token_data.access_token_expire_time,
                session_uuid=access_token_data.session_uuid,
                user=user,  # type: ignore
            )
            return data

    @staticmethod
    async def refresh_token(*, db: AsyncSession, request: Request) -> GetNewToken:
        """
        刷新令牌

        :param db: 数据库会话
        :param request: FastAPI 请求对象
        :return:
        """
        refresh_token = request.cookies.get(settings.COOKIE_REFRESH_TOKEN_KEY)
        if not refresh_token:
            raise errors.RequestError(msg='Refresh Token 已过期，请重新登录')
        token_payload = jwt_decode(refresh_token)

        user = await user_dao.get(db, token_payload.id)
        if not user:
            raise errors.NotFoundError(msg='用户不存在')

        new_token = await create_new_token(
            refresh_token,
            token_payload.session_uuid,
            user.id,
            multi_login=True,
            # extra info
            username=user.username,
            nickname=user.nickname,
            last_login_time=timezone.to_str(user.last_login_time),
            ip=ctx.ip,
            os=ctx.os,
            browser=ctx.browser,
            device_type=ctx.device,
            domain=True,
        )
        data = GetNewToken(
            access_token=new_token.new_access_token,
            access_token_expire_time=new_token.new_access_token_expire_time,
            session_uuid=new_token.session_uuid,
        )
        return data

    @staticmethod
    async def logout(*, request: Request, response: Response) -> None:
        """
        用户登出

        :param request: FastAPI 请求对象
        :param response: FastAPI 响应对象
        :return:
        """
        try:
            token = get_token(request)
            token_payload = jwt_decode(token)
            user_id = token_payload.id
            session_uuid = token_payload.session_uuid
            refresh_token = request.cookies.get(settings.COOKIE_REFRESH_TOKEN_KEY)
        except errors.TokenError:
            return
        finally:
            response.delete_cookie(settings.COOKIE_REFRESH_TOKEN_KEY)

        await redis_client.delete(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}')
        await redis_client.delete(f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_id}:{session_uuid}')
        if refresh_token:
            await redis_client.delete(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}:{refresh_token}')


auth_service: AuthService = AuthService()
