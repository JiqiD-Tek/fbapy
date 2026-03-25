"""小雅开放平台异常定义。"""

from __future__ import annotations

from typing import Any


class XimalayaAPIError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_no: int | str | None = None,
        error_code: str | None = None,
        error_desc: str | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_no = error_no
        self.error_code = error_code
        self.error_desc = error_desc
        self.payload = payload

    @classmethod
    def from_payload(cls, payload: Any, *, status_code: int | None = None) -> XimalayaAPIError:
        if isinstance(payload, dict):
            error_no = payload.get('error_no') or payload.get('code') or payload.get('ret')
            error_code = payload.get('error_code')
            error_desc = payload.get('error_desc') or payload.get('message') or payload.get('msg')
            message = str(error_desc or error_code or f'Ximalaya API request failed: status={status_code}')
            return cls(
                message,
                status_code=status_code,
                error_no=error_no,
                error_code=error_code,
                error_desc=error_desc,
                payload=payload,
            )
        return cls(f'Ximalaya API request failed: status={status_code}', status_code=status_code, payload=payload)


__all__ = ['XimalayaAPIError']
