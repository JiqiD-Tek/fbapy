# -*- coding: UTF-8 -*-
"""
@Project : jiqid_dev
@File    : open_weather_map.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/23 19:56
"""
import asyncio
from cachetools import TTLCache

from pypinyin import pinyin, Style

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

    async def get_weather_info(self, query: str) -> dict:
        """带缓存的天气数据获取"""
        query = self.extract_location(query)
        query = self.city_to_pinyin(query)

        if query in self._cache:
            log.debug(f"命中缓存: {query}")
            return self._cache[query]

        # 加锁防止重复请求
        async with self._lock:
            # 双重检查锁模式
            if query in self._cache:
                return self._cache[query]

            try:
                data = await self._get_weather_info(query=query)
                self._cache[query] = data
                return data
            except Exception as e:
                log.error(f"天气查询失败: query={query}, 错误: {str(e)}")
                raise ValueError(f"天气查询失败: {str(e)}")

    async def _get_weather_info(self, query: str) -> dict:
        url = f"{self.base_url}/data/2.5/forecast?q={query}&appid={self.appid}"
        resp = await self._http_client.get(url)
        return resp.json()

    @staticmethod
    def extract_location(query: str) -> str:
        """标准化地理位置（示例简化）TODO 优化"""
        return query.lower().replace("市", "").strip()

    @staticmethod
    def city_to_pinyin(query: str) -> str:
        """将中文城市名转为拼音（小写无空格）"""
        # 风格选择:
        # - Style.NORMAL   : 普通拼音（带声调，如 nán jīng）
        # - Style.TONE2    : 数字标调（如 nan2 jing1）
        # - Style.NORMAL   : 无音标（默认，如 nan jing）
        pinyin_list = pinyin(query, style=Style.NORMAL)
        return ''.join([p[0] for p in pinyin_list]).lower()


open_weather_map = OpenWeatherMap()
