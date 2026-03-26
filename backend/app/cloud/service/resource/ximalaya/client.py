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

from .endpoints import ENDPOINTS
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
        timeout: float | None = 30.0,
        read: float | None = 30.0,
        write: float | None = 15.0,
    ) -> None:
        self.config = config
        self._http_client = HTTPClient(timeout=timeout, read=read, write=write)

        # 按接口文档分组暴露子客户端，业务层可直接通过 client.xxx 调用。
        self.oauth = _OAuthAPI(self)
        self.on_demand = _OnDemandAPI(self)
        self.search = _SearchAPI(self)
        self.recommendation = _RecommendationAPI(self)
        self.user = _UserAPI(self)
        self.collector = _CollectorAPI(self)
        self.sleep = _SleepAPI(self)
        self.operation = _OperationAPI(self)
        self.reporting = _ReportingAPI(self)
        self.incremental = _IncrementalAPI(self)
        self.video = _VideoAPI(self)

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
        await self._http_client.close()

    @staticmethod
    def serialize_value(value: RequestValue) -> str:
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if value is None:
            return ''
        if isinstance(value, (dict, list, tuple)):
            # 文档里的复杂参数要求按 JSON 字符串传输，并参与签名计算。
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
        # 签名严格遵循文档步骤：
        # 字典序排序 -> key=value&... -> Base64 -> HMAC-SHA1(原始字节) -> MD5。
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

    async def request_path(
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
                # 文档要求 POST 接口使用 form-urlencoded，不走 JSON body。
                response = await self._http_client.request(
                    method,
                    url,
                    data=signed_params,
                    headers={'Content-Type': FORM_CONTENT_TYPE},
                )
        except httpx.HTTPStatusError as exc:
            raise self._build_http_error(exc) from exc

        return self._parse_response(response)

    async def request_endpoint(
        self,
        endpoint_key: str,
        *,
        params: RequestParams | None = None,
        nonce: str | None = None,
        timestamp: int | None = None,
    ) -> JSONResponse:
        endpoint = ENDPOINTS.get(endpoint_key)
        if endpoint is None:
            raise KeyError(f'Unknown Ximalaya endpoint: {endpoint_key}')

        return await self.request_path(
            endpoint.method,
            endpoint.path,
            params=params,
            nonce=nonce,
            timestamp=timestamp,
        )

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
        # 开放平台同时存在 error_xxx 和 code/message 两种错误体风格，这里统一识别。
        if 'error_no' in payload or 'error_code' in payload or 'error_desc' in payload:
            return True

        code = payload.get('code')
        if isinstance(code, int) and code != 0 and any(key in payload for key in ('message', 'msg')):
            return True

        ret = payload.get('ret')
        return bool(isinstance(ret, int) and ret != 0)


class _EndpointGroup:
    def __init__(self, client: XimalayaOpenAPIClient, group: str) -> None:
        self._client = client
        self._group = group

    async def _call(self, name: str, **params: RequestValue) -> JSONResponse:
        return await self._client.request_endpoint(f'{self._group}.{name}', params=params or None)


class _OAuthAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'oauth')

    async def get_login_url(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_login_url', **params)

    async def get_token_info(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_token_info', **params)

    async def refresh_token(self, **params: RequestValue) -> JSONResponse:
        return await self._call('refresh_token', **params)

    async def secure_access_token(self, **params: RequestValue) -> JSONResponse:
        return await self._call('secure_access_token', **params)


class _OnDemandAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'on_demand')

    async def list_categories(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_categories', **params)

    async def list_tags(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_tags', **params)

    async def list_albums(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_albums', **params)

    async def browse_album(self, **params: RequestValue) -> JSONResponse:
        return await self._call('browse_album', **params)

    async def get_albums_batch(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_albums_batch', **params)

    async def get_album_updates_batch(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_album_updates_batch', **params)

    async def get_tracks_batch(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_tracks_batch', **params)

    async def get_last_play_tracks(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_last_play_tracks', **params)

    async def list_metadata(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_metadata', **params)

    async def list_metadata_albums(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_metadata_albums', **params)

    async def search_columns(self, **params: RequestValue) -> JSONResponse:
        return await self._call('search_columns', **params)

    async def get_columns_batch(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_columns_batch', **params)

    async def browse_column(self, **params: RequestValue) -> JSONResponse:
        return await self._call('browse_column', **params)

    async def batch_get_track_play_info(self, **params: RequestValue) -> JSONResponse:
        return await self._call('batch_get_track_play_info', **params)


class _SearchAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'search')

    async def search_albums(self, **params: RequestValue) -> JSONResponse:
        return await self._call('search_albums', **params)

    async def search_tracks(self, **params: RequestValue) -> JSONResponse:
        return await self._call('search_tracks', **params)

    async def hot_words(self, **params: RequestValue) -> JSONResponse:
        return await self._call('hot_words', **params)

    async def suggest_words(self, **params: RequestValue) -> JSONResponse:
        return await self._call('suggest_words', **params)

    async def text_search(self, **params: RequestValue) -> JSONResponse:
        return await self._call('text_search', **params)


class _RecommendationAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'recommendation')

    async def guess_like_albums(self, **params: RequestValue) -> JSONResponse:
        return await self._call('guess_like_albums', **params)

    async def relative_albums_by_album(self, **params: RequestValue) -> JSONResponse:
        return await self._call('relative_albums_by_album', **params)

    async def relative_albums_by_track(self, **params: RequestValue) -> JSONResponse:
        return await self._call('relative_albums_by_track', **params)

    async def one_click_channels(self, **params: RequestValue) -> JSONResponse:
        return await self._call('one_click_channels', **params)

    async def one_click_next_track(self, **params: RequestValue) -> JSONResponse:
        return await self._call('one_click_next_track', **params)

    async def list_scenes(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_scenes', **params)

    async def list_scene_channels(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_scene_channels', **params)

    async def list_scene_tracks(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_scene_tracks', **params)


class _UserAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'user')

    async def get_user_info(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_user_info', **params)

    async def get_persona(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_persona', **params)

    async def get_subscribe_albums_by_uid(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_subscribe_albums_by_uid', **params)

    async def subscribe_add_or_delete(self, **params: RequestValue) -> JSONResponse:
        return await self._call('subscribe_add_or_delete', **params)

    async def subscribe_batch_add(self, **params: RequestValue) -> JSONResponse:
        return await self._call('subscribe_batch_add', **params)

    async def is_subscribed(self, **params: RequestValue) -> JSONResponse:
        return await self._call('is_subscribed', **params)

    async def get_play_history(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_play_history', **params)

    async def batch_upload_play_history(self, **params: RequestValue) -> JSONResponse:
        return await self._call('batch_upload_play_history', **params)

    async def batch_delete_play_history(self, **params: RequestValue) -> JSONResponse:
        return await self._call('batch_delete_play_history', **params)


class _CollectorAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'collector')

    async def batch_track_records(self, **params: RequestValue) -> JSONResponse:
        return await self._call('batch_track_records', **params)

    async def batch_album_browse_records(self, **params: RequestValue) -> JSONResponse:
        return await self._call('batch_album_browse_records', **params)


class _SleepAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'sleep')

    async def list_topics(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_topics', **params)

    async def list_cards(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_cards', **params)


class _OperationAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'operation')

    async def recommend_albums(self, **params: RequestValue) -> JSONResponse:
        return await self._call('recommend_albums', **params)

    async def list_categories(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_categories', **params)

    async def list_dimensions(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_dimensions', **params)

    async def list_tags_of_dimension(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_tags_of_dimension', **params)

    async def list_dimension_tags(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_dimension_tags', **params)

    async def list_xm_columns(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_xm_columns', **params)

    async def batch_get_columns(self, **params: RequestValue) -> JSONResponse:
        return await self._call('batch_get_columns', **params)

    async def browse_column_content(self, **params: RequestValue) -> JSONResponse:
        return await self._call('browse_column_content', **params)

    async def rank_by_type(self, **params: RequestValue) -> JSONResponse:
        return await self._call('rank_by_type', **params)

    async def browse_rank_albums(self, **params: RequestValue) -> JSONResponse:
        return await self._call('browse_rank_albums', **params)


class _ReportingAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'reporting')

    async def device_activate(self, **params: RequestValue) -> JSONResponse:
        return await self._call('device_activate', **params)


class _IncrementalAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'incremental')

    async def list_album_increments(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_album_increments', **params)

    async def list_track_increments(self, **params: RequestValue) -> JSONResponse:
        return await self._call('list_track_increments', **params)


class _VideoAPI(_EndpointGroup):
    def __init__(self, client: XimalayaOpenAPIClient) -> None:
        super().__init__(client, 'video')

    async def get_video_play_info(self, **params: RequestValue) -> JSONResponse:
        return await self._call('get_video_play_info', **params)

    async def batch_get_video_play_info(self, **params: RequestValue) -> JSONResponse:
        return await self._call('batch_get_video_play_info', **params)


__all__ = ['XimalayaOpenAPIClient']
