# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : service.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from backend.common.exception import errors
from backend.common.log import log
from backend.common.response.response_code import CustomErrorCode
from backend.core.conf import settings

from .client import XimalayaOpenAPIClient
from .endpoints import ENDPOINTS
from .exceptions import XimalayaAPIError
from .models import XimalayaClientConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from backend.app.cloud.schema.ximalaya import (
        XimalayaBrowseAlbumParam,
        XimalayaEndpointInvokeParam,
        XimalayaListAlbumsParam,
        XimalayaListCategoriesParam,
        XimalayaListTagsParam,
        XimalayaPathInvokeParam,
        XimalayaSearchAlbumsParam,
        XimalayaSearchTracksParam,
        XimalayaTrackPlayInfoParam,
    )


XimalayaResponse = dict[str, Any] | list[Any]


class XimalayaService:
    """小雅开放平台服务封装。"""

    @staticmethod
    def _resolve_client_config(*, device_id: str) -> XimalayaClientConfig:
        env_app_key = settings.XIMALAYA_APP_KEY or None
        env_app_secret = settings.XIMALAYA_APP_SECRET.get_secret_value() or None
        env_sn = settings.XIMALAYA_SN or None

        config_missing_fields: list[str] = []
        if not env_app_key:
            config_missing_fields.append('app_key')
        if not env_app_secret:
            config_missing_fields.append('app_secret')
        if not env_sn:
            config_missing_fields.append('sn')

        if config_missing_fields:
            raise errors.RequestError(msg=f'喜马拉雅服务端配置缺少 {", ".join(config_missing_fields)}，请在 .env 中配置')

        if not device_id:
            raise errors.RequestError(msg='喜马拉雅请求缺少 device_id，请在请求中传入')

        return XimalayaClientConfig(
            app_key=env_app_key,
            app_secret=env_app_secret,
            sn=env_sn,
            device_id=device_id,
        )

    @staticmethod
    def list_endpoints(group: str | None = None) -> list[dict[str, str]]:
        endpoints = ENDPOINTS.values()
        if group:
            endpoints = [endpoint for endpoint in endpoints if endpoint.group == group]

        def _section_key(section: str) -> tuple[int, ...]:
            return tuple(int(part) for part in section.split('.'))

        return [
            {
                'group': endpoint.group,
                'name': endpoint.name,
                'key': f'{endpoint.group}.{endpoint.name}',
                'path': endpoint.path,
                'method': endpoint.method,
                'section': endpoint.section,
                'description': endpoint.description,
            }
            for endpoint in sorted(endpoints, key=lambda item: _section_key(item.section))
        ]

    @staticmethod
    def _build_api_error_data(exc: XimalayaAPIError) -> dict[str, Any]:
        return {
            'status_code': exc.status_code,
            'error_no': exc.error_no,
            'error_code': exc.error_code,
            'error_desc': exc.error_desc,
            'payload': exc.payload,
        }

    @staticmethod
    def _raise_invoke_error(
        *,
        message: str,
        data: dict[str, Any] | None = None,
        exc: Exception | None = None,
    ) -> None:
        # 保留上游错误细节，方便排查签名、参数和权限问题。
        raise errors.CustomError(
            error=CustomErrorCode.XIMALAYA_INVOKE_ERROR,
            msg=message,
            data=data,
        ) from exc

    @classmethod
    async def _run_request(cls, action: Awaitable[XimalayaResponse]) -> XimalayaResponse:
        try:
            return await action
        except errors.CustomError:
            raise
        except XimalayaAPIError as exc:
            data = cls._build_api_error_data(exc)
            log.error(f'Ximalaya API error: {exc}; data={data}')
            cls._raise_invoke_error(message=str(exc), data=data, exc=exc)
        except httpx.RequestError as exc:
            log.error(f'Ximalaya request failed: {exc}')
            cls._raise_invoke_error(message=f'Ximalaya request failed: {exc}', exc=exc)
        except (KeyError, ValueError) as exc:
            raise errors.RequestError(msg=exc.args[0] if exc.args else str(exc)) from exc
        except Exception as exc:
            log.error(f'Ximalaya service unexpected error: {exc}')
            raise errors.ServerError(msg=str(exc)) from exc

    @staticmethod
    async def _request_endpoint(
        endpoint_key: str,
        *,
        config: XimalayaClientConfig,
        params: dict[str, Any] | None = None,
        nonce: str | None = None,
        timestamp: int | None = None,
    ) -> XimalayaResponse:
        client = XimalayaOpenAPIClient(config)
        try:
            return await client.request_endpoint(
                endpoint_key,
                params=params,
                nonce=nonce,
                timestamp=timestamp,
            )
        finally:
            await client.close()

    @staticmethod
    async def _request_path(
        method: str,
        path: str,
        *,
        config: XimalayaClientConfig,
        params: dict[str, Any] | None = None,
        nonce: str | None = None,
        timestamp: int | None = None,
    ) -> XimalayaResponse:
        client = XimalayaOpenAPIClient(config)
        try:
            return await client.request_path(
                method=method,
                path=path,
                params=params,
                nonce=nonce,
                timestamp=timestamp,
            )
        finally:
            await client.close()

    async def invoke_endpoint(
        self,
        obj: XimalayaEndpointInvokeParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.device_id)
        return await self._run_request(
            self._request_endpoint(
                obj.endpoint_key,
                config=config,
                params=obj.params,
            )
        )

    async def invoke_path(
        self,
        obj: XimalayaPathInvokeParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.device_id)
        return await self._run_request(
            self._request_path(
                method=obj.method,
                path=obj.path,
                config=config,
                params=obj.params,
            )
        )

    async def list_categories(
        self,
        obj: XimalayaListCategoriesParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.device_id)
        return await self._run_request(
            self._request_endpoint(
                'on_demand.list_categories',
                config=config,
            )
        )

    async def list_tags(
        self,
        obj: XimalayaListTagsParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.device_id)
        return await self._run_request(
            self._request_endpoint(
                'on_demand.list_tags',
                config=config,
                params=obj.model_dump(exclude_none=True, exclude={'device_id'}),
            )
        )

    async def list_albums(
        self,
        obj: XimalayaListAlbumsParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.device_id)
        return await self._run_request(
            self._request_endpoint(
                'on_demand.list_albums',
                config=config,
                params=obj.model_dump(exclude_none=True, exclude={'device_id'}),
            )
        )

    async def browse_album(
        self,
        obj: XimalayaBrowseAlbumParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.device_id)
        return await self._run_request(
            self._request_endpoint(
                'on_demand.browse_album',
                config=config,
                params=obj.model_dump(exclude_none=True, exclude={'device_id'}),
            )
        )

    async def search_albums(
        self,
        obj: XimalayaSearchAlbumsParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.device_id)
        return await self._run_request(
            self._request_endpoint(
                'search.search_albums',
                config=config,
                params=obj.model_dump(exclude_none=True, exclude={'device_id'}),
            )
        )

    async def search_tracks(
        self,
        obj: XimalayaSearchTracksParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.device_id)
        return await self._run_request(
            self._request_endpoint(
                'search.search_tracks',
                config=config,
                params=obj.model_dump(exclude_none=True, exclude={'device_id'}),
            )
        )

    async def batch_get_track_play_info(
        self,
        obj: XimalayaTrackPlayInfoParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.device_id)
        return await self._run_request(
            self._request_endpoint(
                'on_demand.batch_get_track_play_info',
                config=config,
                params=obj.build_ids_param(),
            )
        )


ximalaya_service: XimalayaService = XimalayaService()
