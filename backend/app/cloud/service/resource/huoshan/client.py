# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : client.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

from __future__ import annotations

import ast
import asyncio
import json
import uuid

from typing import Any

import httpx

from backend.app.cloud.service.resource.huoshan.exceptions import HuoshanOpenAPIError, HuoshanTTSError
from backend.app.cloud.service.resource.huoshan.models import HUOSHAN_TTS_JSON_CONTENT_TYPE, HuoshanLongTextTTSConfig, HuoshanOpenAPIConfig

import volcenginesdkcore

from volcenginesdkcore.rest import ApiException as VolcengineApiException
from volcenginesdkspeechsaasprod20250521 import (
    BatchListMegaTTSTrainStatusRequest,
    OrderAccessResourcePacksRequest,
    RenewAccessResourcePacksRequest,
    SPEECHSAASPROD20250521Api,
)


class HuoshanOpenAPIClient:
    LEGACY_SHARED_HOSTS = frozenset({'', 'open.volcengineapi.com'})

    def __init__(self, config: HuoshanOpenAPIConfig) -> None:
        if volcenginesdkcore is None or SPEECHSAASPROD20250521Api is None:
            raise RuntimeError('volcengine-python-sdk is required for Huoshan voice management APIs')

        configuration = volcenginesdkcore.Configuration()
        configuration.ak = config.access_key
        configuration.sk = config.secret_key
        configuration.region = config.region
        configuration.client_side_validation = False
        configuration.connect_timeout = config.timeout
        configuration.read_timeout = config.timeout

        host = config.host.strip().removeprefix('https://').removeprefix('http://').rstrip('/')
        if host and host not in self.LEGACY_SHARED_HOSTS:
            configuration.host = host

        self._api = SPEECHSAASPROD20250521Api(volcenginesdkcore.ApiClient(configuration))

    async def close(self) -> None:
        return None

    async def batch_list_mega_tts_train_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = BatchListMegaTTSTrainStatusRequest(
            _configuration=self._api.api_client.configuration,
            **payload,
        )
        return await self._invoke(self._api.batch_list_mega_tts_train_status, request)

    async def order_access_resource_packs(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = OrderAccessResourcePacksRequest(
            _configuration=self._api.api_client.configuration,
            **payload,
        )
        return await self._invoke(self._api.order_access_resource_packs, request)

    async def renew_access_resource_packs(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = RenewAccessResourcePacksRequest(
            _configuration=self._api.api_client.configuration,
            **payload,
        )
        return await self._invoke(self._api.renew_access_resource_packs, request)

    async def _invoke(self, func: Any, request: Any) -> dict[str, Any]:
        try:
            response = await asyncio.to_thread(func, request)
        except VolcengineApiException as exc:
            raise self._convert_sdk_error(exc) from exc
        return self._marshal_response(response)

    @staticmethod
    def _marshal_response(response: Any) -> dict[str, Any]:
        metadata = getattr(response, '_metadata', None)
        response_metadata = metadata.to_dict() if metadata and hasattr(metadata, 'to_dict') else {}
        result = response.to_dict() if hasattr(response, 'to_dict') else response
        return {
            'response_metadata': response_metadata,
            'result': result,
        }

    @classmethod
    def _convert_sdk_error(cls, exc: Exception) -> HuoshanOpenAPIError:
        status_code = int(getattr(exc, 'status', 500) or 500)
        parsed_payload = cls._parse_error_payload(getattr(exc, 'body', None))
        parsed_reason = cls._parse_error_payload(getattr(exc, 'reason', None))
        parsed = parsed_payload or parsed_reason or {}

        if parsed and status_code == 200:
            status_code = 400

        headers = getattr(exc, 'headers', None) or {}
        request_id = parsed.get('RequestId') or parsed.get('request_id') or headers.get('X-Tt-Logid')
        code = parsed.get('Code') or parsed.get('code') or str(status_code)
        message = (
                parsed.get('Message')
                or parsed.get('message')
                or str(getattr(exc, 'reason', None) or exc)
                or 'Volcengine OpenAPI request failed'
        )
        payload: Any = parsed or getattr(exc, 'body', None) or getattr(exc, 'reason', None)

        return HuoshanOpenAPIError(
            status_code=status_code,
            code=code,
            message=message,
            request_id=request_id,
            payload=payload,
        )

    @staticmethod
    def _parse_error_payload(raw: Any) -> dict[str, Any]:
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return {}
            for parser in (json.loads, ast.literal_eval):
                try:
                    value = parser(text)
                except (ValueError, SyntaxError):
                    continue
                if isinstance(value, dict):
                    return value
        return {}


class HuoshanLongTextTTSClient:
    SUCCESS_CODES = {0, 20000000}

    def __init__(self, config: HuoshanLongTextTTSConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(timeout=config.timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def submit(self, *, payload: dict[str, Any], resource_id: str | None = None) -> dict[str, Any]:
        response = await self._request_json(
            url=self._config.submit_url,
            body=payload,
            resource_id=resource_id or self._config.resource_id,
        )
        self._assert_success(response, action='submit')
        return response

    async def query(self, *, task_id: str, resource_id: str | None = None) -> dict[str, Any]:
        response = await self._request_json(
            url=self._config.query_url,
            body={'task_id': task_id},
            resource_id=resource_id or self._config.query_resource_id,
        )
        self._assert_success(response, action='query')
        return response

    async def download_file(self, *, url: str) -> bytes:
        try:
            response = await self._client.get(url, follow_redirects=True, timeout=self._config.timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HuoshanTTSError(
                status_code=exc.response.status_code,
                code='DownloadError',
                message=f'Failed to download Huoshan audio: HTTP {exc.response.status_code}',
                payload=exc.response.text,
            ) from exc
        except httpx.RequestError as exc:
            raise HuoshanTTSError(
                status_code=502,
                code='DownloadError',
                message=f'Failed to download Huoshan audio: {exc}',
            ) from exc
        else:
            return response.content

    async def _request_json(self, *, url: str, body: dict[str, Any], resource_id: str) -> dict[str, Any]:
        headers = {
            'Accept': 'application/json',
            'Content-Type': HUOSHAN_TTS_JSON_CONTENT_TYPE,
            'X-Api-App-Id': self._config.app_id,
            'X-Api-Access-Key': self._config.access_key,
            'X-Api-Resource-Id': resource_id,
            'X-Api-Request-Id': uuid.uuid4().hex,
        }

        try:
            response = await self._client.post(url, json=body, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HuoshanTTSError(
                status_code=exc.response.status_code,
                code=str(exc.response.status_code),
                message=f'Huoshan TTS request failed: HTTP {exc.response.status_code}',
                payload=exc.response.text,
            ) from exc
        except httpx.RequestError as exc:
            raise HuoshanTTSError(
                status_code=502,
                code='RequestError',
                message=f'Huoshan TTS request failed: {exc}',
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise HuoshanTTSError(
                status_code=response.status_code,
                code='InvalidResponse',
                message='Huoshan TTS returned a non-JSON response',
                payload=response.text,
            ) from exc

    @classmethod
    def _assert_success(cls, response: dict[str, Any], *, action: str) -> None:
        code = int(response.get('code', -1))
        if code in cls.SUCCESS_CODES:
            return
        raise HuoshanTTSError(
            status_code=400,
            code=str(code),
            message=f'Huoshan TTS {action} returned an error',
            payload=response,
        )

    @staticmethod
    def infer_query_resource_id(resource_id: str) -> str:
        if resource_id in ('seed-tts-1.0', 'seed-tts-2.0'):
            return 'volc.service_type.10029'
        return resource_id
