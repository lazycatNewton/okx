"""drop m10 mark price and m13 open interest snapshots

Revision ID: e7b3c1d90a42
Revises: 86fae8b0e48c
Create Date: 2026-10-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e7b3c1d90a42'
down_revision: Union[str, Sequence[str], None] = '86fae8b0e48c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """按用户指令移除 M10（标记价格）与 M13（持仓总量）的前后端实现。

    两表自 2026-10-07 起已停写，采集频道、Redis 缓存、实时分发、保留清理与前端卡片
    现已全部删除，留着只会成为无人维护的孤儿结构与数据。
    """

    op.drop_index(op.f('ix_m10_mark_price_snapshots_inst_id'), table_name='m10_mark_price_snapshots')
    op.drop_table('m10_mark_price_snapshots')
    op.drop_index(op.f('ix_m13_open_interest_snapshots_inst_id'), table_name='m13_open_interest_snapshots')
    op.drop_table('m13_open_interest_snapshots')


def downgrade() -> None:
    """重建两张表的结构；被删除的快照数据不恢复（实时快照无法从 OKX 回填）。"""

    op.create_table('m10_mark_price_snapshots',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('inst_id', sa.String(length=64), nullable=False),
    sa.Column('inst_type', sa.String(length=16), nullable=False),
    sa.Column('ts_ms', sa.BigInteger(), nullable=False),
    sa.Column('mark_px', sa.String(length=64), nullable=True),
    sa.Column('site', sa.String(length=16), server_default='okex', nullable=False),
    sa.Column('environment', sa.String(length=16), server_default='production', nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('inst_id', 'ts_ms', name='uq_m10_inst_ts')
    )
    op.create_index(op.f('ix_m10_mark_price_snapshots_inst_id'), 'm10_mark_price_snapshots', ['inst_id'], unique=False)
    op.create_table('m13_open_interest_snapshots',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('inst_id', sa.String(length=64), nullable=False),
    sa.Column('inst_type', sa.String(length=16), nullable=False),
    sa.Column('ts_ms', sa.BigInteger(), nullable=False),
    sa.Column('oi', sa.String(length=64), nullable=True),
    sa.Column('oi_ccy', sa.String(length=64), nullable=True),
    sa.Column('oi_usd', sa.String(length=64), nullable=True),
    sa.Column('site', sa.String(length=16), server_default='okex', nullable=False),
    sa.Column('environment', sa.String(length=16), server_default='production', nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('inst_id', 'ts_ms', name='uq_m13_inst_ts')
    )
    op.create_index(op.f('ix_m13_open_interest_snapshots_inst_id'), 'm13_open_interest_snapshots', ['inst_id'], unique=False)
