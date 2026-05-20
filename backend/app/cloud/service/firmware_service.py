# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware_service.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_firmware import firmware_dao
from backend.app.cloud.crud.crud_firmware_whitelist import firmware_whitelist_dao
from backend.app.cloud.model import Firmware, FirmwareWhitelist
from backend.app.cloud.schema.firmware import (
    BatchSetFirmwareWhitelistParam,
    CreateFirmwareParam,
    CreateFirmwareWhitelistParam,
    FirmwareReleaseScope,
    UpdateFirmwareParam,
    UpdateFirmwareWhitelistParam,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class FirmwareService:
    """固件服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Firmware:
        firmware = await firmware_dao.get(db, pk)
        if not firmware:
            raise errors.NotFoundError(msg='固件不存在')
        return firmware

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[Firmware]:
        return await firmware_dao.get_all(db)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        name: str | None = None,
        version: str | None = None,
        device_model: str | None = None,
        status: int | None = None,
        is_latest: bool | None = None,
        release_scope: FirmwareReleaseScope | None = None,
    ) -> dict[str, Any]:
        firmware_select = await firmware_dao.get_select(
            name=name,
            version=version,
            device_model=device_model,
            status=status,
            is_latest=is_latest,
            release_scope=release_scope,
        )
        return await paging_data(db, firmware_select)

    @staticmethod
    async def get_upgrade(
        *,
        db: AsyncSession,
        device_did: str,
        device_model: str,
        version_code: int,
    ) -> Firmware | None:
        if version_code < 0:
            raise errors.RequestError(msg='当前固件版本代码不正确')

        now = timezone.now()
        whitelist_rule = await firmware_whitelist_dao.get_active_by_device_did(
            db,
            device_did=FirmwareService._normalize_device_did(device_did),
            now=now,
        )
        if whitelist_rule is not None:
            target = await firmware_dao.get(db, whitelist_rule.firmware_id)
            if target is None:
                log.warning('firmware whitelist target missing, did={}, firmware_id={}', device_did, whitelist_rule.firmware_id)
                return None
            if target.status != 1:
                log.warning('firmware whitelist target disabled, did={}, firmware_id={}', device_did, target.id)
                return None
            if target.release_scope != FirmwareReleaseScope.WHITELIST.value:
                log.warning(
                    'firmware whitelist target scope invalid, did={}, firmware_id={}, scope={}',
                    device_did,
                    target.id,
                    target.release_scope,
                )
                return None
            if target.device_model != device_model:
                log.warning(
                    'firmware whitelist target model mismatch, did={}, firmware_id={}, device_model={}, firmware_model={}',
                    device_did,
                    target.id,
                    device_model,
                    target.device_model,
                )
                return None
            if target.version_code == version_code:
                return None
            if target.version_code < version_code and not whitelist_rule.allow_downgrade:
                return None
            return target

        return await firmware_dao.get_public_upgrade_firmware(
            db,
            device_model=device_model,
            version_code=version_code,
        )

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateFirmwareParam) -> Firmware:
        return await firmware_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFirmwareParam) -> int:
        firmware = await firmware_dao.get(db, pk)
        if not firmware:
            raise errors.NotFoundError(msg='固件不存在')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')

        if payload.get('release_scope') == FirmwareReleaseScope.PUBLIC.value:
            whitelist_count = await firmware_whitelist_dao.count_by_firmware_id(db, pk)
            if whitelist_count > 0:
                raise errors.RequestError(msg='该固件仍存在白名单设备，不能改为公开发布')

        return await firmware_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        firmware = await firmware_dao.get(db, pk)
        if not firmware:
            raise errors.NotFoundError(msg='固件不存在')

        whitelist_count = await firmware_whitelist_dao.count_by_firmware_id(db, pk)
        if whitelist_count > 0:
            raise errors.RequestError(msg='该固件仍存在白名单设备，无法删除')

        return await firmware_dao.delete(db, pk)

    @staticmethod
    async def get_whitelist_list(
        *,
        db: AsyncSession,
        firmware_id: int | None = None,
        device_did: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        whitelist_select = await firmware_whitelist_dao.get_select(
            firmware_id=firmware_id,
            device_did=FirmwareService._normalize_device_did(device_did) if device_did else None,
            enabled=enabled,
        )
        return await paging_data(db, whitelist_select)

    @staticmethod
    async def set_whitelist(
        *,
        db: AsyncSession,
        obj: BatchSetFirmwareWhitelistParam,
    ) -> list[FirmwareWhitelist]:
        firmware = await FirmwareService._ensure_whitelist_firmware(db=db, firmware_id=obj.firmware_id)
        device_dids = FirmwareService._normalize_device_dids(obj.device_dids)
        if not device_dids:
            raise errors.RequestError(msg='白名单设备不能为空')

        expires_at = FirmwareService._normalize_whitelist_expiry(obj.expires_at)
        FirmwareService._validate_whitelist_expiry(expires_at)

        payload = obj.model_dump(exclude={'device_dids'})
        payload['expires_at'] = expires_at
        existing_rules = await firmware_whitelist_dao.get_by_device_dids(db, device_dids)
        existing_map = {rule.device_did: rule for rule in existing_rules}

        saved_rules: list[FirmwareWhitelist] = []
        for device_did in device_dids:
            existing_rule = existing_map.get(device_did)
            rule_payload = {**payload, 'device_did': device_did}
            if existing_rule is None:
                rule = await firmware_whitelist_dao.create(
                    db,
                    CreateFirmwareWhitelistParam(**rule_payload),
                )
            else:
                await firmware_whitelist_dao.update(db, existing_rule.id, rule_payload)
                rule = await firmware_whitelist_dao.get(db, existing_rule.id)
            if rule is not None:
                saved_rules.append(rule)

        log.info(
            'firmware whitelist updated, firmware_id={}, device_count={}, firmware_version={}',
            firmware.id,
            len(saved_rules),
            firmware.version,
        )
        return saved_rules

    @staticmethod
    async def update_whitelist(*, db: AsyncSession, pk: int, obj: UpdateFirmwareWhitelistParam) -> int:
        rule = await firmware_whitelist_dao.get(db, pk)
        if not rule:
            raise errors.NotFoundError(msg='固件白名单不存在')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')

        if 'expires_at' in payload:
            payload['expires_at'] = FirmwareService._normalize_whitelist_expiry(payload['expires_at'])
        FirmwareService._validate_whitelist_expiry(payload.get('expires_at'), allow_none=True)
        return await firmware_whitelist_dao.update(db, pk, payload)

    @staticmethod
    async def delete_whitelist(*, db: AsyncSession, pk: int) -> int:
        rule = await firmware_whitelist_dao.get(db, pk)
        if not rule:
            raise errors.NotFoundError(msg='固件白名单不存在')
        return await firmware_whitelist_dao.delete(db, pk)

    @staticmethod
    async def _ensure_whitelist_firmware(*, db: AsyncSession, firmware_id: int) -> Firmware:
        firmware = await firmware_dao.get(db, firmware_id)
        if not firmware:
            raise errors.NotFoundError(msg='固件不存在')
        if firmware.release_scope != FirmwareReleaseScope.WHITELIST.value:
            raise errors.RequestError(msg='只有白名单发布固件才能绑定白名单设备')
        if not firmware.device_model:
            raise errors.RequestError(msg='白名单发布固件必须配置适用设备型号')
        return firmware

    @staticmethod
    def _normalize_device_did(device_did: str) -> str:
        normalized = device_did.strip().upper()
        if not normalized:
            raise errors.RequestError(msg='设备 DID 不能为空')
        return normalized

    @classmethod
    def _normalize_device_dids(cls, device_dids: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in device_dids:
            device_did = cls._normalize_device_did(item)
            if device_did in seen:
                continue
            seen.add(device_did)
            normalized.append(device_did)
        return normalized

    @staticmethod
    def _validate_whitelist_expiry(expires_at: datetime | None, *, allow_none: bool = False) -> None:
        if expires_at is None:
            if allow_none:
                return
            return
        if expires_at <= timezone.now():
            raise errors.RequestError(msg='白名单过期时间必须晚于当前时间')

    @staticmethod
    def _normalize_whitelist_expiry(expires_at: datetime | None) -> datetime | None:
        if expires_at is None:
            return None
        if expires_at.tzinfo is None:
            return expires_at.replace(tzinfo=timezone.tz_info)
        return timezone.from_datetime(expires_at)


firmware_service: FirmwareService = FirmwareService()
