import sqlalchemy as sa

from backend.common.model import MappedBase, TimeZone
from backend.utils.timezone import timezone


user_device = sa.Table(
    'u_user_device',
    MappedBase.metadata,
    sa.Column('id', sa.BigInteger, primary_key=True, unique=True, index=True, autoincrement=True, comment='主键ID'),
    sa.Column('user_id', sa.BigInteger, primary_key=True, comment='用户ID'),
    sa.Column('device_id', sa.BigInteger, primary_key=True, comment='设备ID'),
)


device_toy = sa.Table(
    'u_device_toy',
    MappedBase.metadata,
    sa.Column('id', sa.BigInteger, primary_key=True, unique=True, index=True, autoincrement=True, comment='主键ID'),
    sa.Column('device_id', sa.BigInteger, nullable=False, index=True, comment='设备ID'),
    sa.Column('toy_id', sa.BigInteger, nullable=False, index=True, comment='玩偶ID'),
    sa.Column('created_time', TimeZone, nullable=False, default=timezone.now, comment='创建时间'),
    sa.UniqueConstraint('device_id', 'toy_id', name='uq_device_toy_device_id_toy_id'),
)
