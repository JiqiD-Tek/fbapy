# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : encryptor.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/22 17:38
"""

import os
import base64
from typing import Optional

from Crypto.Cipher import AES

from backend.core.conf import settings


class Encryptor:
    """
        对称加密
    """

    def __init__(self, key=settings.ENCRYPT_SECRET_KEY):
        self.key = key.encode()  # key 长度必须 16/24/32 字节
        self.iv = self.key[:16]  # 固定16字节IV

    @staticmethod
    def generate_key(length: int = 32) -> str:
        """
        生成随机 key
        :param length: key 长度，推荐 32 字节（AES-256）
        :return: 随机 key bytes
        """
        key_bytes = os.urandom(length)
        return base64.urlsafe_b64encode(key_bytes).rstrip(b'=').decode()[:length]

    def _pad(self, s: str) -> bytes:
        pad_len = 16 - len(s.encode()) % 16
        return s.encode() + bytes([pad_len] * pad_len)

    def _unpad(self, b: bytes) -> str:
        pad_len = b[-1]
        return b[:-pad_len].decode()

    def encrypt(self, plaintext: str) -> Optional[str]:
        if not plaintext:
            return None

        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        encrypted = cipher.encrypt(self._pad(plaintext))
        return base64.b64encode(encrypted).decode()

    def decrypt(self, ciphertext: str) -> Optional[str]:
        if not ciphertext:
            return None

        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        decrypted = cipher.decrypt(base64.b64decode(ciphertext))
        return self._unpad(decrypted)


encryptor = Encryptor()


def main():
    for val in [
        "",
        "15050522761",
        "15050522761",
        "guhua@jiqid.com",
        "guhua@roboland.com.cn",
    ]:
        ret = encryptor.encrypt(val)
        print(ret)
        print(encryptor.decrypt(ret))


if __name__ == '__main__':
    main()
