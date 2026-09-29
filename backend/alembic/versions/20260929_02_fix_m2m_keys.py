"""规范用户设备和设备玩偶关联表的主键、外键和索引。

Revision ID: 20260929_02
Revises: 20260929_01
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = '20260929_02'
down_revision = '20260929_01'
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column['name'] == column_name for column in inspector.get_columns(table_name))


def _drop_primary_key(table_name: str, inspector: sa.Inspector) -> None:
    primary_key = inspector.get_pk_constraint(table_name)
    name = primary_key.get('name')
    columns = primary_key.get('constrained_columns') or []
    if name and columns != ['id']:
        op.drop_constraint(name, table_name, type_='primary')


def _ensure_primary_key(table_name: str, inspector: sa.Inspector) -> None:
    primary_key = inspector.get_pk_constraint(table_name)
    if primary_key.get('constrained_columns') == ['id']:
        return
    op.create_primary_key(f'pk_{table_name}', table_name, ['id'])


def _drop_single_column_indexes(table_name: str, inspector: sa.Inspector, columns: set[str]) -> None:
    for index in inspector.get_indexes(table_name):
        index_columns = index.get('column_names') or []
        if len(index_columns) == 1 and index_columns[0] in columns:
            op.drop_index(index['name'], table_name=table_name)


def _has_unique_columns(inspector: sa.Inspector, table_name: str, columns: list[str]) -> bool:
    expected = set(columns)
    return any(
        set(constraint.get('column_names') or []) == expected
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _has_foreign_key(
        inspector: sa.Inspector,
        table_name: str,
        columns: list[str],
        referred_table: str,
        referred_columns: list[str],
) -> bool:
    return any(
        fk.get('constrained_columns') == columns
        and fk.get('referred_table') == referred_table
        and fk.get('referred_columns') == referred_columns
        for fk in inspector.get_foreign_keys(table_name)
    )


def _ensure_foreign_key(
        inspector: sa.Inspector,
        table_name: str,
        columns: list[str],
        referred_table: str,
        referred_columns: list[str],
        name: str,
) -> None:
    if not _has_foreign_key(inspector, table_name, columns, referred_table, referred_columns):
        op.create_foreign_key(name, table_name, referred_table, columns, referred_columns, ondelete='CASCADE')


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, 'u_user_device'):
        if not _has_column(inspector, 'u_user_device', 'created_time'):
            op.add_column(
                'u_user_device',
                sa.Column(
                    'created_time',
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.text('CURRENT_TIMESTAMP'),
                    comment='创建时间',
                ),
            )

        _drop_primary_key('u_user_device', inspector)
        inspector = sa.inspect(bind)
        _drop_single_column_indexes('u_user_device', inspector, {'id', 'device_id'})
        inspector = sa.inspect(bind)
        _ensure_primary_key('u_user_device', inspector)
        inspector = sa.inspect(bind)
        if not _has_unique_columns(inspector, 'u_user_device', ['user_id', 'device_id']):
            op.create_unique_constraint(
                'uq_user_device_user_id_device_id',
                'u_user_device',
                ['user_id', 'device_id'],
            )
        inspector = sa.inspect(bind)
        _ensure_foreign_key(
            inspector, 'u_user_device', ['user_id'], 'u_user', ['id'], 'fk_user_device_user_id',
        )
        inspector = sa.inspect(bind)
        _ensure_foreign_key(
            inspector, 'u_user_device', ['device_id'], 'u_device', ['id'], 'fk_user_device_device_id',
        )
        inspector = sa.inspect(bind)
        if not any(
                set(index.get('column_names') or []) == {'device_id'}
                for index in inspector.get_indexes('u_user_device')
        ):
            op.create_index('idx_user_device_device_id', 'u_user_device', ['device_id'])

    if _table_exists(inspector, 'u_device_toy'):
        _drop_primary_key('u_device_toy', inspector)
        inspector = sa.inspect(bind)
        _drop_single_column_indexes('u_device_toy', inspector, {'id', 'device_id', 'toy_id'})
        inspector = sa.inspect(bind)
        _ensure_primary_key('u_device_toy', inspector)
        inspector = sa.inspect(bind)
        if not _has_unique_columns(inspector, 'u_device_toy', ['device_id', 'toy_id']):
            op.create_unique_constraint(
                'uq_device_toy_device_id_toy_id',
                'u_device_toy',
                ['device_id', 'toy_id'],
            )
        inspector = sa.inspect(bind)
        _ensure_foreign_key(
            inspector, 'u_device_toy', ['device_id'], 'u_device', ['id'], 'fk_device_toy_device_id',
        )
        inspector = sa.inspect(bind)
        _ensure_foreign_key(
            inspector, 'u_device_toy', ['toy_id'], 'u_toy', ['id'], 'fk_device_toy_toy_id',
        )
        inspector = sa.inspect(bind)
        if not any(
                set(index.get('column_names') or []) == {'toy_id'}
                for index in inspector.get_indexes('u_device_toy')
        ):
            op.create_index('idx_device_toy_toy_id', 'u_device_toy', ['toy_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, foreign_keys in {
        'u_device_toy': ['fk_device_toy_toy_id', 'fk_device_toy_device_id'],
        'u_user_device': ['fk_user_device_device_id', 'fk_user_device_user_id'],
    }.items():
        if not _table_exists(inspector, table_name):
            continue
        current_fks = {fk.get('name') for fk in inspector.get_foreign_keys(table_name)}
        for name in foreign_keys:
            if name in current_fks:
                op.drop_constraint(name, table_name, type_='foreignkey')
        inspector = sa.inspect(bind)

    if _table_exists(inspector, 'u_device_toy'):
        if any(index['name'] == 'idx_device_toy_toy_id' for index in inspector.get_indexes('u_device_toy')):
            op.drop_index('idx_device_toy_toy_id', table_name='u_device_toy')
        if _has_unique_columns(inspector, 'u_device_toy', ['device_id', 'toy_id']):
            op.drop_constraint('uq_device_toy_device_id_toy_id', 'u_device_toy', type_='unique')

    inspector = sa.inspect(bind)
    if _table_exists(inspector, 'u_user_device'):
        if any(index['name'] == 'idx_user_device_device_id' for index in inspector.get_indexes('u_user_device')):
            op.drop_index('idx_user_device_device_id', table_name='u_user_device')
        if _has_unique_columns(inspector, 'u_user_device', ['user_id', 'device_id']):
            op.drop_constraint('uq_user_device_user_id_device_id', 'u_user_device', type_='unique')
        if _has_column(inspector, 'u_user_device', 'created_time'):
            op.drop_column('u_user_device', 'created_time')
