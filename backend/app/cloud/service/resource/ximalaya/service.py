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

from .client import XimalayaOpenAPIClient
from .endpoints import ENDPOINTS
from .exceptions import XimalayaAPIError

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

    from .models import XimalayaClientConfig


XimalayaResponse = dict[str, Any] | list[Any]


class XimalayaService:
    """小雅开放平台服务封装。"""

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

    async def invoke_endpoint(self, obj: XimalayaEndpointInvokeParam) -> XimalayaResponse:
        return await self._run_request(
            self._request_endpoint(
                obj.endpoint_key,
                config=obj.config.to_client_config(),
                params=obj.params,
                **obj.build_request_options(),
            )
        )

    async def invoke_path(self, obj: XimalayaPathInvokeParam) -> XimalayaResponse:
        return await self._run_request(
            self._request_path(
                method=obj.method,
                path=obj.path,
                config=obj.config.to_client_config(),
                params=obj.params,
                **obj.build_request_options(),
            )
        )

    async def list_categories(self, obj: XimalayaListCategoriesParam) -> XimalayaResponse:
        return await self._run_request(
            self._request_endpoint(
                'on_demand.list_categories',
                config=obj.config.to_client_config(),
                **obj.build_request_options(),
            )
        )

    async def list_tags(self, obj: XimalayaListTagsParam) -> XimalayaResponse:
        return await self._run_request(
            self._request_endpoint(
                'on_demand.list_tags',
                config=obj.config.to_client_config(),
                params=obj.build_business_params(),
                **obj.build_request_options(),
            )
        )

    async def list_albums(self, obj: XimalayaListAlbumsParam) -> XimalayaResponse:
        return await self._run_request(
            self._request_endpoint(
                'on_demand.list_albums',
                config=obj.config.to_client_config(),
                params=obj.build_business_params(),
                **obj.build_request_options(),
            )
        )

    async def browse_album(self, obj: XimalayaBrowseAlbumParam) -> XimalayaResponse:
        return await self._run_request(
            self._request_endpoint(
                'on_demand.browse_album',
                config=obj.config.to_client_config(),
                params=obj.build_business_params(),
                **obj.build_request_options(),
            )
        )

    async def search_albums(self, obj: XimalayaSearchAlbumsParam) -> XimalayaResponse:
        return await self._run_request(
            self._request_endpoint(
                'search.search_albums',
                config=obj.config.to_client_config(),
                params=obj.build_business_params(),
                **obj.build_request_options(),
            )
        )

    async def search_tracks(self, obj: XimalayaSearchTracksParam) -> XimalayaResponse:
        return await self._run_request(
            self._request_endpoint(
                'search.search_tracks',
                config=obj.config.to_client_config(),
                params=obj.build_business_params(),
                **obj.build_request_options(),
            )
        )

    async def batch_get_track_play_info(self, obj: XimalayaTrackPlayInfoParam) -> XimalayaResponse:
        return await self._run_request(
            self._request_endpoint(
                'on_demand.batch_get_track_play_info',
                config=obj.config.to_client_config(),
                params=obj.build_ids_param(),
                **obj.build_request_options(),
            )
        )


ximalaya_service: XimalayaService = XimalayaService()
