#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : pool.py
# @Created   : 2025/4/16 14:29

import asyncio
from threading import Lock
from weakref import WeakValueDictionary
from typing import Optional, AsyncIterator, Final

from backend.common.log import log
from backend.common.wscore.client import ClientConnection


class CapacityExceededError(Exception):
    """连接池容量已达上限"""

    def __init__(self, capacity: int):
        super().__init__(f"已达到最大连接数限制: {capacity}")
        self.capacity = capacity


class ConnectionPool:
    """线程安全的异步连接池（单例）

    特性：
    - 异步 + 线程安全
    - 弱引用自动回收
    - 并发容量控制
    - 历史峰值统计
    """

    _instance: Optional["ConnectionPool"] = None
    _instance_lock: Final[Lock] = Lock()  # Thread-safe singleton lock

    __slots__ = (
        "_connection_map",
        "_async_lock",
        "_capacity",
        "_max_connections",
        "_current_connections",
        "_initialized",
    )

    def __new__(cls, capacity: int = 1000) -> "ConnectionPool":
        """线程安全单例模式"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, capacity: int = 1000):
        if getattr(self, "_initialized", False):
            return  # 防止重复初始化

        if capacity <= 0:
            raise ValueError("最大连接数限制必须为正整数")

        self._capacity: Final[int] = capacity
        self._async_lock: Final[asyncio.Lock] = asyncio.Lock()
        self._connection_map: WeakValueDictionary[str, ClientConnection] = WeakValueDictionary()
        self._max_connections: int = 0
        self._current_connections: int = 0
        self._initialized = True

        log.info(f"ConnectionPool 初始化完成（最大连接数: {capacity}）")

    # -------------------------------------------------------------------------
    # 属性与统计
    # -------------------------------------------------------------------------
    @property
    def current_connections(self) -> int:
        """当前连接数量"""
        self._current_connections = len(self._connection_map)
        if self._current_connections > self._max_connections:
            self._max_connections = self._current_connections
        return self._current_connections

    @property
    def max_connections(self) -> int:
        """历史峰值"""
        return self._max_connections

    @property
    def capacity(self) -> int:
        """最大连接容量"""
        return self._capacity

    # -------------------------------------------------------------------------
    # 核心接口
    # -------------------------------------------------------------------------
    async def add_connection(self, client_connection: ClientConnection) -> None:
        """添加连接"""
        async with self._async_lock:
            uid = client_connection.uid
            if uid in self._connection_map:
                raise KeyError(f"连接已存在 [UID:{uid}]")

            if len(self._connection_map) >= self._capacity:
                raise CapacityExceededError(self._capacity)

            self._connection_map[uid] = client_connection
            self._current_connections = len(self._connection_map)
            log.debug(f"[{uid}] 已添加，当前连接数: {self._current_connections}")

    async def remove_connection(self, uid: str) -> Optional[ClientConnection]:
        """移除连接"""
        if not uid or not isinstance(uid, str):
            raise ValueError("UID 必须是非空字符串")

        async with self._async_lock:
            conn = self._connection_map.pop(uid, None)
            self._current_connections = len(self._connection_map)
            log.debug(f"[{uid}] 已移除，当前连接数: {self._current_connections}")
            return conn

    async def get_connection(self, uid: str) -> Optional[ClientConnection]:
        """快速获取连接（无锁读取）"""
        if not uid or not isinstance(uid, str):
            raise ValueError("UID 必须是非空字符串")
        return self._connection_map.get(uid)

    async def iter_connections(self) -> AsyncIterator[ClientConnection]:
        """安全迭代所有活跃连接"""
        async with self._async_lock:
            connections = list(self._connection_map.values())

        for conn in connections:
            yield conn

    async def clear(self) -> None:
        """关闭并清空所有连接"""
        async with self._async_lock:
            connections = list(self._connection_map.values())
            self._connection_map.clear()
            self._current_connections = 0

        for conn in connections:
            try:
                await conn.close()
            except Exception as ex:
                log.warning(f"关闭连接失败 [UID:{conn.uid}] - {ex}")
        log.info("所有连接已清空")
