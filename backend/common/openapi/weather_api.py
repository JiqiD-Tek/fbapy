# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : weather_api.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/23 19:56
"""

import asyncio
from cachetools import TTLCache

from backend.common.log import log
from backend.common.http_client import HTTPClient


class OpenWeatherMap(object):
    """ 天气API """

    def __init__(self,
                 appid='c415d706f949e5295d05a4fded91a4fe',
                 cache_ttl: int = 86400,
                 max_cache_size: int = 1000):

        self.base_url = "http://api.openweathermap.org"
        self.appid = appid
        self._http_client = HTTPClient(timeout=10.0, read=10.0, write=5.0)

        # 使用LRU缓存+TTL
        self._cache = TTLCache(maxsize=max_cache_size, ttl=cache_ttl)
        self._lock = asyncio.Lock()

    async def get_weather_info(self, city: str):
        """带缓存的天气数据获取"""
        if city in self._cache:
            log.debug(f"命中缓存: {city}")
            return self._cache[city]

        async with self._lock:
            if city not in self._cache:
                url = f"{self.base_url}/data/2.5/forecast?q={city}&appid={self.appid}"
                resp = await self._http_client.get(url)
                self._cache[city] = resp.text.strip()

            return self._cache[city]


open_weather_map = OpenWeatherMap()


async def main():
    rv = await open_weather_map.get_weather_info("Paris")
    log.debug(rv)


if __name__ == '__main__':
    asyncio.run(main())
