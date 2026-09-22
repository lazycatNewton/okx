// 与后端契约对齐的类型定义。字段命名保持与 OKX / 后端 JSON 一致（驼峰）。

export interface ProductItem {
  instType: 'SPOT' | 'SWAP'
  instId: string
  state: string
  baseCcy: string | null
  quoteCcy: string | null
  settleCcy: string | null
  ctType: string | null
  instFamily: string | null
  selectable: boolean
}

export interface EventContractMarketItem {
  seriesId: string
  eventId: string
  instId: string
  expTime: number | null
  state: string | null
  floorStrike: string | null
  outcome: string | null
  category?: string | null
  listTime?: number | null
  fixTime?: number | null
  capStrike?: string | null
  settleValue?: string | null
  disputed?: string | null
  hitDir?: string | null
}

export interface EconomicCalendarItem {
  calendarId: string
  date: number | null
  event: string | null
  region: string | null
  importance: string | null
  actual: string | null
  forecast: string | null
  previous?: string | null
  category?: string | null
  prevInitial?: string | null
  refDate?: string | null
  unit?: string | null
  ccy?: string | null
  uTime?: string | null
}

export interface BootstrapResponse {
  username: string
  selectedInstIds: string[]
  lastActiveInstId: string | null
  auxSidebar: {
    eventContractMarkets: EventContractMarketItem[]
    economicCalendar: EconomicCalendarItem[]
  }
}

export interface TickerData {
  instType: string
  instId: string
  last: string
  lastSz: string
  askPx: string
  askSz: string
  bidPx: string
  bidSz: string
  open24h: string
  high24h: string
  low24h: string
  volCcy24h: string
  vol24h: string
  sodUtc0: string
  sodUtc8: string
  ts: string
}

export interface Book5Data {
  instId: string
  asks: [string, string, string, string][]
  bids: [string, string, string, string][]
  ts: string
}

export interface CandleItem {
  ts: number
  o: string
  h: string
  l: string
  c: string
  vol: string | null
  volCcy: string | null
  volCcyQuote: string | null
  confirm: string
}

export interface TradeData {
  instId: string
  tradeId: string
  px: string
  sz: string
  side: 'buy' | 'sell'
  ts: string
  count: string
  source: string
  seqId: number
}

export interface MarkPriceData {
  instId: string
  instType: string
  markPx: string
  ts: string
}

export interface OpenInterestData {
  instId: string
  instType: string
  oi: string
  oiCcy: string
  oiUsd: string
  ts: string
}

// 服务端 WebSocket 信封：{ type, instId, channel, data, sourceTs, receivedAt }
export interface WsEnvelope {
  type: 'snapshot' | 'update' | 'empty'
  instId: string
  channel: string
  data:
    | TickerData
    | Book5Data
    | CandleItem
    | TradeData
    | TradeData[]
    | MarkPriceData
    | OpenInterestData
    | null
  sourceTs: string | null
  receivedAt: string
}

export type TradeBar = '1s' | '1m' | '5m' | '15m' | '30m' | '1D'

// M25 S01/S04/S05：均已保存为按周期/单位归一化的 { ts, ...原始字段 } 行。
export interface M25StatItem {
  ts: number
  period: string | null
  unit: string | null
  [key: string]: unknown
}

export type M25Period = '5m' | '15m' | '1D'
export type S04Unit = '0' | '1' | '2'
