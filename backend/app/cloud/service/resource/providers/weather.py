# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : weather.py
@Author  : OpenAI
@Date    : 2026/04/24
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from bs4 import BeautifulSoup

from backend.common.cache.local import local_cache_manager
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings

WEATHER_CACHE_PREFIX = 'weather:report'

REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
    )
}

WEATHER_CODE_MAP = {
    '100': '晴',
    '101': '多云',
    '102': '少云',
    '103': '晴间多云',
    '104': '阴',
    '150': '晴',
    '151': '多云',
    '152': '少云',
    '153': '晴间多云',
    '300': '阵雨',
    '301': '强阵雨',
    '302': '雷阵雨',
    '303': '强雷阵雨',
    '304': '雷阵雨伴有冰雹',
    '305': '小雨',
    '306': '中雨',
    '307': '大雨',
    '308': '极端降雨',
    '309': '毛毛雨/细雨',
    '310': '暴雨',
    '311': '大暴雨',
    '312': '特大暴雨',
    '313': '冻雨',
    '314': '小到中雨',
    '315': '中到大雨',
    '316': '大到暴雨',
    '317': '暴雨到大暴雨',
    '318': '大暴雨到特大暴雨',
    '350': '阵雨',
    '351': '强阵雨',
    '399': '雨',
    '400': '小雪',
    '401': '中雪',
    '402': '大雪',
    '403': '暴雪',
    '404': '雨夹雪',
    '405': '雨雪天气',
    '406': '阵雨夹雪',
    '407': '阵雪',
    '408': '小到中雪',
    '409': '中到大雪',
    '410': '大到暴雪',
    '456': '阵雨夹雪',
    '457': '阵雪',
    '499': '雪',
    '500': '薄雾',
    '501': '雾',
    '502': '霾',
    '503': '扬沙',
    '504': '浮尘',
    '507': '沙尘暴',
    '508': '强沙尘暴',
    '509': '浓雾',
    '510': '强浓雾',
    '511': '中度霾',
    '512': '重度霾',
    '513': '严重霾',
    '514': '大雾',
    '515': '特强浓雾',
    '900': '热',
    '901': '冷',
    '999': '未知',
}

INVALID_LOCATION_VALUES = {
    '未知位置',
    'unknown',
    'unknown location',
    'null',
    'none',
    'nil',
    'n/a',
    '未提供',
    '未指定',
}


@dataclass(frozen=True, slots=True)
class WeatherServiceConfig:
    api_host: str = ''
    api_key: str = ''
    default_location: str = ''
    timeout_seconds: float = 10.0


