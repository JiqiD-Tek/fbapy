# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : storage.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/13 10:15
"""

import uuid
from backend.utils.timezone import timezone


class StorageService:
    BASE_URL = "https://media.jiqid.com/K10"

    def __init__(self, did: str):
        self.did = did

    @staticmethod
    def _today() -> str:
        """返回当前日期 + 时分，格式 YYYYMMDDHHMM"""
        return timezone.now().strftime("%Y%m%d%H%M")

    @staticmethod
    def _uuid() -> str:
        """生成唯一 UUID（短）"""
        return uuid.uuid4().hex[:6]

    @staticmethod
    def _filename(file_type: str, ext: str) -> str:
        """生成文件名"""
        return f"{file_type}_{StorageService._today()}_{StorageService._uuid()}.{ext}"

    def image_feedback(self, ext: str = "jpg") -> str:
        """生成反馈图片路径"""
        filename = self._filename("photo", ext)
        return f"{self.BASE_URL}/image/feedback/{self.did}/{filename}"

    def audio_input(self, ext: str = "wav") -> str:
        """生成用户输入音频路径"""
        filename = self._filename("voice", ext)
        return f"{self.BASE_URL}/audio/input/{self.did}/{filename}"

    def audio_output(self, ext: str = "mp3") -> str:
        """生成系统输出音频路径"""
        filename = self._filename("tts", ext)
        return f"{self.BASE_URL}/audio/output/{self.did}/{filename}"

    def log_system(self, ext: str = "log") -> str:
        """生成系统日志路径"""
        filename = self._filename("system", ext)
        return f"{self.BASE_URL}/log/system/{self.did}/{filename}"

    def log_feedback(self, ext: str = "log") -> str:
        """生成反馈日志路径"""
        filename = self._filename("feedback", ext)
        return f"{self.BASE_URL}/log/feedback/{self.did}/{filename}"

    def ota_release(self, filename: str) -> str:
        """生成 OTA release 固件路径（文件名自定）"""
        return f"{self.BASE_URL}/ota/release/{filename}"

    def ota_beta(self, filename: str) -> str:
        """生成 OTA beta 固件路径"""
        return f"{self.BASE_URL}/ota/beta/{filename}"

    def temp_file(self, ext: str = "dat") -> str:
        """生成临时文件路径"""
        filename = self._filename("tmp", ext)
        return f"{self.BASE_URL}/temp/{self.did}/{filename}"


if __name__ == "__main__":
    storage = StorageService("K10-ABC123")

    print(storage.image_feedback())
    print(storage.audio_input())
    print(storage.audio_output())
    print(storage.log_system())
    print(storage.log_feedback())
    print(storage.ota_release("k10_1.3.0.bin"))
    print(storage.ota_beta("k10_beta_1.3.1.bin"))
    print(storage.temp_file())
