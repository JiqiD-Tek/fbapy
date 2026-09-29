import sqlalchemy as sa

from backend.common.model import MappedBase, TimeZone
from backend.utils.timezone import timezone

user_device = sa.Table(
    'u_user_device',
    MappedBase.metadata,
    sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True, comment='主键 ID'),
    sa.Column(
        'user_id', sa.BigInteger, sa.ForeignKey('u_user.id', ondelete='CASCADE'),
        nullable=False, comment='用户 ID',
    ),
    sa.Column(
        'device_id', sa.BigInteger, sa.ForeignKey('u_device.id', ondelete='CASCADE'),
        nullable=False, comment='设备 ID',
    ),
    sa.Column('created_time', TimeZone, nullable=False, default=timezone.now, comment='创建时间'),
    sa.UniqueConstraint('user_id', 'device_id', name='uq_user_device_user_id_device_id'),
    sa.Index('idx_user_device_device_id', 'device_id'),
)

device_toy = sa.Table(
    'u_device_toy',
    MappedBase.metadata,
    sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True, comment='主键 ID'),
    sa.Column(
        'device_id', sa.BigInteger, sa.ForeignKey('u_device.id', ondelete='CASCADE'),
        nullable=False, comment='设备 ID',
    ),
    sa.Column(
        'toy_id', sa.BigInteger, sa.ForeignKey('u_toy.id', ondelete='CASCADE'),
        nullable=False, comment='玩偶 ID',
    ),
    sa.Column('created_time', TimeZone, nullable=False, default=timezone.now, comment='创建时间'),
    sa.UniqueConstraint('device_id', 'toy_id', name='uq_device_toy_device_id_toy_id'),
    sa.Index('idx_device_toy_toy_id', 'toy_id'),
)
