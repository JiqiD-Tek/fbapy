# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : feedback.py
@Author  : guhua@jiqid.com
@Date    : 2025/12/08 17:34
"""
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domain.crud.crud_feedback import feedback_dao
from backend.app.domain.model import Feedback
from backend.app.domain.schema.feedback import (
    CreateFeedbackParam,
    UpdateFeedbackParam,
    DeleteFeedbackParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class FeedbackService:
    """反馈服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Feedback:
        """ 获取反馈详情 """
        feedback = await feedback_dao.get(db, pk)
        if not feedback:
            raise errors.NotFoundError(msg='反馈不存在')
        return feedback

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[Feedback]:
        """ 获取所有反馈  """
        feedbacks = await feedback_dao.get_all(db)
        return feedbacks

    @staticmethod
    async def get_list(
            *, db: AsyncSession, name: str | None = None,
            device_id: int | None = None, user_id: int | None = None, status: int | None = None) -> dict[str, Any]:
        """ 获取反馈列表（支持分页和查询条件） """
        feedback_select = await feedback_dao.get_select(
            name=name, device_id=device_id, user_id=user_id, status=status)
        return await paging_data(db, feedback_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateFeedbackParam) -> Feedback:
        """ 创建反馈 """
        return await feedback_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFeedbackParam) -> int:
        """ 更新反馈  """
        # 检查反馈是否存在
        feedback = await feedback_dao.get(db, pk)
        if not feedback:
            raise errors.NotFoundError(msg='反馈不存在')

        # 如果是更新状态，可以添加状态流转逻辑
        if obj.status is not None:
            # 这里可以添加状态校验逻辑，比如：
            # - 某些状态只能从前一个状态转变而来
            # - 某些状态不能直接跳转到其他状态
            pass

        # 更新反馈
        count = await feedback_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteFeedbackParam) -> int:
        """ 批量删除反馈  """
        count = await feedback_dao.delete(db, obj.pks)
        return count


feedback_service: FeedbackService = FeedbackService()
