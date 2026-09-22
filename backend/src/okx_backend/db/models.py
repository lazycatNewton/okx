"""ORM 模型。

字段与保存口径依据 okx-requirements.md 第 2 节“保存、保留与首次启动回填”“面板字段与展示映射”。

约定：
- 价格、数量、比率、成交量等一律使用 String 保存 OKX 原始十进制字符串，
  不转 float/Decimal 重新格式化。
- 所有业务时间戳（OKX `ts` 等）保存为毫秒整数（BigInteger），由前端负责格式化显示。
- 每条记录附加 site='okex'、environment='production'、received_at（服务端接收时间）。
- 表名前缀标注所属需求编号，便于对照 okx-requirements.md。
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from okx_backend.db.base import Base

SITE = "okex"
ENVIRONMENT = "production"


class _SiteMixin:
    """所有行情存储记录共享的来源标记字段。"""

    site: Mapped[str] = mapped_column(String(16), default=SITE, server_default=SITE)
    environment: Mapped[str] = mapped_column(
        String(16), default=ENVIRONMENT, server_default=ENVIRONMENT
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 应用偏好（无登录，单例配置；见 okx-requirements.md “前端形态与使用范围”）
# ---------------------------------------------------------------------------


class AppPreference(Base):
    """单例应用偏好：上次活动 Tab。只有一行，主键固定为 1。产品选择顺序在
    SubscriptionConfigVersion 中。"""

    __tablename__ = "app_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_active_inst_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 产品目录（永久，按 instType+instId 保存当前基础信息 + 版本历史）
# ---------------------------------------------------------------------------


class InstrumentCatalogVersion(Base):
    """现货／永续产品目录版本记录。字段变化或 state 变化时追加新版本，不物理删除。"""

    __tablename__ = "instrument_catalog_versions"
    __table_args__ = (
        Index("ix_instrument_catalog_current", "inst_type", "inst_id", "is_current"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inst_type: Mapped[str] = mapped_column(String(16), nullable=False)  # SPOT / SWAP
    inst_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    base_ccy: Mapped[str | None] = mapped_column(String(32))
    quote_ccy: Mapped[str | None] = mapped_column(String(32))
    settle_ccy: Mapped[str | None] = mapped_column(String(32))
    ct_type: Mapped[str | None] = mapped_column(String(16))
    inst_family: Mapped[str | None] = mapped_column(String(64))
    uly: Mapped[str | None] = mapped_column(String(64))
    raw_payload: Mapped[dict] = mapped_column(JSON)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 订阅目录（永久，唯一用户全局配置 + 版本历史）
# ---------------------------------------------------------------------------


class SubscriptionConfigVersion(Base):
    """产品选择的有序 instId 列表版本（单例全局配置）。当前有效配置单独标记，历史版本保留。"""

    __tablename__ = "subscription_config_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ordered_inst_ids: Mapped[list] = mapped_column(JSON, nullable=False)  # 有序 instId 列表
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class M25UnitPreference(Base):
    """S04 单位偏好：每个产品最近一次选择，永久保留（unit: 0 币 / 1 合约 / 2 U）。"""

    __tablename__ = "m25_unit_preferences"

    inst_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    unit: Mapped[str] = mapped_column(String(4), default="1", server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# M01 ticker（7 天，每秒快照）
# ---------------------------------------------------------------------------


class TickerSnapshot(Base, _SiteMixin):
    __tablename__ = "m01_ticker_snapshots"
    __table_args__ = (UniqueConstraint("inst_id", "ts_ms", name="uq_m01_inst_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inst_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    inst_type: Mapped[str] = mapped_column(String(16), nullable=False)
    ts_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last: Mapped[str | None] = mapped_column(String(64))
    last_sz: Mapped[str | None] = mapped_column(String(64))
    bid_px: Mapped[str | None] = mapped_column(String(64))
    bid_sz: Mapped[str | None] = mapped_column(String(64))
    ask_px: Mapped[str | None] = mapped_column(String(64))
    ask_sz: Mapped[str | None] = mapped_column(String(64))
    open24h: Mapped[str | None] = mapped_column(String(64))
    high24h: Mapped[str | None] = mapped_column(String(64))
    low24h: Mapped[str | None] = mapped_column(String(64))
    vol_ccy24h: Mapped[str | None] = mapped_column(String(64))
    vol24h: Mapped[str | None] = mapped_column(String(64))
    sod_utc0: Mapped[str | None] = mapped_column(String(64))
    sod_utc8: Mapped[str | None] = mapped_column(String(64))
    raw_payload: Mapped[dict] = mapped_column(JSON)


# ---------------------------------------------------------------------------
# M02 K 线（成交价，7 天，按 instId+kind+bar+ts 去重）
# ---------------------------------------------------------------------------


class CandleKind(enum.StrEnum):
    TRADE = "trade"  # M02


class Candle(Base, _SiteMixin):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("inst_id", "kind", "bar", "ts_ms", name="uq_candle_key"),
        Index("ix_candle_lookup", "inst_id", "kind", "bar", "ts_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inst_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[CandleKind] = mapped_column(Enum(CandleKind), nullable=False)
    bar: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    o: Mapped[str] = mapped_column(String(64))
    h: Mapped[str] = mapped_column(String(64))
    low: Mapped[str] = mapped_column(String(64), name="l")
    c: Mapped[str] = mapped_column(String(64))
    vol: Mapped[str | None] = mapped_column(String(64))
    vol_ccy: Mapped[str | None] = mapped_column(String(64))
    vol_ccy_quote: Mapped[str | None] = mapped_column(String(64))
    confirm: Mapped[str] = mapped_column(String(4))


# ---------------------------------------------------------------------------
# M03 公共成交（7 天，按 instId+tradeId 去重）
# ---------------------------------------------------------------------------


class PublicTrade(Base, _SiteMixin):
    __tablename__ = "m03_public_trades"
    __table_args__ = (
        UniqueConstraint("inst_id", "trade_id", name="uq_m03_inst_trade"),
        Index("ix_m03_inst_ts", "inst_id", "ts_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inst_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ts_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    px: Mapped[str] = mapped_column(String(64))
    sz: Mapped[str] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(8))
    count: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(String(32))
    seq_id: Mapped[int | None] = mapped_column(BigInteger)
    raw_payload: Mapped[dict] = mapped_column(JSON)


# ---------------------------------------------------------------------------
# M05 五档盘口（7 天，每秒快照）
# ---------------------------------------------------------------------------


class Book5Snapshot(Base, _SiteMixin):
    __tablename__ = "m05_book5_snapshots"
    __table_args__ = (UniqueConstraint("inst_id", "ts_ms", name="uq_m05_inst_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inst_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ts_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    asks: Mapped[list] = mapped_column(JSON)
    bids: Mapped[list] = mapped_column(JSON)
    raw_payload: Mapped[dict] = mapped_column(JSON)


# ---------------------------------------------------------------------------
# M10 标记价格（7 天，每秒快照，仅永续）
# ---------------------------------------------------------------------------


class MarkPriceSnapshot(Base, _SiteMixin):
    __tablename__ = "m10_mark_price_snapshots"
    __table_args__ = (UniqueConstraint("inst_id", "ts_ms", name="uq_m10_inst_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inst_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    inst_type: Mapped[str] = mapped_column(String(16), nullable=False)
    ts_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mark_px: Mapped[str | None] = mapped_column(String(64))


# ---------------------------------------------------------------------------
# M13 持仓总量（7 天，每秒快照，仅永续）
# ---------------------------------------------------------------------------


class OpenInterestSnapshot(Base, _SiteMixin):
    __tablename__ = "m13_open_interest_snapshots"
    __table_args__ = (UniqueConstraint("inst_id", "ts_ms", name="uq_m13_inst_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inst_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    inst_type: Mapped[str] = mapped_column(String(16), nullable=False)
    ts_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    oi: Mapped[str | None] = mapped_column(String(64))
    oi_ccy: Mapped[str | None] = mapped_column(String(64))
    oi_usd: Mapped[str | None] = mapped_column(String(64))


# ---------------------------------------------------------------------------
# M22 事件合约辅助市场（目录永久；更新 7 天）
# ---------------------------------------------------------------------------


class EventContractSeries(Base):
    __tablename__ = "m22_series"

    series_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(64))
    freq: Mapped[str | None] = mapped_column(String(32))
    settlement: Mapped[dict | None] = mapped_column(JSON)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EventContractEvent(Base):
    __tablename__ = "m22_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    series_id: Mapped[str] = mapped_column(String(64), ForeignKey("m22_series.series_id"))
    exp_time: Mapped[int | None] = mapped_column(BigInteger)
    state: Mapped[str | None] = mapped_column(String(32))
    raw_payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EventContractMarket(Base):
    __tablename__ = "m22_markets"

    inst_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), ForeignKey("m22_events.event_id"))
    series_id: Mapped[str] = mapped_column(String(64), index=True)
    list_time: Mapped[int | None] = mapped_column(BigInteger)
    fix_time: Mapped[int | None] = mapped_column(BigInteger)
    exp_time: Mapped[int | None] = mapped_column(BigInteger, index=True)
    state: Mapped[str | None] = mapped_column(String(32))
    outcome: Mapped[str | None] = mapped_column(String(32))
    floor_strike: Mapped[str | None] = mapped_column(String(64))
    cap_strike: Mapped[str | None] = mapped_column(String(64))
    settle_value: Mapped[str | None] = mapped_column(String(64))
    disputed: Mapped[str | None] = mapped_column(String(16))
    hit_dir: Mapped[str | None] = mapped_column(String(16))
    raw_payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EventContractRevision(Base, _SiteMixin):
    """WS `event-contract-markets` 推送的状态变更／floorStrike 生成，7 天保留。"""

    __tablename__ = "m22_revisions"
    __table_args__ = (
        UniqueConstraint("inst_id", "business_ts", "payload_hash", name="uq_m22_revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inst_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON)


# ---------------------------------------------------------------------------
# M23 经济日历（7 天，追加式修订事件；未配置凭证/鉴权失败/网络故障/未达 VIP1 时应用返回空）
# ---------------------------------------------------------------------------


class EconomicCalendarEvent(Base, _SiteMixin):
    __tablename__ = "m23_economic_calendar"
    __table_args__ = (UniqueConstraint("calendar_id", "ts_ms", name="uq_m23_dedupe"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[int | None] = mapped_column(BigInteger, index=True)
    ts_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(64))
    importance: Mapped[str | None] = mapped_column(String(16))
    actual: Mapped[str | None] = mapped_column(String(64))
    forecast: Mapped[str | None] = mapped_column(String(64))
    previous: Mapped[str | None] = mapped_column(String(64))
    raw_payload: Mapped[dict] = mapped_column(JSON)


# ---------------------------------------------------------------------------
# M25 统计与历史（S01/S04/S05，7 天）
# ---------------------------------------------------------------------------


class M25Metric(enum.StrEnum):
    S01 = "S01"
    S04 = "S04"
    S05 = "S05"


class M25Stat(Base, _SiteMixin):
    """统一存储 S01/S04/S05；去重键见 okx-requirements.md 保存表。

    `unit` 在不适用时存空字符串 `''` 而非 NULL：MySQL 的唯一索引把 NULL 视为互不相等
    的值，若允许 NULL，`uq_m25_dedupe` 对 S01/S05（unit 不适用）完全不生效，每次轮询/
    重跑都会插入新行而不是覆盖旧值（已实测复现：约 3 万组重复行）。空字符串是普通值，
    唯一索引对其正常生效。
    """

    __tablename__ = "m25_stats"
    __table_args__ = (
        UniqueConstraint(
            "metric", "query_key", "period", "unit", "ts_ms", name="uq_m25_dedupe"
        ),
        Index("ix_m25_lookup", "metric", "query_key", "period", "unit", "ts_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric: Mapped[M25Metric] = mapped_column(Enum(M25Metric), nullable=False)
    query_key: Mapped[str] = mapped_column(String(64), nullable=False)  # 永续 instId
    period: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    unit: Mapped[str] = mapped_column(String(4), nullable=False, default="")  # 仅 S04 非空
    ts_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
