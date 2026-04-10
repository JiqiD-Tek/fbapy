# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : user.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 14:47
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class AuthSchemaBase(SchemaBase):
    """用户认证基础模型"""

    phone: str | None = Field(None, description='手机号')
    email: str | None = Field(None, description='邮箱')


class AuthLoginParam(AuthSchemaBase):
    """用户登录参数"""

    uuid: str | None = Field(None, description='验证码 UUID')
    captcha: str | None = Field(None, description='验证码')


class MiniProgramLoginParam(SchemaBase):
    """小程序登录注册参数"""

    code: str = Field(description='wx.login 返回的 code')


class MiniProgramProfileParam(SchemaBase):
    """小程序用户信息补充参数"""

    phone_code: str | None = Field(None, description='wx.getPhoneNumber 返回的 code')
    nickname: str | None = Field(None, description='昵称')
    avatar: str | None = Field(None, description='头像')


class DeviceAuthParam(SchemaBase):
    """设备登录参数"""

    mac: str = Field(description='MAC 地址')
    did: str = Field(description='设备did')
    sn: str = Field(description='设备序列号')
    model: str = Field(description='设备型号')


class MQTTAuthParam(SchemaBase):
    """MQTT登录参数"""

    username: str = Field(description='MAC 地址')
    password: str = Field(description='设备did')


class LivekitDeviceParam(SchemaBase):
    """Livekit设备参数"""

    metadata: str = Field(description='元数据')
    room: str = Field(description='房间名')
    name: str = Field(description='名称')


class UserSchemaBase(SchemaBase):
    """用户基础模型"""

    unionid: str | None = Field(None, description='微信 UnionID')
    phone: str | None = Field(None, description='手机号')
    username: str | None = Field(None, description='用户名')
    nickname: str | None = Field(None, description='昵称')
    email: str | None = Field(None, description='邮箱')
    avatar: str | None = Field(None, description='头像')
    sex: int | None = Field(None, description='性别(1男 2女)')
    birthday: datetime | None = Field(None, description='生日')


class CreateUserParam(UserSchemaBase):
    """创建用户参数"""

    class Config:
        # 明确配置
        validate_default = True
        arbitrary_types_allowed = True

        # 重写 __init__ 确保所有可选字段都被处理

    def __init__(self, **data) -> None:
        # 为所有可选字段提供默认值
        optional_fields = ['unionid', 'username', 'nickname', 'email', 'avatar', 'sex', 'birthday']

        for field in optional_fields:
            if field not in data:
                data[field] = None

        super().__init__(**data)


class UserDeviceParam(SchemaBase):
    """用户设备"""

    user_id: int = Field(description='用户 ID')
    device_id: int = Field(description='设备 ID')


class UpdateUserParam(SchemaBase):
    """更新用户参数"""


class DeleteUserParam(SchemaBase):
    """删除用户参数"""

    pks: list[int] = Field(description='用户 ID 列表')


class GetUserInfoDetail(UserSchemaBase):
    """用户详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='用户 ID')
    uuid: str = Field(description='用户UUID')
    last_login_time: datetime | None = Field(None, description='上次登录时间')
