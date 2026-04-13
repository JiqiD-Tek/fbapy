# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : exceptions.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

from __future__ import annotations

from typing import Any


class HuoshanAPIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str | None,
        message: str,
        request_id: str | None = None,
        payload: Any = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        self.payload = payload
        super().__init__(message)

    def __str__(self) -> str:
        code = self.code or 'UnknownError'
        if self.request_id:
            return f'Huoshan API error [{code}] {self.message} (request_id={self.request_id})'
        return f'Huoshan API error [{code}] {self.message}'


class HuoshanOpenAPIError(HuoshanAPIError):
    pass


class HuoshanTTSError(HuoshanAPIError):
    pass
