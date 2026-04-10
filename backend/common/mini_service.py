# -*- coding: UTF-8 -*-
"""
WeChat Mini Program Async Service
Author: guhua@jiqid.com
"""

from __future__ import annotations

import asyncio

from typing import Any, Literal

import httpx

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.redis import redis_client

MiniAPIResponse = dict[str, Any]
MiniProgramState = Literal['developer', 'trial', 'formal']

HTTP_TIMEOUT = httpx.Timeout(
    connect=settings.MINI_REQUEST_TIMEOUT_SECONDS,
    read=settings.MINI_REQUEST_TIMEOUT_SECONDS,
    write=settings.MINI_REQUEST_TIMEOUT_SECONDS,
    pool=settings.MINI_REQUEST_TIMEOUT_SECONDS,
)
HTTP_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=20, keepalive_expiry=120.0)


class MiniService:
    def __init__(self) -> None:
        self._access_token_lock = asyncio.Lock()
        self._http_client = httpx.AsyncClient(
            base_url=self._build_base_url(),
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
            limits=HTTP_LIMITS,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'User-Agent': 'fba-mini-service/1.0',
            },
        )

    @staticmethod
    def _build_base_url() -> str:
        return str(settings.MINI_HOST or '').strip().rstrip('/')

    @staticmethod
    def _get_appid() -> str:
        return str(settings.MINI_APPID or '').strip()

    @staticmethod
    def _get_secret() -> str:
        return settings.MINI_SECRET.get_secret_value().strip()

    def _ensure_configured(self) -> None:
        missing_fields: list[str] = []
        if not self._get_appid():
            missing_fields.append('MINI_APPID')
        if not self._get_secret():
            missing_fields.append('MINI_SECRET')
        if not self._build_base_url():
            missing_fields.append('MINI_HOST')

        if missing_fields:
            raise errors.ServerError(msg=f'小程序配置缺少 {", ".join(missing_fields)}，请在 backend/.env 中配置')

    def _access_token_cache_key(self) -> str:
        return f'{settings.MINI_ACCESS_TOKEN_REDIS_PREFIX}:{self._get_appid()}'

    @staticmethod
    def _validate_required(value: str, field_name: str) -> str:
        normalized = str(value or '').strip()
        if not normalized:
            raise errors.RequestError(msg=f'{field_name} 不能为空')
        return normalized

    @staticmethod
    def _resolve_mini_program_state(state: MiniProgramState | None) -> MiniProgramState:
        if state is not None:
            return state
        return 'formal' if settings.ENVIRONMENT == 'prod' else 'trial'

    @staticmethod
    def _normalize_subscribe_data(
        data: dict[str, Any] | None,
        template_values: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}

        for key, value in (data or {}).items():
            if isinstance(value, dict):
                normalized[key] = dict(value) if 'value' in value else {'value': value}
            else:
                normalized[key] = {'value': value}

        for key, value in template_values.items():
            normalized[key] = {'value': value}

        if not normalized:
            raise errors.RequestError(msg='订阅消息 data 不能为空')

        return normalized

    @staticmethod
    def _resolve_token_ttl(payload: MiniAPIResponse) -> int:
        try:
            expires_in = int(payload.get('expires_in', 7200))
        except (TypeError, ValueError):
            expires_in = 7200

        ttl = expires_in - settings.MINI_ACCESS_TOKEN_EXPIRE_BUFFER_SECONDS
        return ttl if ttl > 0 else 60

    @staticmethod
    def _raise_if_api_error(payload: MiniAPIResponse) -> None:
        errcode = payload.get('errcode')
        if errcode in (None, 0, '0'):
            return

        errmsg = str(payload.get('errmsg') or 'unknown error')
        raise errors.GatewayError(msg=f'微信小程序接口调用失败: {errmsg}', data=payload)

    async def _read_cached_access_token(self) -> str | None:
        try:
            cached_value = await redis_client.get(self._access_token_cache_key())
        except Exception as exc:
            log.warning(f'Mini access token cache read failed: {exc}')
            return None

        token = str(cached_value or '').strip()
        return token or None

    async def _write_cached_access_token(self, token: str, payload: MiniAPIResponse) -> None:
        try:
            await redis_client.set(
                self._access_token_cache_key(),
                token,
                ex=self._resolve_token_ttl(payload),
            )
        except Exception as exc:
            log.warning(f'Mini access token cache write failed: {exc}')

    async def _request(
        self,
        method: Literal['GET', 'POST'],
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> MiniAPIResponse:
        self._ensure_configured()

        try:
            response = await self._http_client.request(method, path, params=params, json=json_body)
            response.raise_for_status()
        except httpx.RequestError as exc:
            log.error(f'WeChat mini request failed: {exc}')
            raise errors.GatewayError(msg=f'微信小程序请求失败: {exc}') from exc
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text if exc.response is not None else str(exc)
            log.error(f'WeChat mini HTTP error: {response_text}')
            raise errors.GatewayError(msg=f'微信小程序请求失败: {response_text}') from exc

        try:
            payload = response.json()
        except ValueError as exc:
            log.error(f'WeChat mini non-JSON response: {response.text}')
            raise errors.GatewayError(msg='微信小程序接口返回了非 JSON 响应') from exc

        if not isinstance(payload, dict):
            raise errors.GatewayError(msg='微信小程序接口返回数据格式非法', data=payload)

        self._raise_if_api_error(payload)
        return payload

    async def close(self) -> None:
        await self._http_client.aclose()

    async def get_access_token(self, *, refresh: bool = False) -> str:
        self._ensure_configured()

        if not refresh:
            cached_token = await self._read_cached_access_token()
            if cached_token:
                return cached_token

        async with self._access_token_lock:
            if not refresh:
                cached_token = await self._read_cached_access_token()
                if cached_token:
                    return cached_token

            payload = await self._request(
                'GET',
                '/cgi-bin/token',
                params={
                    'grant_type': 'client_credential',
                    'appid': self._get_appid(),
                    'secret': self._get_secret(),
                },
            )

            access_token = str(payload.get('access_token') or '').strip()
            if not access_token:
                raise errors.GatewayError(msg='微信小程序 access_token 响应缺少 access_token', data=payload)

            await self._write_cached_access_token(access_token, payload)
            return access_token

    async def access_token(self, *, refresh: bool = False) -> str:
        return await self.get_access_token(refresh=refresh)

    async def code_to_session(self, code: str) -> MiniAPIResponse:
        js_code = self._validate_required(code, 'code')
        return await self._request(
            'GET',
            '/sns/jscode2session',
            params={
                'appid': self._get_appid(),
                'secret': self._get_secret(),
                'js_code': js_code,
                'grant_type': 'authorization_code',
            },
        )

    async def code_2_session(self, code: str) -> MiniAPIResponse:
        return await self.code_to_session(code)

    async def get_user_phone_number(self, code: str) -> MiniAPIResponse:
        phone_code = self._validate_required(code, 'code')
        return await self._request(
            'POST',
            '/wxa/business/getuserphonenumber',
            params={'access_token': await self.get_access_token()},
            json_body={'code': phone_code},
        )

    async def getuserphonenumber(self, code: str) -> MiniAPIResponse:
        return await self.get_user_phone_number(code)

    async def send_subscribe_message(
        self,
        openid: str,
        template_id: str,
        *,
        page: str = 'index',
        data: dict[str, Any] | None = None,
        mini_program_state: MiniProgramState | None = None,
        lang: str = 'zh_CN',
        **template_values: Any,
    ) -> MiniAPIResponse:
        normalized_openid = self._validate_required(openid, 'openid')
        normalized_template_id = self._validate_required(template_id, 'template_id')

        return await self._request(
            'POST',
            '/cgi-bin/message/subscribe/send',
            params={'access_token': await self.get_access_token()},
            json_body={
                'touser': normalized_openid,
                'template_id': normalized_template_id,
                'page': page,
                'data': self._normalize_subscribe_data(data, template_values),
                'miniprogram_state': self._resolve_mini_program_state(mini_program_state),
                'lang': lang,
            },
        )

    async def subscribe_send(
        self,
        openid: str,
        template_id: str,
        page: str = 'index',
        **kwargs: Any,
    ) -> MiniAPIResponse:
        return await self.send_subscribe_message(openid, template_id, page=page, **kwargs)

    async def msg_sec_check(
        self,
        openid: str,
        content: str,
        *,
        scene: int = 1,
        version: int = 2,
    ) -> MiniAPIResponse:
        normalized_openid = self._validate_required(openid, 'openid')
        normalized_content = self._validate_required(content, 'content')

        return await self._request(
            'POST',
            '/wxa/msg_sec_check',
            params={'access_token': await self.get_access_token()},
            json_body={
                'content': normalized_content,
                'scene': scene,
                'version': version,
                'openid': normalized_openid,
            },
        )


mini_service = MiniService()

__all__ = ['MiniService', 'mini_service']
