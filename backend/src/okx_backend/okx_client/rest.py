"""OKX REST 客户端（全球站 `okex`，实盘）。

接口依据：okx-v5-api Skill 0.2.0（核验日期见 okx-requirements.md）。
本文件直接使用 httpx.AsyncClient 而非 python-okx 的同步客户端，原因：
- FastAPI/采集器均为 asyncio 事件循环，python-okx 的 REST 客户端基于 requests（同步阻塞），
  在异步服务中使用需额外线程池包裹，收益低于直接实现。
- 本产品对参数、分页游标、限速窗口有逐接口的强约束（见 okx-requirements.md），直接控制请求
  更容易与需求逐条对照和测试。
`python-okx` 仍保留在依赖中，供后续 M22/M23/M25 等接口酌情复用其签名/鉴权逻辑。
"""

from __future__ import annotations

from typing import Any

import httpx

from okx_backend.config import get_settings


class OkxRestError(RuntimeError):
    def __init__(self, code: str, msg: str) -> None:
        super().__init__(f"OKX REST error {code}: {msg}")
        self.code = code
        self.msg = msg


class OkxRestClient:
    """无鉴权的公共 REST 调用封装；私有/鉴权调用（M23）由子类或单独模块处理。"""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        settings = get_settings()
        self._base_url = base_url or settings.okx_rest_base
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> OkxRestClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        clean_params = {k: v for k, v in params.items() if v is not None}
        resp = await self._client.get(path, params=clean_params)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") not in ("0", 0):
            raise OkxRestError(str(body.get("code")), str(body.get("msg")))
        return body["data"]

    # -- 产品发现：GET /api/v5/public/instruments -----------------------------
    async def get_instruments(self, inst_type: str) -> list[dict[str, Any]]:
        """`instType` 必填：SPOT / SWAP（本期使用范围）。限速 20 次/2s，按 IP+InstrumentType。"""

        return await self._get("/api/v5/public/instruments", {"instType": inst_type})

    # -- M02/M11 历史 K 线补数：GET /api/v5/market/history-candles ------------
    async def get_history_candles(
        self,
        inst_id: str,
        bar: str,
        after: str | None = None,
        before: str | None = None,
        limit: int = 300,
        adjust: str | None = None,
    ) -> list[list[str]]:
        """限速 20 次/2s/IP；单页最大 300；返回 [ts,o,h,l,c,vol,volCcy,volCcyQuote,confirm]。

        `adjust="forward"` 仅对股票永续合约生效，返回前复权 OHLC（成交量同比例调整，
        成交额不调整）；其余产品该参数无实际影响。文档: historyCandles.md。
        """

        return await self._get(
            "/api/v5/market/history-candles",
            {
                "instId": inst_id, "bar": bar, "after": after, "before": before,
                "limit": str(limit), "adjust": adjust,
            },
        )

    async def get_history_mark_price_candles(
        self,
        inst_id: str,
        bar: str,
        after: str | None = None,
        before: str | None = None,
        limit: int = 100,
    ) -> list[list[str]]:
        """M11 历史标记价格 K 线；20 次/2s/IP，单页最大 100。

        该接口不支持 `adjust` 参数（文档未列出，且实测传入 `adjust=forward` 对返回值
        无影响）：股票永续标记价格历史 K 线在拆股等公司行为发生前的时段会保留分割前的
        价格尺度，OKX 未提供前复权版本，本产品也无法在应用层安全地重建复权因子。
        """

        return await self._get(
            "/api/v5/market/history-mark-price-candles",
            {"instId": inst_id, "bar": bar, "after": after, "before": before, "limit": str(limit)},
        )

    # -- 初始 K 线（近 1440 条）：GET /api/v5/market/candles -------------------
    async def get_candles(
        self,
        inst_id: str,
        bar: str,
        after: str | None = None,
        before: str | None = None,
        limit: int = 300,
        adjust: str | None = None,
    ) -> list[list[str]]:
        """限速 40 次/2s/IP；单页最大 300。"""

        return await self._get(
            "/api/v5/market/candles",
            {
                "instId": inst_id, "bar": bar, "after": after, "before": before,
                "limit": str(limit), "adjust": adjust,
            },
        )

    # -- 初始价格回退：GET /api/v5/market/ticker -------------------------------
    async def get_ticker(self, inst_id: str) -> dict[str, Any]:
        data = await self._get("/api/v5/market/ticker", {"instId": inst_id})
        return data[0]

    # -- M25 S01：GET /api/v5/rubik/stat/contracts/long-short-account-ratio-contract
    async def get_long_short_account_ratio_contract(
        self,
        inst_id: str,
        period: str = "5m",
        begin: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[list[str]]:
        """限速 5 次/2s/IP+instId；单页最大 100；返回 [ts, longShortAcctRatio]。"""

        return await self._get(
            "/api/v5/rubik/stat/contracts/long-short-account-ratio-contract",
            {"instId": inst_id, "period": period, "begin": begin, "end": end, "limit": str(limit)},
        )

    # -- M25 S04：GET /api/v5/rubik/stat/taker-volume-contract -----------------
    async def get_taker_volume_contract(
        self,
        inst_id: str,
        period: str = "5m",
        unit: str = "1",
        begin: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[list[str]]:
        """限速 5 次/2s/IP+instId；单页最大 100；返回 [ts, sellVol, buyVol]。"""

        return await self._get(
            "/api/v5/rubik/stat/taker-volume-contract",
            {
                "instId": inst_id, "period": period, "unit": unit,
                "begin": begin, "end": end, "limit": str(limit),
            },
        )

    # -- M25 S05：GET /api/v5/rubik/stat/contracts/open-interest-history -------
    async def get_open_interest_history(
        self,
        inst_id: str,
        period: str = "5m",
        begin: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[list[str]]:
        """限速 10 次/2s/IP+instId；单页最大 100；返回 [ts, oi, oiCcy, oiUsd]。"""

        return await self._get(
            "/api/v5/rubik/stat/contracts/open-interest-history",
            {"instId": inst_id, "period": period, "begin": begin, "end": end, "limit": str(limit)},
        )

    # -- M22 事件合约辅助市场：GET /api/v5/public/event-contract/series/events/markets --
    async def get_event_contract_series(self, series_id: str | None = None) -> list[dict[str, Any]]:
        """限速 10 次/2s/IP；不传 `seriesId` 返回全部系列。"""

        return await self._get(
            "/api/v5/public/event-contract/series", {"seriesId": series_id}
        )

    async def get_event_contract_events(
        self,
        series_id: str,
        before: str | None = None,
        after: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """限速 10 次/2s/IP；`seriesId` 必填；按 `expTime` 用 `before`/`after` 分页，单页最大 100。

        不传 `state`（需求文档：保留全部自动发现的预测市场，不按状态筛选）。
        """

        return await self._get(
            "/api/v5/public/event-contract/events",
            {"seriesId": series_id, "before": before, "after": after, "limit": str(limit)},
        )

    async def get_event_contract_markets(
        self,
        series_id: str,
        before: str | None = None,
        after: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """限速 10 次/2s/IP；`seriesId` 必填；按 `expTime` 用 `before`/`after` 分页，
        单页最大 100。
        """

        return await self._get(
            "/api/v5/public/event-contract/markets",
            {"seriesId": series_id, "before": before, "after": after, "limit": str(limit)},
        )

    # -- M23 经济日历（需鉴权）：GET /api/v5/public/economic-calendar -------------
    async def get_economic_calendar(
        self,
        before: str | None = None,
        after: str | None = None,
        limit: int = 100,
        signed_headers: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """限速 1 次/5s/IP；需登录鉴权（signed_headers 由调用方按官方签名规则生成）；
        按 `date` 用 `before`/`after` 分页，单页最大 100。
        """

        clean_params = {
            k: v for k, v in {"before": before, "after": after, "limit": str(limit)}.items()
            if v is not None
        }
        resp = await self._client.get(
            "/api/v5/public/economic-calendar",
            params=clean_params,
            headers=signed_headers or {},
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") not in ("0", 0):
            raise OkxRestError(str(body.get("code")), str(body.get("msg")))
        return body["data"]
