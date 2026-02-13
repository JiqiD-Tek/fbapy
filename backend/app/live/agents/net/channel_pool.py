#!/usr/bin/env python
"""
@Project : jiqid-py
@File    : channel_pool.py
@Author  : guhua@jiqid.com
@Created : 2025/04/16 14:24
"""

import asyncio
import time
import traceback
import uuid

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import suppress
from typing import Final

from fastapi import WebSocket, WebSocketDisconnect
from jose import jwt

from backend.app.live.agents.net.channel import Channel
from backend.app.live.agents.net.coze.models import WebsocketsEvent
from backend.app.live.agents.net.exception.errors import WebSocketErrorCode
from backend.common.log import log
from backend.core.conf import settings
from backend.database.redis import redis_client


class CapacityExceededError(Exception):
    """连接池容量已达上限"""

    def __init__(self, capacity: int) -> None:
        super().__init__(f'已达到最大连接数限制: {capacity}')
        self.capacity = capacity


class ChannelPool:
    """WebSocket连接网关"""

    def __init__(self, capacity: int = 100) -> None:
        """初始化连接网关"""
        self._capacity: Final[int] = capacity
        self._redis = redis_client
        self._server_id: Final[str] = uuid.uuid4().hex

        # channel_id -> Channel
        self._channels: dict[str, Channel] = {}

        self._lock: Final[asyncio.Lock] = asyncio.Lock()

        # 后台任务
        self._monitor_task: asyncio.Task | None = None
        self._consumer_task: asyncio.Task | None = None

        self._is_closed: bool = True

    def start(self) -> None:
        if not self._is_closed:
            raise RuntimeError('连接网关已启动')

        self._is_closed = False
        self._start_tasks()
        log.info(f'🚀 Gateway 启动成功 [{self._server_id}]')

    def _start_tasks(self) -> None:
        """启动后台任务（连接监控 + 事件消费）"""
        self._monitor_task = asyncio.create_task(self._monitor_channels(), name=f'Monitor-{self._server_id}')
        self._consumer_task = asyncio.create_task(self._consume_events(), name=f'Consumer-{self._server_id}')

        def _handle_task_done(_task: asyncio.Task) -> None:
            if exc := _task.exception():
                log.critical(f'[{_task.get_name()}] 异常终止: {exc}')
            else:
                log.debug(f'[{_task.get_name()}] 正常退出')

        for task in (self._monitor_task, self._consumer_task):
            task.add_done_callback(_handle_task_done)

    async def shutdown(self) -> None:
        """优雅关闭（双阶段关闭）"""
        if self._is_closed:
            return

        self._is_closed = True
        log.info('🛑 开始关闭 Gateway ...')
        start_time = time.monotonic()

        # 阶段1: 停止后台任务
        for task in (self._monitor_task, self._consumer_task):
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=3)

        # 阶段2: 清理连接
        await self.clear()
        duration = (time.monotonic() - start_time) * 1000
        log.info(f'✅ Gateway 已关闭 (耗时: {duration:.1f}ms)')

    async def connect(self, websocket: WebSocket) -> Channel:
        """接入新连接"""
        await websocket.accept()
        log.debug('WebSocket连接建立')

        try:
            uid = await self._validate_token(websocket, is_open=False)
            return await self._register(uid, websocket)
        except ConnectionError:
            await Channel.terminate_connection(websocket, WebSocketErrorCode.INVALID_TOKEN)
            raise
        except CapacityExceededError:
            await Channel.terminate_connection(websocket, WebSocketErrorCode.CONNECTION_LIMIT_EXCEEDED)
            raise
        except Exception as ex:
            await Channel.terminate_connection(websocket, WebSocketErrorCode.INTERNAL_ERROR)
            log.error(f'连接失败: {ex}\n{traceback.format_exc()}')
            raise

    @staticmethod
    async def _validate_token(websocket: WebSocket, is_open: bool = False) -> str:
        """验证令牌"""
        if not is_open:
            return uuid.uuid4().hex

        token = websocket.headers.get('Authorization', '').replace('Bearer', '').strip()
        if not token:
            raise ConnectionError('无效令牌')

        payload = jwt.decode(
            token,
            settings.TOKEN_SECRET_KEY,
            algorithms=[settings.TOKEN_ALGORITHM],
            options={'verify_exp': True},
        )
        mac = payload.get('mac')
        did = payload.get('did')
        ttl = payload.get('ttl')
        if not mac or not did or not ttl:
            raise ConnectionError('无效令牌')

        return did  # 设备DID

    async def _register(self, uid: str, websocket: WebSocket) -> Channel:
        """注册连接到池 + Redis，保证幂等与一致性"""
        try:
            # ---------- 提取通道 IP ----------
            ip_headers = websocket.headers
            ip = (
                ip_headers.get('x-real-ip')
                or (ip_headers.get('x-forwarded-for') or '').split(',')[0].strip()
                or getattr(websocket.client, 'host', 'unknown')
            )

            # ---------- 重复连接检测 ----------
            old_channel = await self.get_channel(uid)
            if old_channel:
                log.warning(f'⚠️ 检测到重复连接 [UID:{uid}]，准备移除旧连接')
                await self._remove(uid)

            # ---------- 注册到连接池 ----------
            channel = Channel(uid, websocket)
            await self.add_channel(channel)
            log.info(f'✅ 新连接注册成功 [UID:{uid}, IP:{ip}]')

            # ---------- 写入 Redis ----------
            channel_key = self._key_channel(uid)
            try:
                async with self._redis.pipeline(transaction=True) as pipe:
                    await pipe.hset(channel_key, mapping={'server': self._server_id})
                    await pipe.expire(channel_key, 86400)
                await pipe.execute()
            except Exception as redis_ex:
                await self.remove_channel(uid)  # Redis 操作失败要回滚连接池注册
                log.exception(f'💥 Redis 注册失败 [UID:{uid}]，已回滚连接池: {redis_ex}')
                raise

            return channel

        except CapacityExceededError:
            log.error(f'🚫 连接池已满，拒绝新连接 [UID:{uid}]')
            raise

        except Exception as ex:
            log.exception(f'💥 注册连接时出现异常 [UID:{uid}]: {ex}')
            # 确保清理不完整注册
            await self._safe_cleanup(uid)
            raise

    async def _safe_cleanup(self, uid: str) -> None:
        """安全清理：无论 Redis / Pool 状态如何，都尽力回收"""
        try:
            await self.remove_channel(uid)
        except Exception as ex:
            log.warning(f'💥 释放连接时出现异常 [UID:{uid}]: {ex}')
        try:
            await self._redis.delete(self._key_channel(uid))
        except Exception as ex:
            log.warning(f'💥 释放连接时出现异常 [UID:{uid}]: {ex}')

    async def safe_disconnect(self, uid: str, websocket: WebSocket) -> None:
        """安全断开通道连接并清理资源"""
        if not uid or not isinstance(uid, str):
            raise ValueError(f'无效的通道UID: {uid}')

        await self._remove(uid, websocket)

    async def _remove(self, uid: str, websocket: WebSocket | None = None) -> None:
        """移除指定用户的WebSocket连接"""
        channel = await self.get_channel(uid=uid)
        if channel is None:
            return

        if websocket is not None and websocket != channel.websocket:
            return

        # 1. 从连接池移除
        channel = await self.remove_channel(uid)
        if channel is None:
            return

        # 2. 确保连接关闭
        await channel.aclose()

        # 3. 清理Redis记录
        with suppress(Exception):
            await self._redis.delete(self._key_channel(uid))

        log.debug(f'连接已移除 [UID:{uid}]')
        return

    async def read_text(self, uid: str) -> AsyncGenerator[str, None]:
        """持续读取通道文本消息"""
        async for msg in self._read(uid, is_binary=False):
            yield msg

    async def read_bytes(self, uid: str) -> AsyncGenerator[bytes, None]:
        """持续读取通道二进制消息"""
        async for msg in self._read(uid, is_binary=True):
            yield msg

    async def _read(self, uid: str, is_binary: bool) -> AsyncGenerator[str | bytes, None]:
        """内部消息读取核心实现"""
        try:
            channel = await self.get_channel(uid)
            if is_binary:
                async for msg in channel.websocket.iter_bytes():
                    yield msg
            else:
                async for msg in channel.websocket.iter_text():
                    yield msg
        except WebSocketDisconnect:
            await self._remove(uid)
            raise

    async def _monitor_channels(self) -> None:
        """持续监控连接池，执行以下操作：
        1. 清理非活跃连接(60分钟无活动)
        2. 记录连接池状态
        """
        while not self._is_closed:
            try:
                await asyncio.sleep(30)
                now = time.monotonic()
                inactive = [
                    conn.uid async for conn in self.iter_channels() if now - conn.last_activity > 3600
                ]  # 1小时无活动则清理
                if inactive:
                    await asyncio.gather(*(self._remove(uid) for uid in inactive), return_exceptions=True)
                    log.debug(f'🧹 清理非活跃连接 {len(inactive)} 个')

                log.info(f'连接池状态监控 [当前连接数：{self.current_channels} | 最大连接容量：{self._capacity}]')

            except asyncio.CancelledError:
                log.info('🛑 连接监控任务被取消，准备退出...')
                break
            except Exception as ex:
                log.exception(f'💥 _monitor_channels 异常: {ex}')
                await asyncio.sleep(5)  # 异常后短暂等待防止快速循环报错

    async def send_event(self, uid: str, event: WebsocketsEvent) -> None:
        """发送事件给指定通道"""
        try:
            channel_key = self._key_channel(uid)
            info = await self._redis.hgetall(channel_key)
            if not info or 'server' not in info:
                log.debug(f'通道断开 [UID:{uid}]')
                return

            await self._redis.xadd(
                self._key_server(info['server']),
                {'uid': uid, 'data': event.model_dump_json()},
            )
        except Exception as ex:
            log.exception(f'💥 send_event 异常 [UID:{uid}] {ex}')
            raise

    async def _consume_events(self) -> None:
        """消费Redis流中的事件"""
        key = self._key_server(self._server_id)
        while not self._is_closed:
            try:
                batches = await self._redis.xread(streams={key: '$'}, count=100, block=3000)
                if not batches:
                    continue
                tasks = [self._dispatch(fields) for _, msgs in batches for _, fields in msgs]
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                log.info('🛑 事件消费任务被取消，准备退出...')
                break
            except Exception as ex:
                log.exception(f'💥 _consume_events 异常: {ex}')
                await asyncio.sleep(2)

    async def _dispatch(self, fields: dict) -> None:
        """分发事件到通道"""
        try:
            uid, data = fields.get('uid'), fields.get('data')
            if uid and data:
                conn = await self.get_channel(uid)
                await conn.safe_send_text(data)
        except KeyError:
            log.debug(f'跳过断开通道 [UID:{fields.get("uid")}]')
        except Exception as ex:
            log.error(f'分发事件失败: {ex}')

    # -------------------------------------------------------------------------
    # channel 管理
    # -------------------------------------------------------------------------
    @property
    def current_channels(self) -> int:
        """当前连接数量"""
        return len(self._channels)

    async def add_channel(self, client_connection: Channel) -> None:
        """添加连接"""
        async with self._lock:
            uid = client_connection.uid
            if uid in self._channels:
                raise KeyError(f'连接已存在 [UID:{uid}]')

            if len(self._channels) >= self._capacity:
                raise CapacityExceededError(self._capacity)

            self._channels[uid] = client_connection
            log.debug(f'[{uid}] 已添加，当前连接数: {len(self._channels)}')

    async def remove_channel(self, uid: str) -> Channel | None:
        """移除连接"""
        if not uid or not isinstance(uid, str):
            raise ValueError('UID 必须是非空字符串')

        async with self._lock:
            conn = self._channels.pop(uid, None)
            log.debug(f'[{uid}] 已移除，当前连接数: {len(self._channels)}')
            return conn

    async def get_channel(self, uid: str) -> Channel | None:
        """快速获取连接（无锁读取）"""
        if not uid or not isinstance(uid, str):
            raise ValueError('UID 必须是非空字符串')
        return self._channels.get(uid)

    async def iter_channels(self) -> AsyncIterator[Channel]:
        """安全迭代所有活跃连接"""
        async with self._lock:
            connections = list(self._channels.values())

        for conn in connections:
            yield conn

    async def clear(self) -> None:
        """关闭并清空所有连接"""
        async with self._lock:
            connections = list(self._channels.values())
            self._channels.clear()

        for conn in connections:
            try:
                await conn.aclose()
            except Exception as ex:
                log.warning(f'关闭连接失败 [UID:{conn.uid}] - {ex}')

        log.debug('所有连接已清空')

    # -------------------------------------------------------
    # Redis Key
    # -------------------------------------------------------
    @staticmethod
    def _key_channel(uid: str) -> str:
        return f'ws:channel:{uid}'

    @staticmethod
    def _key_server(server_id: str) -> str:
        return f'ws:server:{server_id}'


channel_pool = ChannelPool()
