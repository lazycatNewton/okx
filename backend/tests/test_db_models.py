"""数据库模型 / upsert 语句的单元测试（不需要真实数据库连接）。

重点回归：Candle.low 映射到物理列 `l`；`on_duplicate_key_update()` 必须使用物理列名
（`l=`），而不是 ORM 属性名（`low=`）——用 `.values()`/`.on_duplicate_key_update()`
不对称的这一点曾导致 K 线的最低价字段在更新时被静默丢弃。
"""

from __future__ import annotations

from sqlalchemy.dialects import mysql
from sqlalchemy.dialects.mysql import insert as mysql_insert

from okx_backend.db.models import Candle, CandleKind


def test_candle_on_duplicate_key_update_includes_low_column() -> None:
    stmt = mysql_insert(Candle).values(
        inst_id="BTC-USDT",
        kind=CandleKind.TRADE,
        bar="1s",
        ts_ms=1,
        o="1",
        h="2",
        low="0.5",
        c="1.5",
        confirm="0",
    )
    stmt = stmt.on_duplicate_key_update(
        o="1", h="2", l="0.5", c="1.5", confirm="0"  # noqa: E741 - 必须是物理列名 l
    )
    compiled = str(stmt.compile(dialect=mysql.dialect()))
    assert "l = " in compiled or "`l` = " in compiled
    assert "ON DUPLICATE KEY UPDATE" in compiled
