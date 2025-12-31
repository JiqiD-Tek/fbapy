# -*- coding: UTF-8 -*-
"""
@Project : jiqid_dev
@File    : amap_client.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/23 15:30
"""
import asyncio
from typing import Tuple
from cachetools import TTLCache

from backend.common.log import log
from backend.common.http_client import HTTPClient
from backend.common.openapi.amap.models import city_mapping


class AMapClient:

    def __init__(self,
                 api_key: str = 'f8467ff040f77ebe50456656ff718633',
                 cache_ttl: int = 86400,
                 max_cache_size: int = 1000):
        """
        :param api_key: 高德地图API Key
        :param cache_ttl: 缓存过期时间(秒)，默认1天
        :param max_cache_size: 最大缓存条目数
        """
        self.host = 'https://restapi.amap.com'
        self.key = api_key
        self.city_map = city_mapping.mappings

        self._http_client = HTTPClient(
            timeout=10.0,  # 10秒超时
            read=10.0,
            write=5.0
        )

        # 使用组合缓存策略
        self._cache = {
            'ip': TTLCache(maxsize=max_cache_size, ttl=cache_ttl),
            'weather': TTLCache(maxsize=max_cache_size * 2, ttl=cache_ttl // 2)
        }
        self._lock = asyncio.Lock()

    async def get_location_by_ip(self, ip: str) -> dict:
        """
        通过IP获取地理位置信息（带缓存）

        :param ip: 要查询的IP地址
        """
        if not ip:
            raise ValueError("IP地址不能为空")

        # 检查缓存
        if ip in self._cache['ip']:
            log.debug(f"IP定位缓存命中: {ip}")
            return self._cache['ip'][ip]

        async with self._lock:  # 防止缓存击穿
            if ip in self._cache['ip']:  # 双重检查
                return self._cache['ip'][ip]

            try:
                response = await self._fetch_location(ip)
                self._cache['ip'][ip] = response
                return response
            except Exception as e:
                log.error(f"IP定位失败: ip={ip}, 错误: {str(e)}")
                raise ValueError(f"定位失败: {str(e)}")

    async def _fetch_location(self, ip: str) -> dict:
        """实际调用高德API"""
        url = f"{self.host}/v3/ip"
        params = {'ip': ip, 'key': self.key}

        resp = await self._http_client.get(url, params=params)
        data = resp.json()

        if data.get("status") != "1":
            raise ValueError(data.get("message", "未知错误"))

        return data

    async def get_weather_info(self, query):
        if not query:
            raise ValueError("city不能为空")

        # 标准化城市信息
        adcode, name = self._normalize_city(query)

        # 检查缓存（支持编码和名称双键缓存）
        cache_key = f"{adcode}:{name}"
        if cache_key in self._cache['weather']:
            log.debug(f"天气缓存命中: {cache_key}")
            return self._cache['weather'][cache_key]

        async with self._lock:
            if cache_key in self._cache['weather']:
                return self._cache['weather'][cache_key]

            try:
                response = await self._get_weather_info(adcode)
                # 双键缓存
                self._cache['weather'][f"{adcode}:{name}"] = response
                return response
            except Exception as e:
                log.error(f"天气查询失败: adcode={adcode}, name={name}, 错误: {str(e)}")
                raise ValueError(f"天气查询失败: {str(e)}")

    async def _get_weather_info(self, adcode) -> dict:
        url = f"{self.host}/v3/weather/weatherInfo"
        params = {'city': adcode, 'key': self.key, 'extensions': 'all'}

        resp = await self._http_client.get(url, params=params)
        data = resp.json()

        if data.get("status") != "1":
            raise ValueError(data.get("message", "未知错误"))

        return data

    def _normalize_city(self, city: str) -> Tuple[str, str]:
        """标准化城市输入"""
        # 1. 检查编码映射
        if city in self.city_map['by_code']:
            item = self.city_map['by_code'][city]
            return item['adcode'], item['name']

        # 2. 检查名称映射
        if city in self.city_map['by_name']:
            item = self.city_map['by_name'][city]
            return item['adcode'], item['name']

        # 3. 模糊匹配（如输入"北京"可匹配"北京市"）
        for name, item in self.city_map['by_name'].items():
            if city in name:
                return item['adcode'], item['name']

        raise ValueError(f"未知城市: {city}")


amap_client = AMapClient()
