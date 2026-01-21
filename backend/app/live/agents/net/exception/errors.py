#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author    : guhua@jiqid.com
# @File      : errors.py
# @Created   : 2025/4/17 15:49

from enum import Enum


class WebSocketErrorCode(Enum):
    """Combined error code with descriptions."""
    NORMAL_CLOSE = (1000, "Normal closure; the connection successfully completed its purpose.")
    GOING_AWAY = (1001, "The endpoint is going away, such as server shutdown or browser navigation.")
    PROTOCOL_ERROR = (1002, "A protocol error occurred.")
    UNSUPPORTED_DATA = (1003, "Unsupported data type received (e.g., binary data when only text is supported).")
    INVALID_PAYLOAD = (1007, "Invalid payload data (e.g., non-UTF-8 text in a text frame).")
    POLICY_VIOLATION = (1008, "A policy violation occurred.")
    MESSAGE_TOO_BIG = (1009, "Message too large (exceeds the maximum allowed size).")
    INTERNAL_ERROR = (1011, "An internal server error occurred.")

    INVALID_TOKEN = (4001, "Invalid or expired authentication token.")
    CONNECTION_LIMIT_EXCEEDED = (4002, "Connection limit exceeded (too many active connections).")
    RATE_LIMIT_EXCEEDED = (4003, "Rate limit exceeded (too many requests within a short period).")
    PERMISSION_DENIED = (4004, "Insufficient permissions to access the requested resource.")
    SESSION_EXPIRED = (4005, "Session has expired due to inactivity or timeout.")
    SERVICE_UNAVAILABLE = (4006, "Service is temporarily unavailable (e.g., under maintenance).")

    def __init__(self, code: int, reason: str):
        self.code = code
        self.reason = reason

    @classmethod
    def from_code(cls, code: int):
        """Find an error code by its numeric value."""
        for error in cls:
            if error.code == code:
                return error
        raise ValueError(f"Unknown error code: {code}")

    def __str__(self):
        return f"[{self.code}] {self.reason}"
