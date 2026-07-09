# -*- coding: UTF-8 -*-
"""
Doubao OpenAI-compatible client helpers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx
from openai import AsyncOpenAI

from backend.common.exception import errors
from backend.core.conf import settings

DoubaoMessage = dict[str, Any]

DEFAULT_DOUBAO_CHAT_MODEL = 'doubao-seed-2-0-mini-260428'
DEFAULT_DOUBAO_STORY_MODEL = 'doubao-seed-2-0-mini-260428'
VALID_REASONING_EFFORTS = frozenset({'minimal', 'low', 'medium', 'high'})

DOUBAO_HTTP_TIMEOUT = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=30.0)
DOUBAO_HTTP_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=20, keepalive_expiry=120.0)


def _normalize_text(value: Any) -> str:
    return str(value or '').strip()


def _resolve_doubao_base_url(base_url: str | None = None) -> str:
    normalized_base_url = _normalize_text(base_url) or _normalize_text(settings.DOUBAO_BASE_URL)
    if not normalized_base_url:
        raise errors.ServerError(msg='DOUBAO_BASE_URL is not configured')
    return normalized_base_url


def _resolve_doubao_api_key(api_key: str | None = None) -> str:
    if api_key is not None:
        normalized_api_key = _normalize_text(api_key)
    else:
        normalized_api_key = settings.DOUBAO_API_KEY.get_secret_value().strip()

    if not normalized_api_key:
        raise errors.ServerError(msg='DOUBAO_API_KEY is not configured')
    return normalized_api_key


def create_async_doubao_client(
        *,
        base_url: str | None = None,
        api_key: str | None = None,
) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=_resolve_doubao_api_key(api_key),
        base_url=_resolve_doubao_base_url(base_url),
        http_client=httpx.AsyncClient(
            timeout=DOUBAO_HTTP_TIMEOUT,
            follow_redirects=True,
            limits=DOUBAO_HTTP_LIMITS,
        ),
    )


class DoubaoProvider:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.base_url = _normalize_text(config.get('base_url'))
        self.api_key = _normalize_text(config.get('api_key'))
        self.model_name = _normalize_text(config.get('model_name')) or DEFAULT_DOUBAO_CHAT_MODEL
        self.reasoning_effort = self._normalize_reasoning_effort(config.get('reasoning_effort'))
        self.max_tokens = self._parse_int(config.get('max_tokens'))
        self.temperature = self._parse_float(config.get('temperature'))
        self.top_p = self._parse_float(config.get('top_p'))
        self._async_client: AsyncOpenAI | None = None

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        if value in (None, ''):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_float(value: Any) -> float | None:
        if value in (None, ''):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_reasoning_effort(value: Any) -> str | None:
        normalized_value = _normalize_text(value).lower()
        if normalized_value in VALID_REASONING_EFFORTS:
            return normalized_value
        return None

    @staticmethod
    def normalize_messages(messages: Sequence[DoubaoMessage]) -> list[DoubaoMessage]:
        normalized_messages: list[DoubaoMessage] = []

        for message in messages:
            if not isinstance(message, dict):
                continue

            role = _normalize_text(message.get('role')) or 'user'
            if 'content' not in message:
                continue

            normalized_message = dict(message)
            normalized_message['role'] = role
            normalized_messages.append(normalized_message)

        if not normalized_messages:
            raise errors.RequestError(msg='messages cannot be empty')

        return normalized_messages

    def _get_async_client(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = create_async_doubao_client(
                base_url=self.base_url or None,
                api_key=self.api_key or None,
            )
        return self._async_client

    def _build_request_params(
            self,
            messages: Sequence[DoubaoMessage],
            *,
            model_name: str | None = None,
            stream: bool = False,
            **kwargs,
    ) -> dict[str, Any]:
        request_params: dict[str, Any] = {
            'model': _normalize_text(model_name) or self.model_name,
            'messages': self.normalize_messages(messages),
        }
        if stream:
            request_params['stream'] = True

        reasoning_effort = self._normalize_reasoning_effort(
            kwargs.get('reasoning_effort', self.reasoning_effort)
        )
        optional_params = {
            'reasoning_effort': reasoning_effort,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
            'temperature': kwargs.get('temperature', self.temperature),
            'top_p': kwargs.get('top_p', self.top_p),
        }
        for key, value in optional_params.items():
            if value is not None:
                request_params[key] = value

        tools = kwargs.get('tools')
        if tools:
            request_params['tools'] = tools

        return request_params

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        if not getattr(response, 'choices', None):
            return ''

        message = response.choices[0].message
        content = getattr(message, 'content', '') or ''

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    text = _normalize_text(item.get('text'))
                else:
                    text = _normalize_text(getattr(item, 'text', ''))

                if text:
                    parts.append(text)
            return ''.join(parts).strip()

        return _normalize_text(content)

    async def chat(
            self,
            messages: Sequence[DoubaoMessage],
            *,
            model_name: str | None = None,
            **kwargs,
    ) -> str:
        response = await self._get_async_client().chat.completions.create(
            **self._build_request_params(messages, model_name=model_name, **kwargs),
        )
        content = self._extract_response_text(response)
        if not content:
            raise errors.GatewayError(msg='Doubao returned empty content')
        return content

    @staticmethod
    def _extract_stream_text(chunk: Any) -> str:
        if not getattr(chunk, 'choices', None):
            return ''

        delta = getattr(chunk.choices[0], 'delta', None)
        if delta is None:
            return ''

        content = getattr(delta, 'content', '') or ''
        if isinstance(content, str):
            return content
        return _normalize_text(content)

    @staticmethod
    async def _close_stream(stream: Any) -> None:
        aclose = getattr(stream, 'aclose', None)
        if callable(aclose):
            await aclose()

    async def stream_chat(
            self,
            messages: Sequence[DoubaoMessage],
            *,
            model_name: str | None = None,
            **kwargs,
    ) -> AsyncIterator[str]:
        stream = await self._get_async_client().chat.completions.create(
            **self._build_request_params(messages, model_name=model_name, stream=True, **kwargs),
        )
        try:
            async for chunk in stream:
                text = self._extract_stream_text(chunk)
                if text:
                    yield text
        finally:
            await self._close_stream(stream)

    async def close(self) -> None:
        if self._async_client is not None:
            await self._async_client.close()
            self._async_client = None


doubao_provider = DoubaoProvider()
