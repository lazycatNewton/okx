"""drop m12 m14 m15 and m25 s09 s10 s11

Revision ID: c93b5ad10e77
Revises: a4c71e2f0b35
Create Date: 2026-09-22 04:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c93b5ad10e77'
down_revision: Union[str, Sequence[str], None] = 'a4c71e2f0b35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_M25_ENUM_AFTER = "ENUM('S01','S04','S05')"
_M25_ENUM_BEFORE = "ENUM('S01','S04','S05','S09','S10','S11')"


def upgrade() -> None:
    """按用户指令移除 M12／M14／M15 与 M25 的 S09／S10／S11 实现。

    这三张表和这三个指标已不再有任何写入方（采集频道、REST 方法、轮询任务、保留清理
    与前端面板都已删除），留着只会成为无人维护的孤儿结构与数据。

    `m25_stats.metric` 是 MySQL ENUM，必须先删掉被移除指标的行再收窄取值范围，
    否则残留行会变成 ENUM 的非法值（严格模式下 ALTER 直接失败）。
    """

    op.execute("DELETE FROM m25_stats WHERE metric IN ('S09', 'S10', 'S11')")
    op.execute(f"ALTER TABLE m25_stats MODIFY metric {_M25_ENUM_AFTER} NOT NULL")
    op.drop_table("m12_funding_rates")
    op.drop_table("m14_price_limits")
    op.drop_table("m15_estimated_prices")


def downgrade() -> None:
    """重建三张表的结构并放宽 ENUM；被删除的历史数据不恢复（均可由 OKX 重新回填）。"""

    op.execute(f"ALTER TABLE m25_stats MODIFY metric {_M25_ENUM_BEFORE} NOT NULL")
    op.create_table(
        "m12_funding_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("inst_id", sa.String(length=64), nullable=False),
        sa.Column("ts_ms", sa.BigInteger(), nullable=False),
        sa.Column("funding_rate", sa.String(length=64), nullable=True),
        sa.Column("funding_time", sa.BigInteger(), nullable=True),
        sa.Column("next_funding_time", sa.BigInteger(), nullable=True),
        sa.Column("sett_state", sa.String(length=32), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("site", sa.String(length=16), server_default="okex", nullable=False),
        sa.Column(
            "environment", sa.String(length=16), server_default="production", nullable=False
        ),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inst_id", "ts_ms", name="uq_m12_inst_ts"),
    )
    op.create_index("ix_m12_funding_rates_inst_id", "m12_funding_rates", ["inst_id"])
    op.create_table(
        "m14_price_limits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("inst_id", sa.String(length=64), nullable=False),
        sa.Column("inst_type", sa.String(length=16), nullable=False),
        sa.Column("ts_ms", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.String(length=8), nullable=True),
        sa.Column("buy_lmt", sa.String(length=64), nullable=True),
        sa.Column("sell_lmt", sa.String(length=64), nullable=True),
        sa.Column("site", sa.String(length=16), server_default="okex", nullable=False),
        sa.Column(
            "environment", sa.String(length=16), server_default="production", nullable=False
        ),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inst_id", "ts_ms", name="uq_m14_inst_ts"),
    )
    op.create_index("ix_m14_price_limits_inst_id", "m14_price_limits", ["inst_id"])
    op.create_table(
        "m15_estimated_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("inst_id", sa.String(length=64), nullable=False),
        sa.Column("inst_type", sa.String(length=16), nullable=False),
        sa.Column("ts_ms", sa.BigInteger(), nullable=False),
        sa.Column("settle_type", sa.String(length=16), nullable=True),
        sa.Column("settle_px", sa.String(length=64), nullable=True),
        sa.Column("site", sa.String(length=16), server_default="okex", nullable=False),
        sa.Column(
            "environment", sa.String(length=16), server_default="production", nullable=False
        ),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inst_id", "ts_ms", name="uq_m15_inst_ts"),
    )
    op.create_index("ix_m15_estimated_prices_inst_id", "m15_estimated_prices", ["inst_id"])
