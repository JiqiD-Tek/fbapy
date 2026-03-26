import sqlalchemy as sa

from backend.common.model import MappedBase

# 用户设备表
user_device = sa.Table(
    'u_user_device',
    MappedBase.metadata,
    sa.Column('id', sa.BigInteger, primary_key=True, unique=True, index=True, autoincrement=True, comment='主键ID'),
    sa.Column('user_id', sa.BigInteger, primary_key=True, comment='用户ID'),
    sa.Column('device_id', sa.BigInteger, primary_key=True, comment='设备ID'),
)
