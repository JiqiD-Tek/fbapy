from fastapi import Request
import secrets

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask, BackgroundTasks

from backend.app.admin.service.login_log_service import login_log_service
from backend.app.cloud.crud.crud_user import user_dao
from backend.app.cloud.crud.crud_device import device_dao
from backend.app.cloud.model import Baby, Device
from backend.app.cloud.model.m2m import user_device
from backend.app.cloud.model.user import User
from backend.app.cloud.schema.device.device import CreateDeviceParam
from backend.app.cloud.schema.token import (
    GetLoginToken,
    GetNewToken,
    MiniProvisionPayload,
    MiniProvisionStatusDetail,
    MiniProvisionTokenDetail,
)
from backend.app.cloud.schema.user import (
    AuthLoginParam,
    CreateUserParam,
    DeviceAuthParam,
    MiniProgramLoginParam,
    MiniProgramProfileParam,
    UserDeviceParam,
)
from backend.app.cloud.service.device_service import device_service
from backend.common.providers.mini_service import mini_service
from backend.common.context import ctx
from backend.common.enums import LoginLogStatusType, MiniProvisionStatus
from backend.common.exception import errors
from backend.common.i18n import t
from backend.common.log import log
from backend.common.response.response_code import CustomErrorCode
from backend.common.security.auth import identity_verifier
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


