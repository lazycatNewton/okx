"""purge utc+8 aligned daily rows

Revision ID: a4c71e2f0b35
Revises: 6060da89549d
Create Date: 2026-09-22 03:20:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4c71e2f0b35'
down_revision: Union[str, Sequence[str], None] = '6060da89549d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """历史数据修复（非自动生成，手写）：清空按 OKX UTC+8 口径落库的 `1D` 行。

    OKX 的 `1D` 是 UTC+8 开盘价 K 线（`1Dutc` 则是 UTC+0），两者都不是纽约自然日；
    已入库的 `1D` 行时间戳落在 UTC 16:00，也就是纽约时间中午，与本产品统一的纽约时区
    展示不对齐。日线改为由官方 `1H` 在后端按 America/New_York 自然日派生后，新旧两种
    口径的时间戳不同，唯一键不会互相覆盖：旧行会作为“中午的日线”一直残留在图表里。

    这里直接删除，而不是尝试换算：
    - `candles.bar='1D'` 的 OHLC 是 UTC+8 分日聚合的结果，无法反推成纽约分日；
    - `m25_stats.period='1D'` 同理。
    两者都能由服务启动后的回填重新派生（K 线 1H 源覆盖 80 个自然日，M25 1H 源覆盖 7 天），
    因此删除是可恢复的。`1H` 源行本身不受影响。
    """

    op.execute("DELETE FROM candles WHERE bar = '1D'")
    op.execute("DELETE FROM m25_stats WHERE period = '1D'")


def downgrade() -> None:
    """不可逆：被删除的是派生数据，降级后由旧代码按 OKX UTC+8 口径重新回填即可。"""

    pass
