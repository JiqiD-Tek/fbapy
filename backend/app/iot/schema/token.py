from datetime import datetime

from pydantic import Field

from backend.common.enums import StatusType
from backend.common.schema import SchemaBase

from backend.app.iot.schema.user import GetUserInfoDetail


class AccessTokenBase(SchemaBase):
    """访问令牌基础模型"""

    access_token: str = Field(description='访问令牌')
    access_token_expire_time: datetime = Field(description='令牌过期时间')
    refresh_token: str = Field(description='刷新令牌')
    refresh_token_expire_time: datetime = Field(description='刷新令牌过期时间')
    session_uuid: str = Field(description='会话 UUID')


class GetNewToken(AccessTokenBase):
    """获取新令牌"""


class GetLoginToken(AccessTokenBase):
    """获取登录令牌"""

    user: GetUserInfoDetail = Field(description='用户信息')
