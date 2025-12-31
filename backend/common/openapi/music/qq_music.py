# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : tencent.py
@Author  : guhua@jiqid.com
@Date    : 2025/07/14 16:50
"""
import json
import time
import hashlib
import asyncio

from typing import List, Optional
from cachetools import TTLCache

from backend.common.device.model import AudioTrack
from backend.common.log import log
from backend.common.http_client import HTTPClient
from backend.core.conf import settings
from backend.database.redis import redis_client


class AuthorizedError(Exception):
    """权限"""

    def __init__(self, message: str = "未授权"):
        super().__init__(message)


class QQMusic:

    def __init__(
            self,
            base_url="",
            appid="",
            appkey="",
            language="",
            cache_ttl: int = 86400,
            max_cache_size: int = 1000,
    ):
        self.base_url = base_url
        self.app_id = appid
        self.app_key = appkey
        self.language = language
        self.callback_url = f"http://{language[:2]}.api.jiqid.net/api/v1/external/tencent/qq_music_callback"

        self._http_client = HTTPClient(
            timeout=10.0,  # 10秒超时
            read=10.0,
            write=5.0
        )
        self.redis_client = redis_client

        # 使用LRU缓存+TTL
        self._cache = {
            'singer': TTLCache(maxsize=max_cache_size, ttl=cache_ttl),
            'song': TTLCache(maxsize=max_cache_size, ttl=cache_ttl),
        }
        self._lock = asyncio.Lock()  # 防止缓存击穿

    async def async_set_cache(self, key: str, value: dict, prefix: str = 'qq_music_token:') -> None:
        await self.redis_client.set(f'{prefix}{key}', json.dumps(value), ex=86400 * 30)

    async def async_get_cache(self, key: str, prefix: str = 'qq_music_token:') -> Optional[dict]:
        value = await self.redis_client.get(f'{prefix}{key}')
        if value:
            return json.loads(value)
        return None

    async def get_singer_songs(
            self, query: str,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"
    ) -> List[AudioTrack]:
        """音频数据获取"""
        if query in self._cache["singer"]:
            log.debug(f"命中缓存: {query}")
            return self._cache["singer"][query]

        # 加锁防止重复请求
        async with self._lock:
            # 双重检查锁模式
            if query in self._cache["singer"]:
                return self._cache["singer"][query]

            try:
                data = await self._get_singer_songs(query, device_id=device_id, client_ip=client_ip)
                self._cache["singer"][query] = data
                return data

            except Exception as e:
                log.error(f"无法获取歌曲: {query}, 错误: {e}", exc_info=True)
                raise ValueError(f"无法获取歌曲: {e}")

    async def _get_singer_songs(
            self, query: str,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"
    ) -> List[AudioTrack]:
        """音频数据获取"""
        resp = await self.query_singer_list(query=query, device_id=device_id, client_ip=client_ip)
        if not resp["singer_list"]:
            return []

        resp = await self.get_singer_info(
            singer_id=resp["singer_list"][0]["singer_id"], device_id=device_id, client_ip=client_ip)
        return [
            AudioTrack(
                song_id=item["song_id"],
                album_id=item["album_id"],
                singer_id=item["singer_id"],
                song_name=item["song_title"],
                album_name=item["album_name"],
                duration=item["song_play_time"],
                store_url=item["song_play_url"],
                cover_url=item["album_pic"]
            ) for item in resp["songlist"] if item["unplayable_code"] == 0
        ]

    async def get_songs(
            self, query: str,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"
    ) -> List[AudioTrack]:
        """音频数据获取"""
        if query in self._cache["song"]:
            log.debug(f"命中缓存: {query}")
            return self._cache["song"][query]

        # 加锁防止重复请求
        async with self._lock:
            # 双重检查锁模式
            if query in self._cache["song"]:
                return self._cache["song"][query]

            try:
                data = await self._get_songs(query, device_id=device_id, client_ip=client_ip)
                self._cache["song"][query] = data
                return data

            except Exception as e:
                log.error(f"无法获取歌曲: {query}, 错误: {e}", exc_info=True)
                raise ValueError(f"无法获取歌曲: {e}")

    async def _get_songs(
            self, query: str,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"
    ) -> List[AudioTrack]:
        """音频数据获取"""
        resp = await self.custom_search(query=query, device_id=device_id, client_ip=client_ip)
        return [
            AudioTrack(
                song_id=item["song_id"],
                album_id=item["album_id"],
                singer_id=item["singer_id"],
                song_name=item["song_title"],
                album_name=item["album_name"],
                duration=item["song_play_time"],
                store_url=item["song_play_url"],
                cover_url=item["album_pic"]
            ) for item in resp["list"] if item["unplayable_code"] == 0
        ]

    async def login_by_qr_code(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"
    ) -> str:
        qr_code_resp = await self.get_qr_code(device_id=device_id, client_ip=client_ip)
        return qr_code_resp['auth_code']

    async def auth_login(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218", code: str = ""
    ) -> None:
        """执行授权登录流程  """
        try:
            # 1. 获取access token
            access_token_resp = await self._get_accesstoken(
                device_id=device_id, client_ip=client_ip, code=code
            )

            if not access_token_resp or "encryptString" not in access_token_resp:
                raise ValueError("无效的access token响应")

            # 2. 解析encrypt数据
            try:
                encrypt = json.loads(access_token_resp["encryptString"])
                required_fields = [
                    "qqmusic_open_id",
                    "qqmusic_access_token",
                    "expireTime",
                    "qqmusic_refresh_token",
                    "refresh_token_expireTime",
                ]
                if not all(field in encrypt for field in required_fields):
                    raise ValueError("encryptString缺少必要字段")
            except json.JSONDecodeError:
                raise ValueError("encryptString JSON解析失败")

            # 3. 创建设备token
            token_info = await self.create_device_token(
                device_id=device_id, client_ip=client_ip
            )
            if not token_info or "opi_device_id" not in token_info or "opi_device_key" not in token_info:
                raise ValueError("无效的设备token响应")

            # 4. 缓存token信息
            key = self._create_key(device_id, client_ip)
            value = {
                "opi_device_id": token_info["opi_device_id"],
                "opi_device_key": token_info["opi_device_key"],
                "qqmusic_open_id": encrypt["qqmusic_open_id"],
                "qqmusic_access_token": encrypt["qqmusic_access_token"],
                "expire_time": encrypt["expireTime"],
                "qqmusic_refresh_token": encrypt["qqmusic_refresh_token"],
                "refresh_token_expire_time": encrypt["refresh_token_expireTime"],
            }
            await self.async_set_cache(key=key, value=value)

            log.info(f"授权登录成功 | 设备ID: {device_id} | IP: {client_ip}")
        except ValueError as e:
            log.error(f"授权登录验证失败: {e}")
            raise
        except Exception as e:
            log.error(f"授权登录异常: {e}")
            raise

    async def create_device_token(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"
    ) -> dict:
        """ 设备票据 """
        params = {
            "opi_cmd": "CreateDeviceToken",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
        }
        resp = await self._http_get(params=params)
        return resp["token_info"]

    async def get_qr_code(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"
    ) -> dict:
        """ 二维码登录 """
        params = {
            "opi_cmd": "fcg_music_custom_sdk_get_qr_code.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "qqmusic_qrcode_type": "universal",
            "qqmusic_encrypt_auth": json.dumps({
                "response_type": "code",
                "state": device_id,
                "callbackUrl": self.callback_url,
            })
        }
        resp = await self._http_get(params=params)
        return resp

    async def _qrcode_auth_poll(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218", auth_code: str = ""
    ) -> dict:
        params = {
            "opi_cmd": "fcg_music_custom_qrcode_auth_poll.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "qqmusic_openid_authCode": auth_code,
        }
        resp = await self._http_get(params=params)
        return resp

    async def login_by_mini(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218", callback_url: str = "",
    ) -> dict:
        """ 拉起微信小程序登录 """
        params = {
            "opi_cmd": "fcg_music_custom_applet_path.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "encryptString": json.dumps({
                "response_type": "code",
                "state": device_id,
            }),
        }
        resp = await self._http_get(params=params)
        return resp

    async def login_by_h5(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218", callback_url: str = "",
    ) -> dict:
        """ h5授权登录 """
        params = {
            "opi_cmd": "fcg_music_custom_h5_login_path.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "encryptString": json.dumps({
                "response_type": "code",
                "state": device_id,
            }),
            "callbackUrl": callback_url or self.callback_url,
            "needNotifyErr": 1,
            "changeLogin": 0,
        }
        resp = await self._http_get(params=params)
        return resp

    async def _get_accesstoken(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218", code: str = "",
    ) -> dict:
        """ 获取访问令牌 """
        params = {
            "opi_cmd": "fcg_music_oauth_get_accesstoken.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "cmd": "getToken",
            "code": code,
        }
        resp = await self._http_get(params=params)
        return resp

    async def _get_refreshtoken(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218", refresh_token: str = ""
    ) -> dict:
        """ 刷新访问令牌 """
        params = {
            "opi_cmd": "fcg_music_oauth_get_accesstoken.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "cmd": "refreshToken",
            "qqmusic_refresh_token": refresh_token,
        }
        resp = await self._http_get(params=params)
        return resp

    async def get_account_info(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        params = {
            "opi_cmd": "fcg_music_custom_get_account_info.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def custom_search(
            self, query: str, page_now: int = 1, page_size: int = 10,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"
    ) -> dict:
        """ 根据输入的关键字搜索歌曲、专辑、mv、歌单、电台 """
        params = {
            "opi_cmd": "fcg_music_custom_search.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "w": query,
            "p": page_now,
            "num": page_size,
            "t": 0,  # 搜索类型 0：单曲搜索 8：专辑搜索 15：电台
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def songlist_search(
            self, query: str, page_now: int = 1, page_size: int = 10,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 根据关键词搜索歌单 """
        params = {
            "opi_cmd": "fcg_songlist_search.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "w": query,
            "p": page_now,
            "n": page_size,
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def query_singer_list(
            self, query: str, page_now: int = 1, page_size: int = 10,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 搜索歌手列表 """
        params = {
            "opi_cmd": "fcg_music_custom_query_singer_list.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "query": query,
            "page": page_now,
            "page_size": page_size,
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def get_song_info_batch(
            self, song_id: list,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 批量获取歌曲信息 """
        params = {
            "opi_cmd": "fcg_music_custom_get_song_info_batch.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "song_id": ','.join([str(i) for i in song_id]),
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def get_lyric(
            self, song_id: int = 0,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 通过歌曲id，获取歌曲的歌词 """
        params = {
            "opi_cmd": "fcg_music_custom_get_lyric.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "song_id": song_id,
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def get_album_detail(
            self, album_id: int, page_now: int = 1, page_size: int = 10,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 获取专辑详情 """
        params = {
            "opi_cmd": "fcg_music_custom_get_album_detail.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "album_id": album_id,
            "page": page_now,
            "size": page_size,
            "fav_state": 0,  # 是否需要获取用户已收藏状态（需要登录态有效）
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def get_singer_album(
            self, singer_id: int = 0, page_now: int = 1, page_size: int = 10,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 获取歌手专辑列表信息 """
        params = {
            "opi_cmd": "fcg_music_custom_get_singer_album.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "singer_id": singer_id,
            "page_index": page_now,
            "num_per_page": page_size,
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def get_singer_info(
            self, singer_id: int = 0, page_now: int = 1, page_size: int = 10,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 通过歌手id，获取歌手下的歌曲信息，可分页拉取 """
        params = {
            "opi_cmd": "fcg_music_custom_get_singer_info.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "singer_id": singer_id,
            "page_index": page_now,
            "num_per_page": page_size,
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def get_similar_song(
            self, song_id: int = 0,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 相似单曲推荐 """
        params = {
            "opi_cmd": "fcg_music_custom_get_similar_song.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "song_id": song_id,
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def get_play_recently(
            self, type_id: int = 0, update_time: int = 0,
            device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 获取最近播放 """
        params = {
            "opi_cmd": "fcg_music_custom_get_play_recently.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            "type": type_id,  # 1：全部，2：歌曲，3：专辑，4：歌单，12：长音频， 14：播客
            "updateTime": update_time,  # 最近更新时间，由接口下发（见返回数据），客户端传入以减少返回数据量，初始可传0
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def get_songlist_self(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218",
    ) -> dict:
        """ 获取个人歌单目录 """
        params = {
            "opi_cmd": "fcg_music_custom_get_songlist_self.fcg",
            "app_id": self.app_id,
            "timestamp": f"{int(time.time())}",
            "device_id": device_id,
            "client_ip": client_ip,
            **await self._get_auth_params(device_id, client_ip),
        }
        resp = await self._http_get(params=params)
        return resp

    async def _http_get(self, params: dict) -> dict:
        """执行HTTP GET请求 """
        # 1. 参数验证
        if not params or "opi_cmd" not in params:
            raise ValueError("请求参数必须包含opi_cmd字段")

        try:
            # 2. 生成签名并发送请求
            params["sign"] = self._generate_sign(params)
            log.debug(f"发送请求: cmd={params['opi_cmd']}, params={params}")

            # 3. 执行HTTP请求
            rv = await self._http_client.get(
                self.base_url, params=params,
            )
            # 4. 解析响应
            resp = rv.json()
            log.debug(f"请求成功: cmd={params['opi_cmd']}, resp={resp}")

            # 5. 检查业务状态码
            if resp.get("ret") != 0:
                error_msg = resp.get("msg", "未知错误")
                log.error(f"业务逻辑错误: cmd={params['opi_cmd']}, msg={error_msg}")
                raise Exception(f"{params['opi_cmd']}请求失败: {error_msg}")

            return resp

        except Exception as e:
            log.error(f"请求处理异常: cmd={params['opi_cmd']}, error={e}")
            raise

    async def _get_auth_params(
            self, device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"
    ) -> dict:
        """ 获取登录参数 """
        is_auth = await self._is_authorized(device_id, client_ip)
        if not is_auth:
            raise AuthorizedError()

        key = self._create_key(device_id, client_ip)
        value = await self.async_get_cache(key=key)

        return {
            "login_type": 5,
            "device_login_type": 4,
            "user_login_type": 6,

            "opi_device_id": value["opi_device_id"],
            "opi_device_key": value["opi_device_key"],
            "qqmusic_open_id": value["qqmusic_open_id"],
            "qqmusic_access_token": value["qqmusic_access_token"],
        }

    async def _is_authorized(
            self,
            device_id: str = "jiqid000000001",
            client_ip: str = "221.226.35.218"
    ) -> bool:
        """验证并刷新授权状态 """
        key = self._create_key(device_id, client_ip)
        value = await self.async_get_cache(key=key)

        # 1. 检查缓存是否存在
        if value is None:
            log.debug(f"未找到授权缓存: device_id={device_id}, ip={client_ip}")
            return False

        current_time = time.time()

        # 2. 检查refresh_token是否即将过期
        if int(value["refresh_token_expire_time"]) <= current_time + 86400:  # 提前1天刷新
            log.debug(f"Refresh token即将过期: device_id={device_id}")
            return False

        try:
            # 3. 检查access_token是否即将过期
            if int(value["expire_time"]) <= current_time + 3600:  # 提前1小时刷新
                log.debug(f"Access token即将过期，尝试刷新: device_id={device_id}")

                # 4. 刷新token
                access_token_resp = await self._get_refreshtoken(
                    device_id=device_id, client_ip=client_ip,
                    refresh_token=value["qqmusic_refresh_token"]
                )

                # 5. 解析并更新token数据
                encrypt = json.loads(access_token_resp["encryptString"])
                required_fields = [
                    "qqmusic_open_id",
                    "qqmusic_access_token",
                    "expireTime",
                    "qqmusic_refresh_token",
                    "refresh_token_expireTime"
                ]

                if not all(field in encrypt for field in required_fields):
                    log.error("刷新token响应缺少必要字段")
                    return False

                value.update({
                    "qqmusic_open_id": encrypt["qqmusic_open_id"],
                    "qqmusic_access_token": encrypt["qqmusic_access_token"],
                    "expire_time": encrypt["expireTime"],
                    "qqmusic_refresh_token": encrypt["qqmusic_refresh_token"],
                    "refresh_token_expire_time": encrypt["refresh_token_expireTime"],
                })

                await self.async_set_cache(key=key, value=value)
                log.info(f"Token刷新成功: device_id={device_id}")

        except json.JSONDecodeError:
            log.error("刷新token响应JSON解析失败")
            return False
        except KeyError as e:
            log.error(f"刷新token响应字段缺失: {e}")
            return False
        except Exception as e:
            log.error(f"刷新token失败: {e}")
            return False

        return True

    @staticmethod
    def _create_key(device_id: str = "jiqid000000001", client_ip: str = "221.226.35.218"):
        return f"{device_id}:{client_ip}"

    def _generate_sign(self, params: dict) -> str:
        """ 生成请求签名(sign) """
        # 1. 过滤掉None值和sign字段本身
        filtered_params = {k: v for k, v in params.items() if v is not None and k != 'sign'}

        # 2. 按键名ASCII字母升序排序
        sorted_params = sorted(filtered_params.items(), key=lambda x: x[0])

        # 3. 拼接键值对 key=value
        param_str = '&'.join([f"{k}={v}" for k, v in sorted_params])

        # 4. 追加_app_key
        sign_str = f"{param_str}_{self.app_key}"

        # 5. 计算MD5(32位小写)
        md5 = hashlib.md5()
        md5.update(sign_str.encode('utf-8'))

        return md5.hexdigest().lower()


qq_music = None
