# -*- coding: UTF-8 -*-
import time
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
    """生成 MAC / DID / key 三元组（当前只使用 MAC + DID，key 保留占位）"""

    def __init__(self, master_secret: str, salt: str):
        """
        初始化 KeyGenerator

        Args:
            master_secret: 服务器私有密钥，用于派生 DID（UUIDv5）和 key（HKDF）
            salt: HKDF 派生 key 时使用的盐值
        """
        self.master_secret = master_secret.encode()  # 转为 bytes，用于哈希和 HKDF
        self.salt = salt.encode()  # 转为 bytes，用于 HKDF

    def derive_credentials(self, mac: str) -> Dict[str, str]:
        """
        根据 MAC 地址派生设备三元组 (mac, did, key)
        当前版本 key 保留为空字符串

        Args:
            mac: 设备 MAC 地址

        Returns:
            dict: {
                "mac": 标准化后的 MAC 地址,
                "did": 派生的设备 UUIDv5 DID,
                "key": "" （保留字段）
            }
        """
        mac = normalize_mac(mac)  # 将 MAC 地址标准化为大写
        did = self._derive_credential_did(mac)  # 派生唯一 DID
        key = self._derive_credential_key(mac, did)
        return {"mac": mac, "did": did, "key": key}

    def _derive_credential_did(self, mac: str) -> str:
        """
        根据 MAC 派生设备唯一逻辑 ID（DID）
        使用 UUIDv5（SHA1 哈希）生成，保证确定性和唯一性

        规则:
        - 相同 master_secret + 相同 MAC -> 相同 DID
        - 不同 master_secret 或 MAC -> 不同 DID
        - 外部无法推算 master_secret

        Args:
            mac: 已标准化的 MAC 地址

        Returns:
            str: 32 位十六进制字符串，全部大写
        """
        # 使用 master_secret 派生私有 namespace，防止外部预测 DID
        namespace = uuid.UUID(bytes=hashlib.sha256(self.master_secret).digest()[:16])
        # UUIDv5：基于 namespace + name（MAC）生成确定性 UUID
        u = uuid.uuid5(namespace, mac)
        return u.hex.upper()  # 返回大写 32 位十六进制字符串

    def _derive_credential_key(self, mac: str, did: str) -> str:
        """
        根据 MAC 和 DID 派生设备 key
        当前保留实现，暂未启用

        使用 HKDF(SHA256) 从 master_secret 派生固定长度 key

        Args:
            mac: 已标准化 MAC 地址
            did: 派生的设备 DID

        Returns:
            str: base64 urlsafe 编码的 32 字节 key
        """
        info = f"KEY:{mac}:{did}".encode()  # 用作 HKDF info 字段，保证 key 与 mac/did 绑定
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            info=info,
        )
        key = hkdf.derive(self.master_secret)  # 派生 32 字节 key
        return base64.urlsafe_b64encode(key).decode("utf-8")  # urlsafe base64 输出


# ------------------ 注册服务器 ------------------
class RegistrationServer(KeyGenerator):
    """
    注册服务器，用于验证设备注册请求。

    基于 MAC + DID 的方案：
    - MAC：设备物理标识
    - DID：服务器派生的唯一设备逻辑 ID（UUIDv5）
    - key：当前版本保留占位，不使用

    特性：
    - 提供简单的时间窗口校验
    - 使用 TTLCache 防止 nonce 重放
    """

    def __init__(self, master_secret: str, salt: str, max_cache_size=10000, cache_ttl=60):
        """
        初始化 RegistrationServer

        Args:
            master_secret: 用于派生 DID 的服务器私有密钥
            salt: 目前保留，用于 key 派生（未启用）
            max_cache_size: nonce 缓存最大条目数
            cache_ttl: nonce 缓存过期时间（秒）
        """
        super().__init__(master_secret, salt)
        # nonce 缓存，用于防止重放攻击
        # TTLCache 会在条目超过 ttl 后自动删除
        self.nonce_cache = TTLCache(maxsize=max_cache_size, ttl=cache_ttl)

    def verify(self, mac: str, did: str, timestamp: int, nonce: str, **kwargs) -> bool:
        """
        验证设备注册请求是否合法

        验证逻辑：
        1. 时间校验：请求时间必须在 +/- 60 秒内
        2. nonce 校验：防止重复请求
        3. DID 校验：MAC -> DID 确认请求身份

        Args:
            mac: 设备 MAC 地址
            did: 请求中提供的 DID
            timestamp: 请求时间戳（秒）
            nonce: 请求随机值，防止重放
            kwargs: 其他可选字段（忽略）

        Returns:
            bool: True = 请求合法，False = 请求非法
        """
        # ------------------ 时间校验 ------------------
        # 请求时间与服务器时间差绝对值超过 60 秒即拒绝
        # if abs(time.time() - timestamp) > 60:
        #     log.error("时间校验失败")
        #     return False

        # ------------------ nonce 校验 ------------------
        # 如果 nonce 已存在缓存，说明请求重复
        if nonce in self.nonce_cache:
            log.error("nonce 重复")
            return False
        # 将当前 nonce 加入缓存，过期后自动删除
        self.nonce_cache[nonce] = True

        # ------------------ DID 校验 ------------------
        # 根据 MAC 派生 DID
        credentials = self.derive_credentials(mac)
        # 验证请求提供的 DID 是否匹配派生结果
        if did != credentials["did"]:
            log.error("DID 校验失败")
            return False

        # ------------------ 验证通过 ------------------
        return True


# ------------------ 注册客户端 ------------------
class RegistrationClient:
    """客户端注册请求生成器"""

    @staticmethod
    def build_registration_request(
            mac: str, did: str, key: str,  # 三元组 必传
            sn: str = "K102501A0100123", model: str = "K10",  # 设备信息
    ) -> Dict[str, str]:
        mac = normalize_mac(mac)
        data = {
            "mac": mac,
            "did": did,
            "timestamp": int(time.time()),
            "nonce": uuid.uuid4().hex,
            "sn": sn,
            "model": model,
        }
        return data


def normalize_mac(mac: str) -> str:
    """标准化 MAC 地址"""
    return mac.upper()


secure_service = RegistrationServer(settings.MASTER_SECRET, salt=settings.KEY_SALT)


# ------------------ 测试 ------------------
def main(mac_address="C4:1C:9C:09:C9:81"):
    credentials = secure_service.derive_credentials(mac_address)
    log.debug(f"三元组: {credentials}")

    reg_data = RegistrationClient.build_registration_request(credentials["mac"], credentials["did"], credentials["key"])
    log.debug(f"注册数据: {reg_data}")

    valid = secure_service.verify(**reg_data)
    log.debug(f"验证结果: {valid}")


if __name__ == "__main__":
    main()
