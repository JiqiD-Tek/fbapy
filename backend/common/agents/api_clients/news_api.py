# -*- coding: UTF-8 -*-
"""
@Project : jiqid_dev
@File    : news_api.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/23 20:21
"""
import asyncio

from cachetools import TTLCache
from typing import Optional
from langchain_community.tools import DuckDuckGoSearchRun

from backend.common.log import log

duck_tool = DuckDuckGoSearchRun()


class NewsApi:
    """
    新闻API，使用通用的网页搜索工具作为其数据源。
    保留了缓存和异步锁机制以提高性能和避免重复请求。
    """

    def __init__(self,
                 max_cache_size: int = 1000,
                 cache_ttl: int = 3600):

        self._cache = TTLCache(maxsize=max_cache_size, ttl=cache_ttl)
        self._lock = asyncio.Lock()

    async def get_news(self, query: str, num_results: int = 3) -> Optional[str]:
        """
        获取关于特定主题的新闻，并返回格式化的结果。

        Args:
            query (str): 新闻查询的主题。
            num_results (int): 希望返回的头条新闻数量。

        Returns:
            Optional[str]: 格式化后的新闻结果字符串，如果找不到则返回None。
        """
        cache_key = f"{query}::{num_results}"
        if cache_key in self._cache:
            log.debug(f"Cache hit for query: '{query}'")
            return self._cache[cache_key]

        # 使用异步锁防止对同一查询的重复并发请求
        async with self._lock:
            # 双重检查锁模式，再次检查缓存
            if cache_key in self._cache:
                log.debug(f"Cache hit after acquiring lock for query: '{query}'")
                return self._cache[cache_key]

            try:
                log.info(f"Performing web search for news about: '{query}'")
                raw_resp = await asyncio.to_thread(duck_tool.run, query)

                if not raw_resp or not raw_resp.strip():
                    log.warning(f"No results found from web search for '{query}'.")
                    # 缓存空结果以防止短时间内重复查询失败的query
                    self._cache[cache_key] = None
                    return None

                lines = [line.strip() for line in raw_resp.split("\n") if line.strip()]
                top_results = lines[:num_results]

                if not top_results:
                    log.warning(f"No valid lines found after parsing search results for '{query}'.")
                    self._cache[cache_key] = None
                    return None

                formatted_results = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(top_results))
                log.info(f"Top {len(top_results)} news results for '{query}':\n{formatted_results}")

                # 将格式化后的结果存入缓存
                self._cache[cache_key] = formatted_results
                return formatted_results

            except Exception as e:
                log.error(f"Failed to get news for '{query}' due to an error: {str(e)}", exc_info=True)
                # 在这种情况下，我们不缓存结果，以便后续请求可以重试
                return None  # 或者根据需要 re-raise ValueError


# 创建单例
news_api = NewsApi()


# --- 示例用法 ---
async def main():
    print("--- First request for 'AI advancements' ---")
    news1 = await news_api.get_news("AI advancements")
    if news1:
        print(news1)

    print("\n--- Second request for 'AI advancements' (should hit cache) ---")
    news2 = await news_api.get_news("AI advancements")
    if news2:
        print(news2)

    print("\n--- Request for a query with no results ---")
    news3 = await news_api.get_news("non_existent_error_topic")
    if not news3:
        print("As expected, no results were found.")


if __name__ == "__main__":
    asyncio.run(main())
