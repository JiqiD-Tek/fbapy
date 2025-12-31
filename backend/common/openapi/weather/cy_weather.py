# -*- coding: UTF-8 -*-
"""
@Project : jiqidpy
@File    : cy_weather.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/06 16:08
"""
import asyncio
import json
import time
import uuid
import hmac
import hashlib
import base64
from typing import Dict, Any
from urllib.parse import urlparse

from cachetools import TTLCache
from backend.common.log import log
from backend.common.http_client import HTTPClient


class CyWeatherAPI:
    def __init__(self,
                 app_id: str = "xpgdsvkw",
                 app_secret: str = "etf2XOcW87rXJPbC",
                 base_url: str = "https://test-bus.singapore.aibotplatform.com/assistant/weather/weather-forecast",
                 cache_ttl: int = 86400,
                 max_cache_size: int = 1000
                 ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url

        self._http_client = HTTPClient(
            timeout=10.0,  # 10秒超时
            read=10.0,
            write=5.0
        )

        # 使用LRU缓存+TTL
        self._cache = TTLCache(
            maxsize=max_cache_size,
            ttl=cache_ttl
        )
        self._lock = asyncio.Lock()  # 防止缓存击穿

    def generate_signature(self, params: Dict[str, str], path: str, host: str, body: bytes) -> str:
        """生成HMAC-SHA256签名"""
        try:
            params_copy = params.copy()
            params_copy.update({"path": path, "host": host})

            # 排序并拼接参数
            sorted_params = sorted(params_copy.items())
            query_string = "&".join(f"{k}={v}" for k, v in sorted_params)

            log.debug(f"Query String for Signature: {query_string}")

            # 生成签名
            hashed = hmac.new(
                self.app_secret.encode(),
                query_string.encode(),
                hashlib.sha256
            )
            hashed.update(body)

            signature = base64.b64encode(hashed.digest()).decode()
            log.debug(f"Generated signature: {signature}")
            return signature

        except Exception as e:
            log.error(f"Signature generation failed: {e}")
            raise

    async def send_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """发送签名请求"""
        try:
            parsed_url = urlparse(self.base_url)
            path = parsed_url.path
            host = parsed_url.netloc

            # 准备请求参数
            params = {
                "app_id": self.app_id,
                "timestamp": str(int(time.time())),
                "nonce": str(uuid.uuid4()),
            }

            # 手动序列化确保一致性
            body_data = json.dumps(
                request_data,
                ensure_ascii=False,
                separators=(',', ':')
            ).encode("utf-8")

            # 生成签名
            signature = self.generate_signature(params, path, host, body_data)

            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Signature": signature,
            }

            log.info(f"Sending weather request for: {request_data.get('payload', {}).get('city', 'Unknown')}")

            # 发送请求
            resp = await self._http_client.post(
                url=self.base_url,
                content=body_data,
                headers=headers,
                params=params
            )

            response_data = resp.json()
            log.debug(f"Weather API response: {response_data}")
            return response_data

        except asyncio.TimeoutError:
            log.error("Weather API request timeout")
            raise ValueError("请求超时，请稍后重试")
        except json.JSONDecodeError:
            log.error("Weather API response JSON decode error")
            raise ValueError("服务器响应格式错误")
        except Exception as e:
            log.error(f"Weather API request failed: {e}")
            raise ValueError(f"天气服务暂时不可用: {str(e)}")

    async def _get_weather_info(
            self, query: str, latitude: float = 0., longitude: float = 0.) -> dict:

        request_data = {
            "metadata": {"appID": self.app_id, },
            "payload": {
                "city": query,
                "language": "en",
                "pos": {"latitude": latitude, "longitude": longitude},
            },
        }
        resp = await self.send_request(request_data)
        return resp.get("payload", {})

    async def get_weather_info(
            self, query: str, latitude: float = 0., longitude: float = 0.) -> dict:

        if query in self._cache:
            log.debug(f"命中缓存: {query}")
            return self._cache[query]

        # 加锁防止重复请求
        async with self._lock:
            # 双重检查锁模式
            if query in self._cache:
                return self._cache[query]

            try:
                data = await self._get_weather_info(
                    query=query, latitude=latitude, longitude=longitude)
                self._cache[query] = data
                return data
            except Exception as e:
                log.error(f"天气查询失败: query={query}, 错误: {str(e)}")
                raise ValueError(f"天气查询失败: {str(e)}")


# 全局实例
cy_weather = CyWeatherAPI()


async def main():
    """测试主函数"""
    try:
        # 测试基本查询
        response = await cy_weather.get_weather_info(query="shanghai")
        log.info(f"Response: {response}")

        # 测试带位置的查询
        response2 = await cy_weather.get_weather_info(
            query="beijing",
            latitude=39.9042,
            longitude=116.4074
        )
        log.info(f"Response with location: {response2}")

    except Exception as e:
        log.error(f"Request failed: {e}")


if __name__ == '__main__':
    asyncio.run(main())
