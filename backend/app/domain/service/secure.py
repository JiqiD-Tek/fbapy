# -*- coding: UTF-8 -*-
import time
import hmac
import uuid
import base64
import hashlib

from typing import Dict
from cachetools import TTLCache
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.common.log import log
from backend.core.conf import settings


# ------------------ 密钥生成器 ------------------
class KeyGenerator:
    """生成 MAC / DID / key 三元组"""

    def __init__(self, master_secret: str, salt: str):
        self.master_secret = master_secret.encode()
        self.salt = salt.encode()

    def derive_credentials(self, mac: str) -> Dict[str, str]:
        mac = normalize_mac(mac)
        did = self._derive_credential_did(mac)
        key = self._derive_credential_key(mac, did)
        return {"mac": mac, "did": did, "key": key}

    def _derive_credential_did(self, mac: str) -> str:
        namespace = uuid.UUID(bytes=hashlib.sha256(self.master_secret).digest()[:16])
        u = uuid.uuid5(namespace, mac)
        return u.hex.upper()

    def _derive_credential_key(self, mac: str, did: str) -> str:
        info = f"KEY:{mac}:{did}".encode()
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            info=info,
        )
        key = hkdf.derive(self.master_secret)
        return base64.urlsafe_b64encode(key).decode("utf-8")


# ------------------ 注册服务器 ------------------
class RegistrationServer(KeyGenerator):
    """验证注册请求"""

    def __init__(self, master_secret: str, salt: str, max_cache_size=10000, cache_ttl=60):
        super().__init__(master_secret, salt)
        self.nonce_cache = TTLCache(maxsize=max_cache_size, ttl=cache_ttl)

    def verify(self, mac: str, did: str, timestamp: int, nonce: str, signature: str, **kwargs) -> bool:
        # 时间校验
        if abs(time.time() - timestamp) > 60:
            log.error("时间校验失败")
            return False

        # nonce 校验
        if nonce in self.nonce_cache:
            log.error("nonce 重复")
            return False
        self.nonce_cache[nonce] = True  # 自动过期

        # 重新生成三元组
        credentials = self.derive_credentials(mac)
        key = credentials["key"]

        # DID 校验
        if did != credentials["did"]:
            log.error("DID 校验失败")
            return False

        # 签名校验
        data = {
            "mac": mac,
            "did": did,
            "timestamp": timestamp,
            "nonce": nonce,
            **kwargs,
        }
        expected = sign(data, key)
        valid = hmac.compare_digest(expected, signature)
        if not valid:
            log.error("签名校验失败")
        return valid


# ------------------ 注册客户端 ------------------
class RegistrationClient:
    """客户端注册请求生成器"""

    @staticmethod
    def build_registration_request(mac: str, did: str, key: str) -> Dict[str, str]:
        mac = normalize_mac(mac)
        data = {
            "mac": mac,
            "did": did,
            "timestamp": int(time.time()),
            "nonce": uuid.uuid4().hex,
            "sn": "K10-0001",
            "model": "K10",
        }
        data["signature"] = sign(data, key)
        return data


def normalize_mac(mac: str) -> str:
    """标准化 MAC 地址"""
    return mac.upper()


def sign(data: Dict[str, str], key: str) -> str:
    """生成签名"""
    sorted_items = sorted(data.items())  # 按 key 排序
    sign_string = "&".join(f"{k}={v}" for k, v in sorted_items)
    return hmac.new(key.encode(), sign_string.encode(), hashlib.sha256).hexdigest()


secure_service = RegistrationServer(settings.MASTER_SECRET, salt=settings.KEY_SALT)


# ------------------ 测试 ------------------
def main(mac_address="C4:1C:9C:09:C9:81"):
    credentials = secure_service.derive_credentials(mac_address)
    print("三元组:", credentials)

    reg_data = RegistrationClient.build_registration_request(credentials["mac"], credentials["did"], credentials["key"])
    print("注册数据:", reg_data)

    valid = secure_service.verify(**reg_data)
    print("验证结果:", valid)


if __name__ == "__main__":
    main()
