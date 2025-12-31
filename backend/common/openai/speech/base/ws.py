# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：ws.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/16 10:47
"""

import time
import asyncio
import websockets

from typing import Any

from backend.common.log import log


class AsyncWebSocketClient(object):
    """高性能WebSocket客户端

    特性：
    - 自动重连机制
    - 线程安全的消息收发
    - 详细的连接状态监控
    - 支持大消息传输(1GB)
    """

    def __init__(self, url: str, token: str = ""):
        """
        Args:
            url: WebSocket服务地址 (ws:// or wss://)
            token: 认证令牌
        """
        self._url = url
        self._token = token

        self._lock = asyncio.Lock()
        self._conn = None

    @property
    def is_connected(self) -> bool:
        """兼容多种连接对象的连接状态检查"""
        if self._conn is None:
            return False

        # 方法1：检查标准websockets属性
        if hasattr(self._conn, 'close_code'):
            return self._conn.close_code is None

        # 方法2：检查标准websockets属性
        if hasattr(self._conn, 'closed'):
            return not self._conn.closed

        # 方法3：检查常见替代属性
        if hasattr(self._conn, 'is_closed'):  # 某些库使用is_closed
            return not self._conn.is_closed()

        # 方法4：最后手段，假设连接有效
        return True

    async def ensure_connection(
            self,
            max_retries: int = 3,
            initial_delay: float = 1.0,
            timeout: float = 10.0
    ) -> None:
        """确保WebSocket连接处于活跃状态，支持自动重连

        Args:
            max_retries: 最大重试次数 (默认3次)
            initial_delay: 初始重试延迟(秒) (默认1秒，采用指数退避)
            timeout: 单次连接超时时间(秒) (默认10秒)

        Raises:
            ConnectionError: 当所有重试失败后抛出
            RuntimeError: 当连接处于无效状态时抛出
        """
        if self.is_connected:
            return

        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                # 带超时的连接尝试
                await asyncio.wait_for(self.connect(), timeout=timeout)
                if self.is_connected:
                    log.debug(f"连接建立成功 (尝试 {attempt}/{max_retries})")
                    return

            except (ConnectionError, asyncio.TimeoutError) as e:
                last_exception = e
                if attempt < max_retries:
                    delay = min(initial_delay * (2 ** (attempt - 1)), 30.0)  # 指数退避，上限30秒
                    log.warning(
                        f"连接尝试 {attempt}/{max_retries} 失败: {str(e)}. {delay:.1f}秒后重试..."
                    )
                    await asyncio.sleep(delay)

        # 所有重试失败后的处理
        error_msg = f"无法建立连接 (尝试 {max_retries} 次). 最后错误: {str(last_exception)}"
        log.error(error_msg)
        raise ConnectionError(error_msg) from last_exception

    async def _connect(self, timeout: float = 10.0):
        """内部方法：建立WebSocket连接"""
        self._conn = await asyncio.wait_for(
            websockets.connect(
                self._url,
                additional_headers={'Authorization': f'Bearer; {self._token}'},  # 需要分号
                max_size=1_000_000_000,
            ),
            timeout=timeout
        )
        log.debug(f"WebSocket连接建立成功: {self._url}")

    async def connect(self, timeout: float = 10.0) -> None:
        """建立WebSocket连接

        Args:
            timeout: 连接超时时间（秒）
        """
        if self.is_connected:
            return

        try:
            await self._connect(timeout=timeout)

        except asyncio.TimeoutError:
            error_msg = f"连接超时({timeout}s): {self._url}"
            log.error(error_msg)
            raise ConnectionError(error_msg)

        except websockets.InvalidURI as e:
            error_msg = f"无效的WebSocket地址: {self._url} ({str(e)})"
            log.error(error_msg)
            raise ConnectionError(error_msg)

        except websockets.WebSocketException as e:
            error_msg = f"WebSocket连接错误: {str(e)}"
            log.error(error_msg)
            raise ConnectionError(error_msg)

        except Exception as e:
            error_msg = f"未知连接错误: {str(e)}"
            log.error(error_msg)
            raise ConnectionError(error_msg)

    async def _send(self, data: Any, timeout: float = 10.0) -> None:
        """内部发送方法（带超时和连接检查）"""
        try:
            await asyncio.wait_for(self._conn.send(data), timeout)
        except asyncio.TimeoutError:
            log.error(f"数据发送超时（{timeout}s）")
            raise
        except websockets.ConnectionClosed as e:
            log.error(f"连接已关闭")
            raise ConnectionError("连接中断") from e
        except Exception as e:
            log.error(f"发送数据失败: {type(e).__name__}: {str(e)}")
            raise RuntimeError("数据发送失败") from e

    async def send(self, data: Any, timeout: float = 10.0) -> Any:
        """安全发送数据并返回响应
        Args:
            data: 可序列化的消息数据
            timeout: 发送/接收超时时间(秒)，默认30秒

        """
        await self.ensure_connection()

        async with self._lock:
            start_time = time.perf_counter()

            try:
                # 带超时的发送和接收
                await self._send(data, timeout)
                response = await asyncio.wait_for(self._conn.recv(), timeout)

                elapsed_ms = (time.perf_counter() - start_time) * 1000
                log.debug(
                    f"消息往返耗时: {elapsed_ms:.2f}ms | "
                    f"请求长度: {len(data)}字节 | "
                    f"响应长度: {len(response) if response else 0}字节"
                )
                return response

            except websockets.ConnectionClosed as e:
                self._conn = None  # 清除失效连接
                log.error(f"连接断开 (e: {e})")
                raise ConnectionError("WebSocket连接已中断") from e

            except asyncio.TimeoutError:
                log.error(f"操作超时({timeout}s)")
                raise TimeoutError(f"操作超过{timeout}秒未完成")

            except Exception as e:
                log.error(
                    f"操作失败（耗时: {(time.perf_counter() - start_time):.2f}s）| "
                    f"错误: {type(e).__name__}: {str(e)}"
                )
                raise RuntimeError("消息处理失败") from e

    async def close(self, code: int = 1000, reason: str = "无") -> None:
        """优雅关闭WebSocket连接

        Args:
            code: WebSocket关闭状态码 (默认1000-正常关闭)
            reason: 关闭原因描述
        """
        if not self.is_connected:
            log.debug("连接已关闭，无需重复操作")
            return

        try:
            # 尝试正常关闭连接
            await self._conn.close()
            log.debug(
                f"WebSocket连接已关闭 | "
                f"状态码: {getattr(self._conn, 'close_code', code)} | "
                f"原因: {getattr(self._conn, 'close_reason', reason) or reason}"
            )
        except websockets.ConnectionClosed:
            log.debug("连接已关闭，无需再次关闭")
        except asyncio.CancelledError:
            log.warning("连接关闭操作被取消")
            raise
        except Exception as e:
            log.error(f"关闭连接时发生意外错误: {type(e).__name__}: {str(e)}")
            raise RuntimeError("无法安全关闭连接") from e
        finally:
            # 确保无论如何都清理连接对象
            self._conn = None
            if self._lock.locked():
                # 释放可能被锁定的资源
                self._lock.release()
