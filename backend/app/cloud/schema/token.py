from datetime import datetime

from pydantic import Field

from backend.app.cloud.schema.user import GetUserInfoDetail
from backend.common.enums import MiniProvisionStatus
from backend.common.schema import SchemaBase


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


class MiniProvisionTokenDetail(SchemaBase):
    """小程序配网 token 详情"""

    token: str = Field(description='配网 token')
    expire_seconds: int = Field(description='过期时间（秒）')
    status: MiniProvisionStatus = Field(description='配网状态')
    msg: str = Field(description='状态说明')


class MiniProvisionStatusDetail(SchemaBase):
    """小程序配网绑定结果"""

    token: str = Field(description='配网 token')
    status: MiniProvisionStatus = Field(description='配网状态')
    msg: str = Field(description='状态说明')
    bound: bool = Field(description='是否已完成绑定')
    expire_seconds: int = Field(description='剩余过期时间（秒）')
    device_id: int | None = Field(None, description='设备 ID')
    device_did: str | None = Field(None, description='设备 DID')
    device_sn: str | None = Field(None, description='设备序列号')


class MiniProvisionPayload(SchemaBase):
    """小程序配网 token 缓存数据"""

    token: str = Field(description='配网 token')
    user_id: int = Field(description='用户 ID')
    status: MiniProvisionStatus = Field(MiniProvisionStatus.pending, description='配网状态')
    msg: str = Field('', description='状态说明')
    bound: bool = Field(False, description='是否已完成绑定')
    device_id: int | None = Field(None, description='设备 ID')
    device_did: str | None = Field(None, description='设备 DID')
    device_sn: str | None = Field(None, description='设备序列号')

    def to_token_detail(self, expire_seconds: int) -> MiniProvisionTokenDetail:
        return MiniProvisionTokenDetail(
            token=self.token,
            expire_seconds=max(expire_seconds, 0),
            status=self.status,
            msg=self.msg,
        )

    def to_status_detail(self, expire_seconds: int) -> MiniProvisionStatusDetail:
        return MiniProvisionStatusDetail(
            token=self.token,
            status=self.status,
            msg=self.msg,
            bound=self.bound,
            expire_seconds=max(expire_seconds, 0),
            device_id=self.device_id,
            device_did=self.device_did,
            device_sn=self.device_sn,
        )


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
    bot_id: str = Field(description='聊天机器人 ID')


class LivekitToken(SchemaBase):
    """令牌"""

    url: str = Field(description='URL')
    token: str = Field(description='令牌')
    ttl: int = Field(description='令牌剩余时间')


class FbaToken(SchemaBase):
    """令牌"""

    token: str = Field(description='令牌')
    ttl: int = Field(description='令牌剩余时间')


class MiniProvisionBindParam(SchemaBase):
    """设备通过配网 token 绑定参数"""

    token: str = Field(description='小程序配网 token')


class StsToken(SchemaBase):
    """令牌"""

    access_key_id: str = Field(description='key')
    access_key_secret: str = Field(description='秘钥')
    security_token: str = Field(description='令牌')
    expiration: str = Field(description='失效时间')


class OSSToken(SchemaBase):
    """令牌"""

    url: str = Field(description='存储路径')
    sign_url: str = Field(description='签名路径')
