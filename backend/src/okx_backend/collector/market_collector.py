"""M01/M02/M05 采集器：维护 desired 订阅集合、落库、写 Redis 最新状态缓存。

范围（核心闭环阶段）：
- M01 ticker：public WS `tickers`，现货／永续均适用。
- M02 成交价 K 线：business WS `candle{bar}`，bar in {1s,5m,15m,1D}。
- M05 五档盘口：public WS `books5`。

已选产品集合来自订阅目录（数据库当前有效配置），本采集器只处理"持续采集"部分——
即：只要产品仍是已选且 live，无论 Tab 是否激活、浏览器是否连接，都要采集。
目前只有 M02 K 线落 MySQL；M01/M03/M05/M10/M13 仅写 Redis 最新值（2026-10-07）。
`activate-product`/`deactivate-product`（浏览器实时分发开关）不影响这里的 desired 集合。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import case
from sqlalchemy.dialects.mysql import insert as mysql_insert

from okx_backend.cache import get_redis
from okx_backend.config import get_settings
from okx_backend.db.base import session_scope
from okx_backend.db.models import (
    Candle,
    CandleKind,
)
from okx_backend.okx_client.ws_client import ChannelArg, OkxWsClient
from okx_backend.realtime.hub import get_hub
from okx_backend.services.candle_cache import cache_latest_candle
from okx_backend.services.ny_day import NY_DAY_SOURCE_BAR
from okx_backend.services.ny_day_candles import on_source_candle_stored

# 对外提供（前端可选）的周期。`1D` 不是 OKX 频道，而是由官方 `1H` 按纽约自然日派生，
# 见 services/ny_day_candles.py；OKX 自身的 `1D` 是 UTC+8 开盘口径，与本产品统一的纽约
# 时区展示不对齐，因此不再直接订阅。
TRADE_BARS = ("1s", "1m", "5m", "15m", "30m", "1D")

# 实际向 OKX 订阅/回填的源周期：把 `1D` 换成派生源 `1H`，其余保持不变。
TRADE_SOURCE_BARS = tuple(NY_DAY_SOURCE_BAR if bar == "1D" else bar for bar in TRADE_BARS)


@dataclass(frozen=True)
class CandleRow:
    ts_ms: str
    o: str
    high: str
    low: str
    close: str
    vol: str | None
    vol_ccy: str | None
    vol_ccy_quote: str | None
    confirm: str


def parse_candle_row(row: list[str]) -> CandleRow:
    """OKX 的 M02 K 线固定 9 列。"""

    ts_ms, o, high, low, close, vol, vol_ccy, vol_ccy_quote, confirm = row
    return CandleRow(ts_ms, o, high, low, close, vol, vol_ccy, vol_ccy_quote, confirm)


def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _to_optional_int(value: str | None) -> int | None:
    return int(value) if value else None


class MarketCollector:
    """针对一批 (inst_id, inst_type) 维护 M01/M02/M05 的 WS 订阅、落库与缓存。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._public_ws = OkxWsClient(settings.okx_ws_public, self._on_public_message)
        self._business_ws = OkxWsClient(settings.okx_ws_business, self._on_business_message)
        self._inst_types: dict[str, str] = {}  # inst_id -> instType，供 M01 payload 补全

    def start(self) -> None:
        self._public_ws.start()
        self._business_ws.start()

    async def stop(self) -> None:
        await self._public_ws.stop()
        await self._business_ws.stop()

    def apply_selected_products(self, products: list[tuple[str, str, str | None]]) -> None:
        """`products`: [(instId, instType, instFamily), ...]，只包含已选且 live 的产品。"""

        self._inst_types = {inst_id: inst_type for inst_id, inst_type, _ in products}
        public_channels: set[ChannelArg] = set()
        business_channels: set[ChannelArg] = set()
        for inst_id, inst_type, _ in products:
            public_channels.add(ChannelArg(channel="tickers", inst_id=inst_id))
            public_channels.add(ChannelArg(channel="books5", inst_id=inst_id))
            public_channels.add(ChannelArg(channel="trades", inst_id=inst_id))
            for bar in TRADE_SOURCE_BARS:
                business_channels.add(ChannelArg(channel=f"candle{bar}", inst_id=inst_id))
            if inst_type == "SWAP":
                # M10/M13：需求文档只对永续接入，现货不订阅这些频道。
                public_channels.add(ChannelArg(channel="mark-price", inst_id=inst_id))
                public_channels.add(ChannelArg(channel="open-interest", inst_id=inst_id))
        self._public_ws.set_desired_channels(public_channels)
        self._business_ws.set_desired_channels(business_channels)

    # -- public: tickers / books5 / trades / M10 / M13 ------------------------
    async def _on_public_message(self, message: dict) -> None:
        arg = message.get("arg", {})
        channel = arg.get("channel")
        data = message.get("data", [])
        if channel == "tickers":
            for row in data:
                await self._store_ticker(row)
        elif channel == "books5":
            for row in data:
                await self._store_book5(arg.get("instId"), row)
        elif channel == "trades":
            for row in data:
                await self._store_public_trade(arg.get("instId"), row)
        elif channel == "mark-price":
            for row in data:
                await self._store_mark_price(row)
        elif channel == "open-interest":
            for row in data:
                await self._store_open_interest(row)

    # M01/M03/M05/M10/M13 暂不落 MySQL（用户指令，2026-10-07）：仅维护 Redis 最新值并广播。
    # 对应表、模型与 7 天保留清理暂留，让存量行自然过期。
    async def _store_ticker(self, row: dict) -> None:
        inst_id = row["instId"]
        redis = get_redis()
        await redis.set(f"m01:latest:{inst_id}", json.dumps(row), ex=120)
        await get_hub().broadcast_update(inst_id, "ticker", row)

    async def _store_book5(self, inst_id: str | None, row: dict) -> None:
        if inst_id is None:
            inst_id = row.get("instId")
        if inst_id is None:
            logger.warning(f"books5 row missing instId: {row!r}")
            return
        redis = get_redis()
        await redis.set(f"m05:latest:{inst_id}", json.dumps(row), ex=120)
        await get_hub().broadcast_update(inst_id, "books5", row)

    async def _store_public_trade(self, inst_id: str | None, row: dict) -> None:
        inst_id = inst_id or row.get("instId")
        trade_id = row.get("tradeId")
        if inst_id is None or trade_id is None:
            logger.warning(f"trade row missing identity: {row!r}")
            return
        redis = get_redis()
        key = f"m03:latest:{inst_id}"
        raw = await redis.get(key)
        latest = json.loads(raw) if raw else []
        latest = [row, *[item for item in latest if item.get("tradeId") != trade_id]][:100]
        await redis.set(key, json.dumps(latest), ex=120)
        await get_hub().broadcast_update(inst_id, "trades", row)

    # -- public: M10 mark-price / M13 open-interest（均仅永续）-----------------
    async def _store_mark_price(self, row: dict) -> None:
        inst_id = row.get("instId")
        if inst_id is None:
            logger.warning(f"mark-price row missing instId: {row!r}")
            return
        redis = get_redis()
        await redis.set(f"m10:latest:{inst_id}", json.dumps(row), ex=120)
        await get_hub().broadcast_update(inst_id, "mark-price", row)

    async def _store_open_interest(self, row: dict) -> None:
        inst_id = row.get("instId")
        if inst_id is None:
            logger.warning(f"open-interest row missing instId: {row!r}")
            return
        redis = get_redis()
        await redis.set(f"m13:latest:{inst_id}", json.dumps(row), ex=120)
        await get_hub().broadcast_update(inst_id, "open-interest", row)

    # -- business: trade candles ---------------------------------------------
    async def _on_business_message(self, message: dict) -> None:
        arg = message.get("arg", {})
        channel: str = arg.get("channel", "")
        inst_id = arg.get("instId")
        if inst_id is None:
            return
        if channel.startswith("candle"):
            kind = CandleKind.TRADE
            bar = channel.removeprefix("candle")
        else:
            return
        for row in message.get("data", []):
            await self._store_candle(inst_id, kind, bar, row)

    async def _store_candle(
        self, inst_id: str, kind: CandleKind, bar: str, row: list[str],
        derive_ny_day: bool = True,
        *, historical: bool = False,
    ) -> None:
        try:
            candle = parse_candle_row(row)
        except ValueError:
            logger.warning(f"unexpected candle row for {inst_id}/{kind}/{bar}: {row!r}")
            return
        # REST 快照可能早于正在接收的 WS；未完结历史不能覆盖更新的实时高低/收盘价。
        if historical and candle.confirm != "1":
            return
        data = {
            "ts": candle.ts_ms, "o": candle.o, "h": candle.high, "l": candle.low,
            "c": candle.close, "vol": candle.vol, "volCcy": candle.vol_ccy,
            "volCcyQuote": candle.vol_ccy_quote, "confirm": candle.confirm,
        }
        prefix = "m02"
        # `1H` 只是纽约日线的派生源，不作为对外周期：不写它的最新值缓存、不向浏览器广播，
        # 否则前端会收到一个它从未订阅的频道。
        is_source_only = bar == NY_DAY_SOURCE_BAR
        async with session_scope() as session:
            updates = dict(
                o=candle.o, h=candle.high, l=candle.low, c=candle.close, vol=candle.vol,
                vol_ccy=candle.vol_ccy, vol_ccy_quote=candle.vol_ccy_quote,
                received_at=datetime.now(UTC), confirm=candle.confirm,
            )
            # MySQL 按赋值顺序更新；confirm 必须最后写，所有字段依据原 confirm 判断。
            guarded = [
                (name, case((Candle.confirm != "1", value), else_=Candle.__table__.c[name]))
                if candle.confirm != "1" else (name, value)
                for name, value in updates.items()
            ]
            stmt = mysql_insert(Candle).values(
                inst_id=inst_id, kind=kind, bar=bar, ts_ms=int(candle.ts_ms), o=candle.o,
                h=candle.high,
                low=candle.low, c=candle.close, vol=candle.vol, vol_ccy=candle.vol_ccy,
                vol_ccy_quote=candle.vol_ccy_quote, confirm=candle.confirm,
            ).on_duplicate_key_update(guarded)
            await session.execute(stmt)
        if historical:
            # 倒序历史只修复数据库，不作为“最新实时”逐根广播/污染 Redis。
            # 浏览器定期读本产品历史接口取得整批修正，避免 React 合批只保留最后一根。
            return
        if is_source_only:
            if not derive_ny_day:
                return
            # 新的一根 1H 只会影响它所属的那个纽约自然日；重算该日并把结果当作 `1D` 广播。
            daily = await on_source_candle_stored(inst_id, kind, int(candle.ts_ms))
            if daily is not None:
                await get_hub().broadcast_update(inst_id, f"candle:{kind.value}:1D", daily)
            return
        if await cache_latest_candle(f"{prefix}:latest:{inst_id}:{bar}", data):
            await get_hub().broadcast_update(inst_id, f"candle:{kind.value}:{bar}", data)


_collector: MarketCollector | None = None


def get_collector() -> MarketCollector:
    global _collector
    if _collector is None:
        _collector = MarketCollector()
    return _collector
