"""M25 REST 查询响应组装的回归测试（不需要真实 DB/HTTP，直接测试字段合并顺序）。

依据 okx-requirements.md：M25 各行既有权威整数业务时间戳 `ts_ms`（数据库列），
`raw_payload` 自身也带一个官方字符串 `ts` 字段。曾经因为
字典展开顺序错误（`{"ts": ts_ms, **raw_payload}`），`raw_payload` 的字符串 `ts`
会覆盖权威整数 `ts_ms`，前端 `new Date(字符串)` 解析失败并抛
`RangeError: invalid timestamp for ET formatting`（已用真实浏览器复现）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _FakeM25Row:
    ts_ms: int
    period: str
    unit: str
    raw_payload: dict


def _build_item(row: _FakeM25Row) -> dict:
    """与 m25_router.get_m25_stat 中的响应组装逻辑保持一致。"""

    return {**row.raw_payload, "ts": row.ts_ms, "period": row.period, "unit": row.unit}


def test_authoritative_ts_ms_overrides_raw_payload_string_ts() -> None:
    row = _FakeM25Row(
        ts_ms=1789212300000,
        period="5m",
        unit="",
        raw_payload={"ts": "1789212300000", "longShortAcctRatio": "1.79"},
    )
    item = _build_item(row)
    assert item["ts"] == 1789212300000
    assert isinstance(item["ts"], int)
    assert item["longShortAcctRatio"] == "1.79"


def test_s04_raw_payload_fields_preserved_alongside_authoritative_ts() -> None:
    row = _FakeM25Row(
        ts_ms=1789212300000,
        period="5m",
        unit="1",
        raw_payload={"ts": "1789212300000", "buyVol": "360.18", "sellVol": "128.02"},
    )
    item = _build_item(row)
    assert item["ts"] == 1789212300000
    assert item["buyVol"] == "360.18"
    assert item["sellVol"] == "128.02"
    assert item["period"] == "5m"
    assert item["unit"] == "1"
