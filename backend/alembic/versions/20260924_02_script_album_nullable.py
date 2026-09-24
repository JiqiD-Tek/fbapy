"""允许设备生成的剧本不归属专辑。

Revision ID: 20260924_02
Revises: 20260924_01
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = '20260924_02'
down_revision = '20260924_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'u_script',
        'album_id',
        existing_type=sa.BigInteger(),
        nullable=True,
        comment='所属剧本专辑 ID，为空表示不属于专辑',
    )


def downgrade() -> None:
    # 如果表中已有未归属专辑的剧本，降级前需要先处理这些数据。
    op.alter_column(
        'u_script',
        'album_id',
        existing_type=sa.BigInteger(),
        nullable=False,
        comment='所属剧本专辑 ID',
    )
