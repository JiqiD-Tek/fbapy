from datetime import datetime

from pydantic import Field

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


class CurrentLocation(SchemaBase):
    """获取登录令牌"""
    ip: str = Field(description='IP 地址')
    country: str = Field(description='国家')
    region: str = Field(description='地区')
    city: str = Field(description='城市')


class CozeToken(SchemaBase):
    """令牌"""
    token_type: str = Field(description='令牌类型')
    access_token: str = Field(description='访问令牌')
    expires_in: int = Field(description='令牌过期时间')
    ttl: int = Field(description='令牌剩余时间')


class LivekitToken(SchemaBase):
    """令牌"""
    url: str = Field(description='URL')
    token: str = Field(description='令牌')
    ttl: int = Field(description='令牌剩余时间')


class FbaToken(SchemaBase):
    """令牌"""
    token: str = Field(description='令牌')
    ttl: int = Field(description='令牌剩余时间')


class StsToken(SchemaBase):
    """令牌
    """
    access_key_id: str = Field(description='key')
    access_key_secret: str = Field(description='秘钥')
    security_token: str = Field(description='令牌')
    expiration: str = Field(description='失效时间')


class OSSToken(SchemaBase):
    """令牌
    """
    url: str = Field(description='存储路径')
    sign_url: str = Field(description='签名路径')
