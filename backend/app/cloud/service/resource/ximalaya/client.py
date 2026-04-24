"""小雅开放平台异步客户端实现。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from typing import TYPE_CHECKING, Any, Literal

import httpx

from backend.common.http_client import HTTPClient

from .exceptions import XimalayaAPIError
from .models import FORM_CONTENT_TYPE, JSONResponse, RequestParams, RequestValue, XimalayaClientConfig

if TYPE_CHECKING:
    from types import TracebackType

    from typing_extensions import Self


class XimalayaOpenAPIClient:
    def __init__(
            self,
            config: XimalayaClientConfig,
            *,
            http_client: HTTPClient | None = None,
            timeout: float | None = 30.0,
            read: float | None = 30.0,
            write: float | None = 15.0,
    ) -> None:
        self.config = config
        self._owns_http_client = http_client is None
        self._http_client = http_client or HTTPClient(timeout=timeout, read=read, write=write)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http_client.close()

    @staticmethod
    def serialize_value(value: RequestValue) -> str:
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if value is None:
            return ''
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        return str(value)

    @staticmethod
    def generate_nonce(length: int = 16) -> str:
        return secrets.token_hex(length // 2)

    @staticmethod
    def current_timestamp_ms() -> int:
        return int(time.time() * 1000)

    def build_url(self, path: str) -> str:
        if path.startswith(('http://', 'https://')):
            return path
        return f'{self.config.base_url.rstrip("/")}/{path.lstrip("/")}'

    def build_common_params(
            self,
            *,
            nonce: str | None = None,
            timestamp: int | None = None,
    ) -> RequestParams:
        params: RequestParams = {
            'app_key': self.config.app_key,
            'client_os_type': self.config.client_os_type,
            'device_id_type': self.config.device_id_type,
            'device_id': self.config.device_id,
            'sn': self.config.sn,
            'nonce': nonce or self.generate_nonce(),
            'timestamp': timestamp or self.current_timestamp_ms(),
        }
        if self.config.version:
            params['version'] = self.config.version
        return params

    def normalize_params(self, params: RequestParams | None = None) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in (params or {}).items():
            if value is None or key == 'sig':
                continue
            normalized[key] = self.serialize_value(value)
        return normalized

    def sign(self, params: RequestParams | None = None) -> str:
        normalized = self.normalize_params(params)
        sorted_items = sorted(normalized.items())
        joined = '&'.join(f'{key}={value}' for key, value in sorted_items)
        encoded = base64.b64encode(joined.encode('utf-8'))
        sha1_bytes = hmac.new(self.config.app_secret.encode('utf-8'), encoded, hashlib.sha1).digest()
        return hashlib.md5(sha1_bytes).hexdigest()

    def build_signed_params(
            self,
            params: RequestParams | None = None,
            *,
            nonce: str | None = None,
            timestamp: int | None = None,
    ) -> dict[str, str]:
        merged = self.build_common_params(nonce=nonce, timestamp=timestamp)
        if params:
            merged.update(params)
        normalized = self.normalize_params(merged)
        normalized['sig'] = self.sign(normalized)
        return normalized

    async def list_tags(
            self,
            *,
            params: RequestParams | None = None,
            nonce: str | None = None,
            timestamp: int | None = None,
    ) -> JSONResponse:
        return await self._request('GET', '/v2/tags/list', params=params, nonce=nonce, timestamp=timestamp)

    async def list_albums(
            self,
            *,
            params: RequestParams | None = None,
            nonce: str | None = None,
            timestamp: int | None = None,
    ) -> JSONResponse:
        return await self._request('GET', '/v2/albums/list', params=params, nonce=nonce, timestamp=timestamp)

    async def browse_album(
            self,
            *,
            params: RequestParams | None = None,
            nonce: str | None = None,
            timestamp: int | None = None,
    ) -> JSONResponse:
        return await self._request('GET', '/albums/browse', params=params, nonce=nonce, timestamp=timestamp)

    async def search_albums(
        self,
        *,
        params: RequestParams | None = None,
        nonce: str | None = None,
        timestamp: int | None = None,
    ) -> JSONResponse:
        return await self._request('GET', '/search/albums', params=params, nonce=nonce, timestamp=timestamp)

    async def recommend_albums(
        self,
        *,
        params: RequestParams | None = None,
        nonce: str | None = None,
        timestamp: int | None = None,
    ) -> JSONResponse:
        return await self._request('GET', '/operation/recommend_albums', params=params, nonce=nonce, timestamp=timestamp)

    async def _request(
        self,
            method: Literal['GET', 'POST'],
            path: str,
            *,
            params: RequestParams | None = None,
            nonce: str | None = None,
            timestamp: int | None = None,
    ) -> JSONResponse:
        signed_params = self.build_signed_params(params, nonce=nonce, timestamp=timestamp)
        url = self.build_url(path)

        try:
            if method == 'GET':
                response = await self._http_client.get(url, params=signed_params)
            else:
                response = await self._http_client.request(
                    method,
                    url,
                    data=signed_params,
                    headers={'Content-Type': FORM_CONTENT_TYPE},
                )
        except httpx.HTTPStatusError as exc:
            raise self._build_http_error(exc) from exc

        return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> JSONResponse:
        try:
            payload = response.json()
        except ValueError as exc:
            raise XimalayaAPIError(
                'Ximalaya API returned a non-JSON response',
                status_code=response.status_code,
                payload=response.text,
            ) from exc

        if self._payload_is_error(payload):
            raise XimalayaAPIError.from_payload(payload, status_code=response.status_code)
        return payload

    def _build_http_error(self, exc: httpx.HTTPStatusError) -> XimalayaAPIError:
        response = exc.response
        if response is None:
            return XimalayaAPIError(str(exc))

        try:
            payload = response.json()
        except ValueError:
            payload = response.text

        if isinstance(payload, dict):
            return XimalayaAPIError.from_payload(payload, status_code=response.status_code)
        return XimalayaAPIError(str(exc), status_code=response.status_code, payload=payload)

    @staticmethod
    def _payload_is_error(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        if 'error_no' in payload or 'error_code' in payload or 'error_desc' in payload:
            return True

        code = payload.get('code')
        if isinstance(code, int) and code != 0 and any(key in payload for key in ('message', 'msg')):
            return True

        ret = payload.get('ret')
        return bool(isinstance(ret, int) and ret != 0)
