# -*- coding: UTF-8 -*-
"""
@Project : jiqid_dev
@File    : open_music.py
@Author  : guhua@jiqid.com
@Date    : 2025/07/03 14:54
"""
from backend.common.device.model import AudioTrack

RESOURCES = [
    {
        "id": 1,
        "title": "咚咚呛",
        "artist": "儿歌",
        "duration": "43",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234087_k45fkk.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    },
    {
        "id": 2,
        "title": "大自然的声音",
        "artist": "儿歌",
        "duration": "71",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234097_s2eey1.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    },
    {
        "id": 3,
        "title": "丢手绢",
        "artist": "儿歌",
        "duration": "58",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234104_rjtu6r.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    },
    {
        "id": 4,
        "title": "复韵母歌",
        "artist": "儿歌",
        "duration": "117",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234106_cu36z4.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    },
    {
        "id": 5,
        "title": "过新年",
        "artist": "儿歌",
        "duration": "35",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234108_swovvh.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    },
    {
        "id": 6,
        "title": "海洋",
        "artist": "儿歌",
        "duration": "90",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234110_3sb1rp.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    },
    {
        "id": 7,
        "title": "花草里真热闹",
        "artist": "儿歌",
        "duration": "117",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234115_94isfc.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    },
    {
        "id": 8,
        "title": "欢乐舞曲",
        "artist": "儿歌",
        "duration": "62",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234120_1q1txc.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    },
    {
        "id": 9,
        "title": "环保之歌",
        "artist": "儿歌",
        "duration": "67",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234121_1u954j.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    },
    {
        "id": 10,
        "title": "纸飞机",
        "artist": "儿歌",
        "duration": "45",
        "store_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689234121_pifzi1.mp3",
        "pic_url": "http://cnbj2.fds.api.xiaomi.com/res-center/audio/2023-07-13/1689233376_egawql.jpg",
    }
]

import asyncio
from typing import List
from cachetools import TTLCache


class OpenMusic:
    """ 音乐API """

    def __init__(self,
                 cache_ttl: int = 86400,
                 max_cache_size: int = 1000):
        # 使用LRU缓存+TTL
        self._cache = TTLCache(
            maxsize=max_cache_size,
            ttl=cache_ttl
        )
        self._lock = asyncio.Lock()  # 防止缓存击穿

    async def get_songs(self, query: str) -> List[AudioTrack]:
        """带缓存的音频数据获取"""
        return await self._get_songs(query=query)

    async def _get_songs(self, query: str):
        """ 数据库查询音频资源 """
        return [
            AudioTrack(
                song_id=item["id"],
                album_id=0,
                singer_id=0,
                song_name=item["title"],
                album_name="",
                duration=item["duration"],
                store_url=item["store_url"],
                cover_url=item["pic_url"]
            ) for item in RESOURCES
        ]


open_music = OpenMusic()
