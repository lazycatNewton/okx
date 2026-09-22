"""drop m11 mark price candles

Revision ID: ad4f1b5392f5
Revises: 75fd54ac1bfe
Create Date: 2026-09-22 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ad4f1b5392f5'
down_revision: Union[str, Sequence[str], None] = '75fd54ac1bfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CANDLE_KIND_AFTER = "ENUM('TRADE')"
_CANDLE_KIND_BEFORE = "ENUM('TRADE','MARK')"


def upgrade() -> None:
    """按用户指令移除 M11（标记价格 K 线）实现。

    采集频道（`mark-price-candle{bar}`）、REST 历史回填方法、`candle:mark:*` 实时
    频道、前端图表组件均已删除。`candles.kind` 是 MySQL ENUM，必须先删掉 `MARK` 的行
    再收窄取值范围，否则残留行会变成 ENUM 的非法值（严格模式下 ALTER 直接失败）。
    """

    op.execute("DELETE FROM candles WHERE kind = 'MARK'")
    op.execute(f"ALTER TABLE candles MODIFY kind {_CANDLE_KIND_AFTER} NOT NULL")


def downgrade() -> None:
    """放宽 ENUM 取值范围；被删除的历史标记价格 K 线不恢复（可由官方历史接口重新回填）。"""

    op.execute(f"ALTER TABLE candles MODIFY kind {_CANDLE_KIND_BEFORE} NOT NULL")
