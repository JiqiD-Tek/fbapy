# -*- coding: UTF-8 -*-
"""
@Project : jiqid_dev
@File    : news_api.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/23 20:21
"""
import asyncio
import datetime
from cachetools import TTLCache

from backend.common.log import log
from backend.common.http_client import HTTPClient


class NewsApi(object):
    """ 新闻API """

    def __init__(self,
                 apikey: str = '62542980ed714de39d26cd1499779d18',
                 language: str = 'action_zh',
                 country: str = 'ch',
                 max_cache_size: int = 1000,
                 cache_ttl: int = 3600
                 ):
        self.base_url = "https://newsapi.org"
        self.apikey = apikey
        self.language = language  # action_en action_zh
        self.country = country  # us action_zh
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

    async def get_news(self, query):
        if query in self._cache:
            log.debug(f"命中缓存: {query}")
            return self._cache[query]

        # 加锁防止重复请求
        async with self._lock:
            # 双重检查锁模式
            if query in self._cache:
                return self._cache[query]

            try:
                data = await self._get_news(query)
                self._cache[query] = data
                return data

            except Exception as e:
                log.error(f"新闻查询失败: {query}, 错误: {str(e)}", exc_info=True)
                raise ValueError(f"无法获取新闻: {str(e)}")

    async def _get_news(self, query: str) -> dict:
        """带缓存的天气数据获取"""
        url = f"{self.base_url}/v2/everything"
        params = {
            "q": query,
            "from": (datetime.datetime.now() - datetime.timedelta(days=1)).strftime(format="%Y-%m-%d"),
            "language": self.language,
            "sortBy": "popularity",
            "apiKey": self.apikey,
            "page": 1,
            "pageSize": 1,
        }
        resp = await self._http_client.get(url, params=params)
        return resp.json()


news_api = NewsApi()
