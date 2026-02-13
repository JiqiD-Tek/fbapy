# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : weather_api.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/23 19:56
"""

import asyncio

from typing import Any

from cachetools import TTLCache

from backend.common.http_client import HTTPClient
from backend.common.log import log


class OpenWeatherMap:
    """
    天气API客户端，用于从 OpenWeatherMap 获取天气预报数据。
    内置了基于TTL的缓存和异步锁，以提高性能并避免重复请求。
    """

    def __init__(
        self,
        appid: str = 'c415d706f949e5295d05a4fded91a4fe',
        cache_ttl: int = 3600,  # 缓存1小时
        max_cache_size: int = 1000,
    ) -> None:

        self.base_url = 'https://api.openweathermap.org'
        self.appid = appid
        self._http_client = HTTPClient(timeout=10.0, read=10.0, write=5.0)

        self._cache = TTLCache(maxsize=max_cache_size, ttl=cache_ttl)
        self._lock = asyncio.Lock()

    async def get_weather_info(self, city: str) -> dict[str, Any] | None:
        """
        获取并缓存指定城市的天气数据。

        Args:
            city (str): 城市名称 (例如, "Paris")。

        Returns:
            Optional[Dict[str, Any]]: 包含天气数据的字典，如果获取失败则返回 None。
        """
        if city in self._cache:
            log.debug(f"Cache hit for city: '{city}'")
            return self._cache[city]

        # 使用异步锁防止对同一城市的重复并发请求
        async with self._lock:
            # 双重检查锁模式：在获取锁后再次检查缓存
            if city in self._cache:
                log.debug(f"Cache hit after acquiring lock for city: '{city}'")
                return self._cache[city]

            log.info(f"Cache miss. Fetching weather data for '{city}' from API.")

            # 调用私有方法执行网络请求
            weather_data = await self._fetch_from_api(city)

            # 缓存结果，即使是None（负缓存），以防止短时间内重复请求失败的城市
            self._cache[city] = weather_data

            return weather_data

    async def _fetch_from_api(self, city: str) -> dict[str, Any] | None:
        """
        从OpenWeatherMap API获取数据的核心逻辑。
        """
        url = f'{self.base_url}/data/2.5/forecast'
        params = {'q': city, 'appid': self.appid, 'units': 'metric'}
        try:
            resp = await self._http_client.get(url, params=params)
            data = resp.json()
            log.info(f"Successfully fetched weather data for '{city}'.")
        except Exception as e:
            log.error(f"Failed to fetch weather for '{city}'. Error: {e!s}", exc_info=True)
            raise
        else:
            return data


# 创建单例
open_weather_map = OpenWeatherMap()


async def main() -> None:
    print("--- First request for 'Shanghai' (should fetch from API) ---")
    rv1 = await open_weather_map.get_weather_info('Shanghai')
    if rv1:
        log.debug(f"Paris weather 'cod': {rv1.get('cod')}")

    print("\n--- Second request for 'Shanghai' (should hit cache) ---")
    rv2 = await open_weather_map.get_weather_info('Shanghai')
    if rv2:
        log.debug('Request for Paris was served from cache.')


if __name__ == '__main__':
    asyncio.run(main())