class AuthService:
    """认证服务类"""

    @staticmethod
    def _build_login_log_username(user: User | None) -> str:
        if user is None:
            return ''
        return user.username or user.phone or user.email or user.unionid or user.uuid

    @staticmethod
    async def _issue_login_token(*, db: AsyncSession, user: User) -> GetLoginToken:
        await user_dao.update_login_time(db, user.id)
        await db.refresh(user)

        access_token_data = await create_access_token(
            user.id,
            multi_login=True,
            username=user.username,
            nickname=user.nickname,
            last_login_time=timezone.to_str(user.last_login_time),
            ip=ctx.ip,
            os=ctx.os,
            browser=ctx.browser,
            device=ctx.device,
            terminal=True,
        )
        refresh_token_data = await create_refresh_token(
            access_token_data.session_uuid,
            user.id,
            multi_login=True,
        )

        return GetLoginToken(
            access_token=access_token_data.access_token,
            access_token_expire_time=access_token_data.access_token_expire_time,
            refresh_token=refresh_token_data.refresh_token,
            refresh_token_expire_time=refresh_token_data.refresh_token_expire_time,
            session_uuid=access_token_data.session_uuid,
            user=user,  # type: ignore[arg-type]
        )

    @staticmethod
    def _extract_mini_openid(payload: dict) -> str:
        openid = str(payload.get('openid') or '').strip()
        if not openid:
            raise errors.GatewayError(msg='微信小程序登录响应缺少 openid', data=payload)
        return openid

    @staticmethod
    def _extract_mini_unionid(payload: dict) -> str:
        unionid = str(payload.get('unionid') or '').strip()
        if not unionid:
            raise errors.GatewayError(msg='当前小程序登录响应未返回 unionid', data=payload)
        return unionid

    @staticmethod
    def _extract_mini_phone_number(payload: dict) -> str:
        phone_info = payload.get('phone_info')
        if not isinstance(phone_info, dict):
            raise errors.GatewayError(msg='微信小程序手机号响应缺少 phone_info', data=payload)

        phone_number = str(phone_info.get('purePhoneNumber') or phone_info.get('phoneNumber') or '').strip()
        if not phone_number:
            raise errors.GatewayError(msg='微信小程序手机号响应缺少手机号', data=payload)

        return phone_number

    @staticmethod
    def _normalize_provision_token(token: str) -> str:
        normalized = str(token or '').strip()
        if not normalized:
            raise errors.RequestError(msg='token 不能为空')
        return normalized

    @classmethod
    def _mini_provision_token_key(cls, token: str) -> str:
        return f'{settings.MINI_PROVISION_TOKEN_REDIS_PREFIX}:{cls._normalize_provision_token(token)}'

    @staticmethod
    def _build_mini_provision_payload(*, token: str, user: User) -> MiniProvisionPayload:
        return MiniProvisionPayload(
            token=token,
            user_id=user.id,
            status=MiniProvisionStatus.pending,
            msg='等待设备绑定',
            bound=False,
            device_id=None,
            device_did=None,
            device_sn=None,
        )

    @classmethod
    async def _load_mini_provision_payload(cls, token: str) -> tuple[str, str, MiniProvisionPayload]:
        normalized_token = cls._normalize_provision_token(token)
        key = cls._mini_provision_token_key(normalized_token)
        payload_raw = await redis_client.get(key)
        if not payload_raw:
            raise errors.NotFoundError(msg='配网 token 不存在或已过期')

        try:
            payload = MiniProvisionPayload.model_validate_json(payload_raw)
        except Exception as exc:
            raise errors.ServerError(msg='配网 token 数据损坏') from exc

        return normalized_token, key, payload

    @classmethod
    async def _save_mini_provision_payload(
            cls,
            *,
            key: str,
            payload: MiniProvisionPayload,
            expire_seconds: int | None = None,
    ) -> int:
        ttl = expire_seconds if expire_seconds is not None else await redis_client.ttl(key)
        if ttl is None or ttl <= 0:
            ttl = settings.MINI_PROVISION_TOKEN_EXPIRE_SECONDS

        await redis_client.set(key, payload.model_dump_json(), ex=ttl)
        return ttl

    @classmethod
    async def create_mini_provision_token(
            cls,
            *,
            db: AsyncSession,
            user_id: int,
    ) -> MiniProvisionTokenDetail:
        user = await user_dao.get(db, user_id)
        if user is None:
            raise errors.NotFoundError(msg='用户不存在')

        token = secrets.token_urlsafe(24)
        payload = cls._build_mini_provision_payload(token=token, user=user)
        await redis_client.set(
            cls._mini_provision_token_key(token),
            payload.model_dump_json(),
            ex=settings.MINI_PROVISION_TOKEN_EXPIRE_SECONDS,
        )

        return payload.to_token_detail(settings.MINI_PROVISION_TOKEN_EXPIRE_SECONDS)

    @classmethod
    async def get_mini_provision_status(
            cls,
            *,
            user_id: int,
            token: str,
    ) -> MiniProvisionStatusDetail:
        _, key, payload = await cls._load_mini_provision_payload(token)
        payload_user_id = payload.user_id
        if payload_user_id != user_id:
            raise errors.ForbiddenError(msg='无权查看该配网 token')

        ttl = await redis_client.ttl(key)
        if ttl is None or ttl < 0:
            ttl = 0

        return payload.to_status_detail(ttl)

    @classmethod
    async def bind_device_by_mini_provision_token(
            cls,
            *,
            db: AsyncSession,
            device: DeviceAuthParam,
            token: str,
    ) -> MiniProvisionStatusDetail:
        _, key, payload = await cls._load_mini_provision_payload(token)

        try:
            payload_device_did = str(payload.device_did or '').strip()
            if payload.status == MiniProvisionStatus.success:
                if payload_device_did and payload_device_did != device.did:
                    raise errors.RequestError(msg='该配网 token 已被其他设备使用')
                ttl = await redis_client.ttl(key)
                if ttl is None or ttl < 0:
                    ttl = 0
                return payload.to_status_detail(ttl)
            if payload.status == MiniProvisionStatus.failed:
                raise errors.RequestError(msg=payload.msg or '配网绑定失败')

            if payload.user_id <= 0:
                raise errors.ServerError(msg='配网 token 缺少用户信息')

            if await user_dao.get(db, payload.user_id) is None:
                raise errors.NotFoundError(msg='配网用户不存在')

            device_model = await cls._register_device(db, device)
            result = await db.execute(select(user_device.c.user_id).where(user_device.c.device_id == device_model.id))
            bound_user_ids = set(result.scalars().all())
            stale_user_ids = bound_user_ids - {payload.user_id}

            if stale_user_ids:
                await db.execute(
                    update(Baby)
                    .where(Baby.user_id.in_(stale_user_ids), Baby.device_id == device_model.id)
                    .values(device_id=None)
                )
                from backend.app.cloud.service.baby_service import baby_service

                await baby_service.invalidate_device_baby_cache_by_did(device_model.did)

                await db.execute(
                    delete(user_device).where(
                        user_device.c.device_id == device_model.id,
                        user_device.c.user_id != payload.user_id,
                    )
                )

            if payload.user_id in bound_user_ids:
                msg = '设备已绑定当前用户'
            else:
                await device_service.bind_device(
                    db=db,
                    obj=UserDeviceParam(user_id=payload.user_id, device_id=device_model.id),
                )
                msg = '设备绑定成功'

            payload.status = MiniProvisionStatus.success
            payload.msg = msg
            payload.bound = True
            payload.device_id = device_model.id
            payload.device_did = device_model.did
            payload.device_sn = device_model.sn
            ttl = await cls._save_mini_provision_payload(key=key, payload=payload)
            return payload.to_status_detail(ttl)
        except (errors.RequestError, errors.CustomError, errors.ConflictError, errors.GatewayError,
                errors.NotFoundError) as exc:
            if payload.status != MiniProvisionStatus.success:
                payload.status = MiniProvisionStatus.failed
                payload.msg = exc.msg
                payload.bound = False
                await cls._save_mini_provision_payload(key=key, payload=payload)
            raise

    @classmethod
    async def _get_or_create_mini_program_user(
            cls,
            *,
            db: AsyncSession,
            code: str,
    ) -> User:
        session_payload = await mini_service.code_to_session(code)
        cls._extract_mini_openid(session_payload)
        unionid = cls._extract_mini_unionid(session_payload)
        user = await user_dao.get_by_unionid(db, unionid)
        if user is not None:
            return user

        user_param = CreateUserParam.model_construct(
            unionid=unionid,
            username='',
        )
        return await user_dao.create(db, user_param)

    @classmethod
    async def update_mini_program_profile(
            cls,
            *,
            db: AsyncSession,
            user_id: int,
            obj: MiniProgramProfileParam,
    ) -> User:
        user = await user_dao.get(db, user_id)
        if user is None:
            raise errors.NotFoundError(msg='用户不存在')

        if not any([obj.phone_code, obj.nickname, obj.avatar]):
            raise errors.RequestError(msg='请至少提交一项小程序用户信息')

        updates: dict[str, str] = {}

        if obj.phone_code:
            phone_payload = await mini_service.get_user_phone_number(obj.phone_code)
            phone = cls._extract_mini_phone_number(phone_payload)
            existing_phone_user = await user_dao.get_by_phone(db, phone)
            if existing_phone_user is not None and existing_phone_user.id != user.id:
                raise errors.ConflictError(msg='该手机号已绑定其他用户')
            if user.phone != phone:
                updates['phone'] = phone

        if obj.nickname is not None and user.nickname != obj.nickname:
            updates['nickname'] = obj.nickname
        if obj.avatar is not None and user.avatar != obj.avatar:
            updates['avatar'] = obj.avatar

        if updates:
            await user_dao.update_model(db, user.id, updates)
            await db.flush()
            await db.refresh(user)
            await redis_client.delete(f'{settings.JWT_USER_REDIS_PREFIX}:terminal:{user.id}')

        return user

    @classmethod
    async def _register_device(cls, db: AsyncSession, device: DeviceAuthParam) -> Device:
        valid = identity_verifier.verify(**device.model_dump())
        if not valid:
            raise errors.CustomError(error=CustomErrorCode.DEVICE_ILLEGAL)

        model = await device_dao.get_by_did(db, device.did)
        if model is None:
            device_param = CreateDeviceParam.model_construct(
                model=device.model, sn=device.sn, mac=device.mac, did=device.did, quota=3600 * 24  # 默认配额 24小时
            )
            model = await device_dao.create(db, device_param)

        return model

    @classmethod
    async def _register_user(cls, db: AsyncSession, auth: AuthLoginParam) -> User:
        # 邮箱、手机号 加密存储
        # phone = encryptor.encrypt(auth.phone)
        # email = encryptor.encrypt(auth.email)

        phone = auth.phone
        email = auth.email

        if phone:
            user = await user_dao.get_by_phone(db, phone)
        elif email:
            user = await user_dao.get_by_email(db, email)
        else:
            raise errors.CustomError(error=CustomErrorCode.PHONE_EMAIL_NONE)

        if user is None:
            user_param = CreateUserParam.model_construct(phone=phone, email=email, username='')
            user = await user_dao.create(db, user_param)

        return user

    async def _register(self, db: AsyncSession, auth: AuthLoginParam, device: DeviceAuthParam) -> User:
        # 设备合法的用户才支持注册
        device = await self._register_device(db, device)
        user = await self._register_user(db, auth)
        # 绑定设备
        await device_service.bind_device(
            db=db, obj=UserDeviceParam(user_id=user.id, device_id=device.id),
        )

        return user

    async def login(
            self,
            *,
            db: AsyncSession,
            auth: AuthLoginParam,
            device: DeviceAuthParam,
            background_tasks: BackgroundTasks,
    ) -> GetLoginToken:
        """
        用户登录
        """
        user = None
        try:
            if settings.LOGIN_CAPTCHA_ENABLED:
                if not auth.uuid or not auth.captcha:
                    raise errors.RequestError(msg=t('error.captcha.invalid'))
                captcha_code = await redis_client.get(f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{auth.uuid}')
                if not captcha_code:
                    raise errors.RequestError(msg=t('error.captcha.expired'))
                if captcha_code.lower() != auth.captcha.lower():
                    raise errors.CustomError(error=CustomErrorCode.CAPTCHA_ERROR)
                await redis_client.delete(f'{settings.LOGIN_CAPTCHA_REDIS_PREFIX}:{auth.uuid}')

            user = await self._register(db, auth, device)
            data = await self._issue_login_token(db=db, user=user)
        except errors.NotFoundError as e:
            log.error('登陆错误: 用户不存在')
            raise errors.NotFoundError(msg=e.msg)
        except (errors.RequestError, errors.CustomError, errors.ConflictError) as e:
            log.error(f'登陆错误: {e}')
            task = BackgroundTask(
                login_log_service.create,
                user_uuid=user.uuid if user else uuid4_str(),
                username=self._build_login_log_username(user),
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
                user_uuid=user.uuid,
                username=self._build_login_log_username(user),
                login_time=timezone.now(),
                status=LoginLogStatusType.success.value,
                msg=t('success.login.success'),
            )
            return data

    async def mini_program_login(
            self,
            *,
            db: AsyncSession,
            obj: MiniProgramLoginParam,
            background_tasks: BackgroundTasks,
    ) -> GetLoginToken:
        user = None
        try:
            user = await self._get_or_create_mini_program_user(db=db, code=obj.code)
            data = await self._issue_login_token(db=db, user=user)
        except (errors.RequestError, errors.CustomError, errors.ConflictError, errors.GatewayError) as e:
            log.error(f'小程序登录错误: {e}')
            task = BackgroundTask(
                login_log_service.create,
                user_uuid=user.uuid if user else uuid4_str(),
                username=self._build_login_log_username(user),
                login_time=timezone.now(),
                status=LoginLogStatusType.fail.value,
                msg=e.msg,
            )
            raise errors.RequestError(code=e.code, msg=e.msg, background=task)
        except Exception as e:
            log.error(f'小程序登录错误: {e}')
            raise
        else:
            background_tasks.add_task(
                login_log_service.create,
                user_uuid=user.uuid,
                username=self._build_login_log_username(user),
                login_time=timezone.now(),
                status=LoginLogStatusType.success.value,
                msg=t('success.login.success'),
            )
            return data

    @staticmethod
    async def refresh_token(*, db: AsyncSession, refresh_token: str) -> GetNewToken:
        """
        刷新令牌

        :param db: 数据库会话
        :param refresh_token: 刷新令牌
        :return:
        """
        if not refresh_token:
            raise errors.RequestError(msg='Refresh Token 已过期，请重新登录')

        token_payload = jwt_decode(refresh_token)

        user = await user_dao.get(db, token_payload.user_id)
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
            terminal=True,
        )
        data = GetNewToken(
            access_token=new_token.new_access_token,
            access_token_expire_time=new_token.new_access_token_expire_time,
            refresh_token=new_token.new_refresh_token,
            refresh_token_expire_time=new_token.new_refresh_token_expire_time,
            session_uuid=new_token.session_uuid,
        )
        return data

    @staticmethod
    async def logout(*, request: Request) -> None:
        """
        用户登出

        :param request: FastAPI 请求对象
        :return:
        """
        try:
            token = get_token(request)
            token_payload = jwt_decode(token)
            user_id = token_payload.user_id
            session_uuid = token_payload.session_uuid
        except errors.TokenError:
            return

        await redis_client.delete(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}')
        await redis_client.delete(f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_id}:{session_uuid}')
        await redis_client.delete(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}:{session_uuid}')


auth_service: AuthService = AuthService()
