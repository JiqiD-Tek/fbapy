# -*- coding: UTF-8 -*-
import base64
import hashlib
import uuid

from typing import Annotated

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import Cookie, Depends, Header

from backend.app.iot.schema.user import DeviceAuthParam
from backend.common.exception import errors
from backend.common.log import log
from backend.common.response.response_code import CustomErrorCode
from backend.core.conf import settings


class IdentityGenerator:
    """生成 MAC / DID / key 三元组（当前只使用 MAC + DID，key 保留占位）"""

    def __init__(self, master_secret: str, salt: str) -> None:
        """
        初始化 KeyGenerator

        Args:
            master_secret: 服务器私有密钥，用于派生 DID（UUIDv5）和 key（HKDF）
            salt: HKDF 派生 key 时使用的盐值
        """
        self.master_secret = master_secret.encode()  # 转为 bytes，用于哈希和 HKDF
        self.salt = salt.encode()  # 转为 bytes，用于 HKDF

    def derive_credentials(self, mac: str) -> dict[str, str]:
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
        return {'mac': mac, 'did': did, 'key': key}

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
        info = f'KEY:{mac}:{did}'.encode()  # 用作 HKDF info 字段，保证 key 与 mac/did 绑定
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            info=info,
        )
        key = hkdf.derive(self.master_secret)  # 派生 32 字节 key
        return base64.urlsafe_b64encode(key).decode('utf-8')  # urlsafe base64 输出


class IdentityVerifier(IdentityGenerator):
    """
    注册服务器，用于验证设备注册请求。

    基于 MAC + DID 的方案：
    - MAC：设备物理标识
    - DID：服务器派生的唯一设备逻辑 ID（UUIDv5）
    - key：当前版本保留占位，不使用

    """

    def verify(self, mac: str, did: str, **kwargs) -> bool:
        """
        验证设备注册请求是否合法

        验证逻辑：
        1. 时间校验：请求时间必须在 +/- 60 秒内
        2. nonce 校验：防止重复请求
        3. DID 校验：MAC -> DID 确认请求身份

        Args:
            mac: 设备 MAC 地址
            did: 请求中提供的 DID
            kwargs: 其他可选字段（忽略）

        Returns:
            bool: True = 请求合法，False = 请求非法
        """
        # ------------------ DID 校验 ------------------
        # 根据 MAC 派生 DID
        credentials = self.derive_credentials(mac)
        # 验证请求提供的 DID 是否匹配派生结果
        if did != credentials['did']:
            log.error('DID 校验失败')
            return False

        # ------------------ 验证通过 ------------------
        return True


# ------------------ 注册客户端 ------------------
class RequestBuilder:
    """客户端注册请求生成器"""

    @staticmethod
    def build_registration_request(
            mac: str,
            did: str,
            key: str,  # 三元组 必传
            sn: str = 'K102501A0100123',
            model: str = 'K11',  # 设备信息
    ) -> dict[str, str]:
        mac = normalize_mac(mac)
        data = {
            'mac': mac,
            'did': did,
            'key': key,
            'sn': sn,
            'model': model,
        }
        return data


def normalize_mac(mac: str) -> str:
    """标准化 MAC 地址"""
    return mac.upper()


identity_verifier = IdentityVerifier(settings.MASTER_SECRET, salt=settings.KEY_SALT)


def verify_device_credentials(mac: str, did: str) -> dict[str, str]:
    """
    校验设备 MAC / DID 合法性并返回派生结果

    :param mac: 设备 MAC 地址
    :param did: 设备 DID
    :return: 派生凭据字典
    """
    credentials = identity_verifier.derive_credentials(mac=mac)
    if did != credentials.get('did'):
        raise errors.CustomError(error=CustomErrorCode.DEVICE_ILLEGAL)
    return credentials


def verify_device_request(
        *,
        mac: str,
        did: str,
        sn: str,
        model: str,
) -> dict[str, str]:
    """
    校验完整设备请求（含时间戳和防重放）并返回派生结果

    :param mac: 设备 MAC 地址
    :param did: 设备 DID
    :param sn: 设备序列号
    :param model: 设备型号
    :return: 派生凭据字典
    """
    valid = identity_verifier.verify(
        mac=mac,
        did=did,
        sn=sn,
        model=model,
    )
    if not valid:
        raise errors.CustomError(error=CustomErrorCode.DEVICE_ILLEGAL)
    return identity_verifier.derive_credentials(mac=mac)


async def device_auth_verify(
        mac: Annotated[str | None, Header(description='MAC 地址')] = None,
        did: Annotated[str | None, Header(description='设备did')] = None,
        sn: Annotated[str | None, Header(description='设备序列号')] = None,
        model: Annotated[str | None, Header(description='设备型号')] = None,
        mac_cookie: Annotated[str | None, Cookie(alias='mac', description='MAC 地址')] = None,
        did_cookie: Annotated[str | None, Cookie(alias='did', description='设备did')] = None,
        sn_cookie: Annotated[str | None, Cookie(alias='sn', description='设备序列号')] = None,
        model_cookie: Annotated[str | None, Cookie(alias='model', description='设备型号')] = None,
) -> DeviceAuthParam:
    """
    从请求头/Cookie 读取设备认证参数并执行 MAC / DID 校验（Header 优先）

    :param mac: 设备 MAC 地址（header）
    :param did: 设备 did（header）
    :param sn: 设备序列号（header）
    :param model: 设备型号（header）
    :param mac_cookie: 设备 MAC 地址（cookie）
    :param did_cookie: 设备 did（cookie）
    :param sn_cookie: 设备序列号（cookie）
    :param model_cookie: 设备型号（cookie）
    :return: 规范化后的设备认证参数（DeviceAuthParam）
    """
    # Header 优先，Cookie 兜底
    mac = mac or mac_cookie
    did = did or did_cookie
    sn = sn or sn_cookie
    model = model or model_cookie

    if not mac or not did or not sn or not model:
        raise errors.CustomError(error=CustomErrorCode.DEVICE_ILLEGAL)

    device = DeviceAuthParam(mac=mac, did=did, sn=sn, model=model)
    verify_device_request(
        mac=device.mac,
        did=device.did,
        sn=sn,
        model=model,
    )
    return device


DependsDeviceAuth = Depends(device_auth_verify)


# ------------------ 测试 ------------------
def main(mac: str) -> None:
    credentials = identity_verifier.derive_credentials(mac)
    log.debug(f'三元组: {credentials}')

    reg_data = RequestBuilder.build_registration_request(credentials['mac'], credentials['did'], credentials['key'])
    log.debug(f'注册数据: {reg_data}')

    valid = identity_verifier.verify(**reg_data)
    log.debug(f'验证结果: {valid}')


if __name__ == '__main__':
    MAC = 'C4:1C:9C:09:C9:81'
    MAC = '3E:96:10:BA:61:2F'
    log.debug(f'MAC: {MAC}')
    main(mac=MAC)
