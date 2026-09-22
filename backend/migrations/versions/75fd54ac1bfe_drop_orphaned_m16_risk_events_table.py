"""drop orphaned m16 risk events table

Revision ID: 75fd54ac1bfe
Revises: c93b5ad10e77
Create Date: 2026-09-22 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '75fd54ac1bfe'
down_revision: Union[str, Sequence[str], None] = 'c93b5ad10e77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """补一条遗漏的迁移：M16（强平订单／ADL 预警）的应用代码已在此前一轮改动中整体
    移除（采集、REST、hub 频道、`RiskEvent` 模型均已删除），但当时没有配套写迁移
    删表，导致 `m16_risk_events` 一直是无人写入的孤儿表。这里补上。
    """

    op.drop_table("m16_risk_events")


def downgrade() -> None:
    """重建表结构；被删除的历史强平/ADL 事件不恢复（均可由 OKX 重新推送积累）。"""

    op.create_table(
        "m16_risk_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("inst_id", sa.String(length=64), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum("LIQUIDATION", "ADL_WARNING", name="riskeventtype"),
            nullable=False,
        ),
        sa.Column("business_ts", sa.BigInteger(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("site", sa.String(length=16), server_default="okex", nullable=False),
        sa.Column(
            "environment", sa.String(length=16), server_default="production", nullable=False
        ),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "inst_id", "event_type", "business_ts", "payload_hash", name="uq_m16_dedupe"
        ),
    )
    op.create_index("ix_m16_risk_events_inst_id", "m16_risk_events", ["inst_id"])
