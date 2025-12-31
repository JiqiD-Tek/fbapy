#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : http_client.py
# @Created   : 2025/4/24 19:25

import httpx

from typing import Optional, Dict
from httpx import Response

from backend.common.log import log


class HTTPClient:
    def __init__(
            self, base_url: str = "",
            timeout: Optional[float] = 60.0,
            read: Optional[float] = 60.0,
            write: Optional[float] = 30.0,
            headers: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.read = read
        self.write = write
        self.headers = headers or {}

        self._http_client = self._create_http_client()

    def _create_http_client(self) -> httpx.AsyncClient:
        """大模型高并发专用HTTP客户端，具备：
        - 智能连接池
        - 流式长超时
        - 多层容错
        - 资源监控
        """
        limits = httpx.Limits(
            max_keepalive_connections=50,
            max_connections=200,
            keepalive_expiry=300.0
        )

        transport = httpx.AsyncHTTPTransport(
            retries=5,
            http2=True,
            limits=limits,
        )

        return httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(
                timeout=self.timeout,  # 全局超时兜底
                read=self.read,  # 读取超时
                write=self.write,  # 发送超时
                pool=10.0  # 连接池超时
            ),
            limits=limits,
            transport=transport,
            headers={"User-Agent": "ModelClient/1.0"},
            max_redirects=5,
            follow_redirects=True,
            verify=False,
        )

    async def request(self, method: str, url: str, **kwargs) -> Response | None:
        """封装请求方法，支持GET、POST等请求类型"""
        try:
            response = await self._http_client.request(method, url, **kwargs)
            response.raise_for_status()  # 如果响应状态码不是 200，会抛出 HTTPStatusError
            return response
        except httpx.RequestError as e:
            log.error(f"Request error: {e}")
            raise
        except httpx.HTTPStatusError as e:
            log.error(f"HTTP error: {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            raise

    async def get(self, url: str, params: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
        """封装 GET 请求"""
        return await self.request("GET", url, params=params, **kwargs)

    async def post(self, url: str, json: Optional[Dict] = None, **kwargs) -> httpx.Response:
        """封装 POST 请求"""
        return await self.request("POST", url, json=json, **kwargs)

    async def close(self):
        """关闭客户端连接"""
        await self._http_client.aclose()
