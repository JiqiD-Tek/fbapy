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

from backend.common.http_client import HTTPClient
from backend.common.exception import errors
from backend.common.log import log
from backend.common.response.response_code import CustomErrorCode
from backend.core.conf import settings

from .client import XimalayaOpenAPIClient
from .exceptions import XimalayaAPIError
from .models import XimalayaClientConfig

if TYPE_CHECKING:
    from backend.app.cloud.schema.resource.ximalaya import (
        XimalayaBrowseAlbumParam,
        XimalayaListAlbumsParam,
        XimalayaRecommendedParam,
        XimalayaListTagsParam,
        XimalayaSearchAlbumsParam,
    )

XimalayaResponse = dict[str, Any] | list[Any]


class XimalayaService:
    """小雅开放平台服务封装。"""

    def __init__(self) -> None:
        self._http_client: HTTPClient | None = None

    def _get_http_client(self) -> HTTPClient:
        if self._http_client is None:
            self._http_client = HTTPClient(timeout=30.0, read=30.0, write=15.0)
        return self._http_client

    async def close(self) -> None:
        if self._http_client is None:
            return
        await self._http_client.close()
        self._http_client = None

    @staticmethod
    def _resolve_client_config(*, device_id: str) -> XimalayaClientConfig:
        return XimalayaClientConfig(
            app_key=settings.XIMALAYA_APP_KEY,
            app_secret=settings.XIMALAYA_APP_SECRET.get_secret_value(),
            sn=settings.XIMALAYA_SN,
            device_id=device_id,
        )

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
        raise errors.CustomError(
            error=CustomErrorCode.XIMALAYA_INVOKE_ERROR,
            msg=message,
            data=data,
        ) from exc

    async def recommend_albums(
            self,
            obj: XimalayaRecommendedParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.did)

        try:
            async with XimalayaOpenAPIClient(config, http_client=self._get_http_client()) as client:
                return await client.recommend_albums()
        except XimalayaAPIError as exc:
            data = self._build_api_error_data(exc)
            log.error(f'Ximalaya API error: {exc}; data={data}')
            self._raise_invoke_error(message=str(exc), data=data, exc=exc)
        except httpx.RequestError as exc:
            log.error(f'Ximalaya request failed: {exc}')
            self._raise_invoke_error(message=f'Ximalaya request failed: {exc}', exc=exc)
        except ValueError as exc:
            raise errors.RequestError(msg=exc.args[0] if exc.args else str(exc)) from exc
        except Exception as exc:
            log.error(f'Ximalaya service unexpected error: {exc}')
            raise errors.ServerError(msg=str(exc)) from exc

    async def list_tags(
            self,
            obj: XimalayaListTagsParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.did)
        params = obj.model_dump(exclude_none=True, exclude={'device_id'})

        try:
            async with XimalayaOpenAPIClient(config, http_client=self._get_http_client()) as client:
                return await client.list_tags(params=params)
        except XimalayaAPIError as exc:
            data = self._build_api_error_data(exc)
            log.error(f'Ximalaya API error: {exc}; data={data}')
            self._raise_invoke_error(message=str(exc), data=data, exc=exc)
        except httpx.RequestError as exc:
            log.error(f'Ximalaya request failed: {exc}')
            self._raise_invoke_error(message=f'Ximalaya request failed: {exc}', exc=exc)
        except ValueError as exc:
            raise errors.RequestError(msg=exc.args[0] if exc.args else str(exc)) from exc
        except Exception as exc:
            log.error(f'Ximalaya service unexpected error: {exc}')
            raise errors.ServerError(msg=str(exc)) from exc

    async def list_albums(
            self,
            obj: XimalayaListAlbumsParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.did)
        params = obj.model_dump(exclude_none=True, exclude={'device_id'})

        try:
            async with XimalayaOpenAPIClient(config, http_client=self._get_http_client()) as client:
                return await client.list_albums(params=params)
        except XimalayaAPIError as exc:
            data = self._build_api_error_data(exc)
            log.error(f'Ximalaya API error: {exc}; data={data}')
            self._raise_invoke_error(message=str(exc), data=data, exc=exc)
        except httpx.RequestError as exc:
            log.error(f'Ximalaya request failed: {exc}')
            self._raise_invoke_error(message=f'Ximalaya request failed: {exc}', exc=exc)
        except ValueError as exc:
            raise errors.RequestError(msg=exc.args[0] if exc.args else str(exc)) from exc
        except Exception as exc:
            log.error(f'Ximalaya service unexpected error: {exc}')
            raise errors.ServerError(msg=str(exc)) from exc

    async def browse_album(
            self,
            obj: XimalayaBrowseAlbumParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.did)
        params = obj.model_dump(exclude_none=True, exclude={'device_id'})

        try:
            async with XimalayaOpenAPIClient(config, http_client=self._get_http_client()) as client:
                return await client.browse_album(params=params)
        except XimalayaAPIError as exc:
            data = self._build_api_error_data(exc)
            log.error(f'Ximalaya API error: {exc}; data={data}')
            self._raise_invoke_error(message=str(exc), data=data, exc=exc)
        except httpx.RequestError as exc:
            log.error(f'Ximalaya request failed: {exc}')
            self._raise_invoke_error(message=f'Ximalaya request failed: {exc}', exc=exc)
        except ValueError as exc:
            raise errors.RequestError(msg=exc.args[0] if exc.args else str(exc)) from exc
        except Exception as exc:
            log.error(f'Ximalaya service unexpected error: {exc}')
            raise errors.ServerError(msg=str(exc)) from exc

    async def search_albums(
            self,
            obj: XimalayaSearchAlbumsParam,
    ) -> XimalayaResponse:
        config = self._resolve_client_config(device_id=obj.did)
        params = obj.model_dump(exclude_none=True, exclude={'device_id'})

        try:
            async with XimalayaOpenAPIClient(config, http_client=self._get_http_client()) as client:
                return await client.search_albums(params=params)
        except XimalayaAPIError as exc:
            data = self._build_api_error_data(exc)
            log.error(f'Ximalaya API error: {exc}; data={data}')
            self._raise_invoke_error(message=str(exc), data=data, exc=exc)
        except httpx.RequestError as exc:
            log.error(f'Ximalaya request failed: {exc}')
            self._raise_invoke_error(message=f'Ximalaya request failed: {exc}', exc=exc)
        except ValueError as exc:
            raise errors.RequestError(msg=exc.args[0] if exc.args else str(exc)) from exc
        except Exception as exc:
            log.error(f'Ximalaya service unexpected error: {exc}')
            raise errors.ServerError(msg=str(exc)) from exc


ximalaya_service: XimalayaService = XimalayaService()