class WeatherService:
    def __init__(self) -> None:
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.WEATHER_TIMEOUT_SECONDS),
            headers=REQUEST_HEADERS,
            follow_redirects=True,
        )

    @property
    def config(self) -> WeatherServiceConfig:
        return WeatherServiceConfig(
            api_host=settings.WEATHER_API_HOST.strip(),
            api_key=settings.WEATHER_API_KEY.strip(),
            default_location=settings.WEATHER_DEFAULT_LOCATION.strip(),
            timeout_seconds=settings.WEATHER_TIMEOUT_SECONDS,
        )

    @staticmethod
    def normalize_location(location: str | None) -> str | None:
        if location is None:
            return None

        normalized = str(location).strip()
        if not normalized:
            return None
        if normalized.lower() in INVALID_LOCATION_VALUES:
            return None
        return normalized

    def resolve_location(self, *, city: str | None, ip: str | None = None) -> str:
        normalized_city = self.normalize_location(city)
        if normalized_city is not None:
            return normalized_city

        if self.normalize_location(ip) is not None:
            log.debug('weather query received ip without city, fallback to default location')

        return self.config.default_location

    @staticmethod
    def _build_cache_key(location: str) -> str:
        return f'{WEATHER_CACHE_PREFIX}:{location}'

    def _ensure_config_ready(self) -> WeatherServiceConfig:
        config = self.config
        if not config.api_key:
            raise errors.ServerError(msg='WEATHER_API_KEY is not configured')
        return config

    async def _request_json(self, url: str) -> dict[str, Any]:
        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
            raise errors.ServerError(msg='天气服务请求失败') from exc
        except httpx.HTTPStatusError as exc:
            raise errors.ServerError(msg='天气服务响应异常') from exc
        except ValueError as exc:
            raise errors.ServerError(msg='天气服务返回了无效数据') from exc

    async def _fetch_city_info(self, location: str) -> dict[str, Any]:
        config = self._ensure_config_ready()
        url = (
            f'https://{config.api_host}/geo/v2/city/lookup'
            f'?key={config.api_key}&location={location}&lang=zh'
        )
        payload = await self._request_json(url)

        code = str(payload.get('code', ''))
        if code and code != '200':
            raise errors.RequestError(msg=payload.get('message') or f'未找到相关城市：{location}')

        locations = payload.get('location') or []
        if not locations:
            raise errors.RequestError(msg=f'未找到相关城市：{location}')
        return locations[0]

    async def _fetch_weather_page(self, url: str) -> BeautifulSoup:
        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
        except httpx.RequestError as exc:
            raise errors.ServerError(msg='获取天气页面失败') from exc
        except httpx.HTTPStatusError as exc:
            raise errors.ServerError(msg='天气页面响应异常') from exc

        return BeautifulSoup(response.text, 'html.parser')

    @staticmethod
    def _parse_current_basic(soup: BeautifulSoup) -> dict[str, str]:
        current_basic: dict[str, str] = {}
        for item in soup.select('.c-city-weather-current .current-basic .current-basic___item'):
            parts = item.get_text(strip=True, separator=' ').split(' ')
            if len(parts) == 2:
                key, value = parts[1], parts[0]
                current_basic[key] = value
        return current_basic

    @staticmethod
    def _parse_weather_code(icon_src: str | None) -> str:
        if not icon_src:
            return '999'
        filename = icon_src.split('/')[-1]
        return filename.split('.')[0] if filename else '999'

    def _parse_forecast(
            self,
            soup: BeautifulSoup,
    ) -> list[dict[str, str | None]]:
        forecast_items: list[dict[str, str | None]] = []

        for row in soup.select('.city-forecast-tabs__row')[:7]:
            date_elem = row.select_one('.date-bg .date')
            if date_elem is None:
                continue

            icon_elem = row.select_one('.date-bg .icon')
            weather_code = self._parse_weather_code(icon_elem.get('src') if icon_elem else None)
            weather_text = WEATHER_CODE_MAP.get(weather_code, '未知')

            temperatures = [span.get_text(strip=True) for span in row.select('.tmp-cont .temp')]
            high_temp = temperatures[0] if len(temperatures) >= 2 else None
            low_temp = temperatures[-1] if len(temperatures) >= 2 else None

            forecast_items.append(
                {
                    'date': date_elem.get_text(strip=True),
                    'weather': weather_text,
                    'temp_max': high_temp,
                    'temp_min': low_temp,
                }
            )

        return forecast_items

    def _parse_weather_page(self, soup: BeautifulSoup) -> tuple[str, str, dict[str, str], list[dict[str, str | None]]]:
        city_elem = soup.select_one('h1.c-submenu__location')
        city_name = city_elem.get_text(strip=True) if city_elem else '未知'

        current_elem = soup.select_one('.c-city-weather-current .current-abstract')
        current_abstract = current_elem.get_text(strip=True) if current_elem else '未知'

        current_basic = self._parse_current_basic(soup)
        forecast_items = self._parse_forecast(soup)
        return city_name, current_abstract, current_basic, forecast_items

    @staticmethod
    def _build_weather_report(
            city_name: str,
            current_abstract: str,
            current_basic: dict[str, str],
            forecast_items: list[dict[str, str | None]],
    ) -> str:
        lines = [f'您查询的位置是：{city_name}', '', f'当前天气：{current_abstract}']

        if current_basic:
            lines.append('详细参数：')
            for key, value in current_basic.items():
                if value != '0':
                    lines.append(f'  · {key}: {value}')

        if forecast_items:
            lines.append('')
            lines.append('未来7天预报：')
            for item in forecast_items:
                if item['temp_min'] and item['temp_max']:
                    lines.append(
                        f"{item['date']}: {item['weather']}，气温 {item['temp_min']}~{item['temp_max']}"
                    )
                elif item['temp_max']:
                    lines.append(f"{item['date']}: {item['weather']}，气温 {item['temp_max']}")
                else:
                    lines.append(f"{item['date']}: {item['weather']}")

        lines.append('')
        lines.append('（如需某一天的具体天气，请告诉我日期）')
        return '\n'.join(lines)

    async def query(self, *, city: str | None = None, ip: str | None = None) -> dict[str, Any]:
        location = self.resolve_location(city=city, ip=ip)
        cache_key = self._build_cache_key(location)
        cached = local_cache_manager.get(cache_key)
        if cached is not None:
            return cached

        city_info = await self._fetch_city_info(location)
        fx_link = str(city_info.get('fxLink') or '').strip()
        if not fx_link:
            raise errors.ServerError(msg='天气城市信息缺少 fxLink')

        weather_page = await self._fetch_weather_page(fx_link)
        city_name, current_abstract, current_basic, forecast_items = self._parse_weather_page(weather_page)
        weather_report = self._build_weather_report(
            city_name=city_name,
            current_abstract=current_abstract,
            current_basic=current_basic,
            forecast_items=forecast_items,
        )

        data = {
            'query_location': location,
            'city_text': city_name,
            'city': city_info,
            'current': {
                'text': current_abstract,
                'basic': current_basic,
            },
            'forecast': forecast_items,
            'report': weather_report,
        }
        local_cache_manager.set(cache_key, data)
        return data

    async def aclose(self) -> None:
        await self._http_client.aclose()


weather_service = WeatherService()


async def main():
    print(await weather_service.query(city='上海'))


if __name__ == '__main__':
    asyncio.run(main())
