#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Project : jiqid-py
@File    : gateway.py
@Author  : guhua@jiqid.com
@Created : 2025/04/16 14:24
"""

import asyncio
import time
import traceback
import uuid
from contextlib import suppress
from dataclasses import dataclass
from typing import AsyncGenerator, Final, Optional, Union

from fastapi import WebSocket, WebSocketDisconnect

from backend.common.log import log
from backend.common.wscore.client import ClientConnection
from backend.common.wscore.coze.models import WebsocketsEvent
from backend.common.wscore.exception.errors import WebSocketErrorCode
from backend.common.wscore.pool import CapacityExceededError, ConnectionPool
from backend.database.redis import redis_client


# =========================================================
# 🔧 Connection Config
# =========================================================
@dataclass(slots=True, frozen=True)
class ConnectionConfig:
    """连接网关配置"""

    capacity: int = 1000
    heartbeat_interval: int = 30  # 秒

    def __post_init__(self):
        if self.capacity <= 0:
            raise ValueError("capacity 必须 > 0")
        if self.heartbeat_interval <= 0:
            raise ValueError("heartbeat_interval 必须 > 0")


class ConnectionGateway:
    """WebSocket连接网关（支持分布式、容错与动态伸缩）"""

    __slots__ = (
        "_config",
        "_redis",
        "_server_id",
        "_pool",
        "_loop",
        "_lock",
        "_monitor_task",
        "_consumer_task",
        "_is_running",
    )

    _DEFAULT_CONFIG: Final[ConnectionConfig] = ConnectionConfig()

    def __init__(self, config: ConnectionConfig = _DEFAULT_CONFIG):
        """初始化连接网关

        参数:
            config: 连接管理配置
        """
        self._config: Final[ConnectionConfig] = config
        self._pool: ConnectionPool = ConnectionPool(capacity=self._config.capacity)
        self._redis = redis_client
        self._server_id: Final[str] = uuid.uuid4().hex

        self._lock: Final[asyncio.Lock] = asyncio.Lock()

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._consumer_task: Optional[asyncio.Task] = None

        self._is_running: bool = False

    # -------------------------------------------------------
    # Properties
    # -------------------------------------------------------
    @property
    def loop(self):
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    @property
    def server_id(self) -> str:
        return self._server_id

    @property
    def pool(self) -> ConnectionPool:
        return self._pool

    @property
    def is_running(self) -> bool:
        return self._is_running

    # -------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------
    def start(self) -> None:
        if self._is_running:
            raise RuntimeError("连接网关已启动")

        self._is_running = True
        self._start_tasks()
        log.info(f"🚀 Gateway 启动成功 [{self._server_id}]")

    def _start_tasks(self) -> None:
        """启动后台任务（连接监控 + 事件消费）"""
        loop = self.loop
        self._monitor_task = loop.create_task(
            self._monitor_connections(), name=f"Monitor-{self._server_id}"
        )
        self._consumer_task = loop.create_task(
            self._consume_events(), name=f"Consumer-{self._server_id}"
        )

        def _handle_task_done(_task: asyncio.Task) -> None:
            if exc := _task.exception():
                log.critical(f"[{_task.get_name()}] 异常终止: {exc}")
            else:
                log.debug(f"[{_task.get_name()}] 正常退出")

        for task in (self._monitor_task, self._consumer_task):
            task.add_done_callback(_handle_task_done)

    async def shutdown(self) -> None:
        """优雅关闭（双阶段关闭）"""
        if not self._is_running:
            return

        self._is_running = False
        log.info("🛑 开始关闭 Gateway ...")
        start_time = time.monotonic()

        # 阶段1: 停止后台任务
        for task in (self._monitor_task, self._consumer_task):
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=3)

        # 阶段2: 清理连接
        await self._pool.clear()
        duration = (time.monotonic() - start_time) * 1000
        log.info(f"✅ Gateway 已关闭 (耗时: {duration:.1f}ms)")

    # -------------------------------------------------------
    # WebSocket Lifecycle
    # -------------------------------------------------------
    async def connect(self, websocket: WebSocket) -> ClientConnection:
        """接入新连接"""
        await websocket.accept()
        log.debug("WebSocket连接建立")

        try:
            uid = await self._validate_token(websocket)
            return await self._register(uid, websocket)
        except ConnectionError:
            await ClientConnection.terminate_connection(websocket, WebSocketErrorCode.INVALID_TOKEN)
            raise
        except CapacityExceededError:
            await ClientConnection.terminate_connection(websocket, WebSocketErrorCode.CONNECTION_LIMIT_EXCEEDED)
            raise
        except Exception as ex:
            await ClientConnection.terminate_connection(websocket, WebSocketErrorCode.INTERNAL_ERROR)
            log.error(f"连接失败: {ex}\n{traceback.format_exc()}")
            raise

    @staticmethod
    async def _validate_token(websocket: WebSocket) -> str:
        """验证令牌（支持测试token）"""
        token = (
                websocket.headers.get("Authorization", "")
                .replace("Bearer ", "")
                or "jiqid_test_123456"
        )
        if not token:
            raise ConnectionError("无效令牌")

        # 身份验证(三元组) TODO

        return token

    async def _register(self, uid: str, websocket: WebSocket) -> ClientConnection:
        """注册连接到池 + Redis，保证幂等与一致性"""
        try:
            # ---------- 1️⃣ 提取客户端 IP ----------
            ip_headers = websocket.headers
            ip = (
                    ip_headers.get("x-real-ip")
                    or (ip_headers.get("x-forwarded-for") or "").split(",")[0].strip()
                    or getattr(websocket.client, "host", "unknown")
            )

            # ---------- 2️⃣ 重复连接检测 ----------
            old_conn = await self._pool.get_connection(uid)
            if old_conn:
                log.warning(f"⚠️ 检测到重复连接 [UID:{uid}]，准备移除旧连接")
                await self._remove(uid)

            # ---------- 3️⃣ 注册到连接池 ----------
            conn = ClientConnection(uid, websocket)
            await conn.device_repo.set_fields(ip=ip)
            await self._pool.add_connection(conn)

            # ---------- 4️⃣ 写入 Redis ----------
            conn_key = self._key_connection(uid)
            conn_ttl = 86400  # 1天
            try:
                async with self._redis.pipeline(transaction=True) as pipe:
                    await pipe.hset(conn_key, mapping={"server": self._server_id})
                    await pipe.expire(conn_key, conn_ttl)
                await pipe.execute()
            except Exception as redis_ex:
                # Redis 操作失败要回滚连接池注册
                await self._pool.remove_connection(uid)
                log.exception(f"💥 Redis 注册失败 [UID:{uid}]，已回滚连接池: {redis_ex}")
                raise

            # ---------- 5️⃣ 初始化连接 ----------
            await conn.init()
            log.info(f"✅ 新连接注册成功 [UID:{uid}, IP:{ip}]")
            return conn

        except CapacityExceededError as cap_ex:
            log.error(f"🚫 连接池已满，拒绝新连接 [UID:{uid}]")
            raise cap_ex

        except Exception as ex:
            log.exception(f"💥 注册连接时出现异常 [UID:{uid}]: {ex}")
            # 确保清理不完整注册
            await self._safe_cleanup(uid)
            raise

    async def _safe_cleanup(self, uid: str):
        """安全清理：无论 Redis / Pool 状态如何，都尽力回收"""
        try:
            await self._pool.remove_connection(uid)
        except Exception:
            pass
        try:
            await self._redis.delete(self._key_connection(uid))
        except Exception:
            pass

    async def safe_disconnect(self, uid: str, websocket: WebSocket) -> None:
        """安全断开客户端连接并清理资源"""
        if not uid or not isinstance(uid, str):
            raise ValueError(f"无效的客户端UID: {uid}")

        await self._remove(uid, websocket)

    async def _remove(
            self, uid: str, websocket: Optional[WebSocket] = None
    ) -> None:
        """移除指定用户的WebSocket连接"""
        conn = await self.pool.get_connection(uid=uid)
        if conn is None:
            return None

        if websocket is not None and websocket != conn.websocket:
            return None

        # 1. 从连接池移除
        conn = await self.pool.remove_connection(uid)
        if conn is None:
            return None

        # 2. 确保连接关闭
        await conn.close()

        # 3. 清理Redis记录
        with suppress(Exception):
            await self._redis.delete(self._key_connection(uid))

        log.debug(f"连接已移除 [UID:{uid}]")
        return None

    async def read_text(self, uid: str) -> AsyncGenerator[str, None]:
        """持续读取客户端文本消息"""
        async for msg in self._read(uid, is_binary=False):
            yield msg

    async def read_bytes(self, uid: str) -> AsyncGenerator[bytes, None]:
        """持续读取客户端二进制消息"""
        async for msg in self._read(uid, is_binary=True):
            yield msg

    async def _read(
            self, uid: str, is_binary: bool
    ) -> AsyncGenerator[Union[str, bytes], None]:
        """内部消息读取核心实现"""
        try:
            conn = await self.get_connection(uid)
            if is_binary:
                async for msg in conn.websocket.iter_bytes():
                    yield msg
            else:
                async for msg in conn.websocket.iter_text():
                    yield msg
        except WebSocketDisconnect:
            await self._remove(uid)
            raise

    async def get_connection(self, uid: str) -> ClientConnection:
        """获取指定客户端的连接对象"""
        conn = await self._pool.get_connection(uid=uid)
        if conn is None:
            raise KeyError(f"连接不存在, [UID:{uid}]")

        return conn

    async def _monitor_connections(self) -> None:
        """持续监控连接池，执行以下操作：
        1. 清理非活跃连接(60分钟无活动)
        2. 记录连接池状态
        """
        timeout = 3600  # 1小时无活动则清理

        while self._is_running:
            try:
                await asyncio.sleep(self._config.heartbeat_interval)
                now = time.monotonic()
                inactive = [
                    conn.uid async for conn in self._pool.iter_connections()
                    if now - conn.last_activity > timeout
                ]
                if inactive:
                    await asyncio.gather(
                        *(self._remove(uid) for uid in inactive),
                        return_exceptions=True
                    )
                    log.debug(f"🧹 清理非活跃连接 {len(inactive)} 个")

                log.info(
                    f"连接池状态监控 [当前连接数：{self._pool.current_connections} "
                    f"| 历史峰值：{self._pool.max_connections} "
                    f"| 最大连接容量：{self._pool.capacity}]"
                )

            except asyncio.CancelledError:
                log.info("🛑 连接监控任务被取消，准备退出...")
                break
            except Exception as ex:
                log.exception(f"💥 _monitor_connections 异常: {ex}")
                await asyncio.sleep(5)  # 异常后短暂等待防止快速循环报错

    async def send_event(self, uid: str, event: WebsocketsEvent) -> None:
        """发送事件给指定客户端"""
        try:
            conn_key = self._key_connection(uid)
            info = await self._redis.hgetall(conn_key)
            if not info or "server" not in info:
                log.debug(f"客户端离线 [UID:{uid}]")
                return

            await self._redis.xadd(
                self._key_server(info["server"]),
                {"uid": uid, "data": event.model_dump_json()},
            )
        except Exception as ex:
            log.exception(f"💥 send_event 异常 [UID:{uid}] {ex}")
            raise

    async def _consume_events(self):
        """消费Redis流中的事件"""
        key = self._key_server(self.server_id)
        while self._is_running:
            try:
                batches = await self._redis.xread(
                    streams={key: "$"}, count=100, block=3000
                )
                if not batches:
                    continue
                tasks = [
                    self._dispatch(fields)
                    for _, msgs in batches
                    for _, fields in msgs
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                log.info("🛑 事件消费任务被取消，准备退出...")
                break
            except Exception as ex:
                log.exception(f"💥 _consume_events 异常: {ex}")
                await asyncio.sleep(2)

    async def _dispatch(self, fields: dict):
        """分发事件到客户端"""
        try:
            uid, data = fields.get("uid"), fields.get("data")
            if uid and data:
                conn = await self.get_connection(uid)
                await conn.safe_send_text(data)
        except KeyError:
            log.debug(f"跳过离线客户端 [UID:{fields.get('uid')}]")
        except Exception as ex:
            log.error(f"分发事件失败: {ex}")

    # -------------------------------------------------------
    # Redis Key Helpers
    # -------------------------------------------------------
    @staticmethod
    def _key_connection(uid: str) -> str:
        return f"ws:connection:{uid}"

    @staticmethod
    def _key_server(server_id: str) -> str:
        return f"ws:server:{server_id}"


# =========================================================
# 🌐 Global Gateway Instance
# =========================================================
connection_gateway = ConnectionGateway()
