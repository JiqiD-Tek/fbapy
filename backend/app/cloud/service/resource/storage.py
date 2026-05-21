# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : storage.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/13 10:15
"""

import uuid

from backend.common.providers.ali_oss import oss_client
from backend.utils.timezone import timezone


class StorageService:
    CDN_HOST = 'https://media.jiqid.com'

    def __init__(self, product: str = 'fba'):
        self.product = product

    @staticmethod
    def _today() -> str:
        """返回当前日期 + 时分，格式 YYYYMMDDHHMM"""
        return timezone.now().strftime('%Y%m%d%H%M')

    @staticmethod
    def _uuid() -> str:
        """生成唯一 UUID（短）"""
        return uuid.uuid4().hex[:6]

    def create_object_name(self, uid: str, ext: str = 'jpg') -> str:
        filename = f'{self._today()}_{self._uuid()}.{ext}'
        key = f'{self.product}/{ext}/{uid}/{filename}'
        return key

    def get_object_url(self, object_name: str) -> str:
        return f'{self.CDN_HOST}/{object_name}'

    def get_sign_url(self, object_name: str) -> str:
        return oss_client.sign_url(object_name)

    def generate_signature(self):
        return oss_client.generate_signature()


if __name__ == '__main__':
    storage_service = StorageService()
    object_name = storage_service.create_object_name(uid='D98BB367386B5B18A815EC31F74B43A6')
    print(object_name)
    print(storage_service.get_object_url(object_name))
    print(storage_service.get_sign_url(object_name))
