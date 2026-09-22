// 独立的实时数据层：负责 WebSocket 建连、重连、消息规范化与产品/频道状态维护。
// 渲染层（Tab、卡片、图表、盘口）只通过 useMarketData() 读取这里维护的状态，
// 不自行建立 WebSocket 连接，也不在组件内直接处理协议细节。
import type {
  Book5Data,
  CandleItem,
  MarkPriceData,
  OpenInterestData,
  TickerData,
  TradeData,
  WsEnvelope,
} from './types'

export interface ChannelState<T> {
  status: 'empty' | 'snapshot' | 'update'
  data: T | null
  receivedAt: string | null
}

export interface ProductRealtimeState {
  ticker: ChannelState<TickerData>
  books5: ChannelState<Book5Data>
  candles: Record<string, ChannelState<CandleItem>>
  trades: ChannelState<TradeData[]>
  markPrice: ChannelState<MarkPriceData>
  openInterest: ChannelState<OpenInterestData>
}

type Listener = () => void

const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 30000

function emptyProductState(): ProductRealtimeState {
  return {
    ticker: { status: 'empty', data: null, receivedAt: null },
    books5: { status: 'empty', data: null, receivedAt: null },
    candles: {},
    trades: { status: 'empty', data: null, receivedAt: null },
    markPrice: { status: 'empty', data: null, receivedAt: null },
    openInterest: { status: 'empty', data: null, receivedAt: null },
  }
}

/**
 * 单例实时数据层。负责：
 * - 建立 /ws/app 连接，指数退避重连（1s..30s，含抖动）。
 * - 维护"当前浏览器已激活产品"集合；重连后重新发送 activate-product。
 * - 按信封 type（snapshot/update/empty）更新每个产品每个频道的规范化状态。
 */
class MarketDataStore {
  private ws: WebSocket | null = null
  private reconnectAttempt = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private activatedInstIds = new Set<string>()
  private state = new Map<string, ProductRealtimeState>()
  private listeners = new Set<Listener>()
  private connected = false
  private stopped = false

  connect(): void {
    if (this.ws || this.stopped) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/app`
    const ws = new WebSocket(url)
    this.ws = ws

    ws.onopen = () => {
      this.reconnectAttempt = 0
      this.connected = true
      // 重连后按当前已激活集合重新声明；后端会先回 snapshot 再回 update。
      for (const instId of this.activatedInstIds) {
        this.sendActivate(instId)
      }
      this.notify()
    }

    ws.onmessage = (event) => {
      this.handleMessage(event.data)
    }

    ws.onclose = () => {
      this.connected = false
      this.ws = null
      this.notify()
      if (!this.stopped) this.scheduleReconnect()
    }

    ws.onerror = () => {
      ws.close()
    }
  }

  disconnect(): void {
    this.stopped = true
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.ws?.close()
    this.ws = null
  }

  private scheduleReconnect(): void {
    const delay = Math.min(
      RECONNECT_BASE_MS * 2 ** this.reconnectAttempt,
      RECONNECT_MAX_MS,
    )
    const jitter = delay * Math.random() * 0.3
    this.reconnectAttempt += 1
    this.reconnectTimer = setTimeout(() => this.connect(), delay + jitter)
  }

  private handleMessage(raw: string): void {
    let envelope: WsEnvelope
    try {
      envelope = JSON.parse(raw)
    } catch {
      return
    }
    const productState = this.state.get(envelope.instId) ?? emptyProductState()
    const channelState: ChannelState<unknown> = {
      status: envelope.type,
      data: envelope.data,
      receivedAt: envelope.receivedAt,
    }
    if (envelope.channel === 'ticker') {
      productState.ticker = channelState as ChannelState<TickerData>
    } else if (envelope.channel === 'books5') {
      productState.books5 = channelState as ChannelState<Book5Data>
    } else if (envelope.channel.startsWith('candle:')) {
      // 后端实时推送里 candle 的 ts 取自 OKX 原始行（字符串毫秒）；而 REST 历史查询
      // 返回的是数据库 BigInteger 序列化的数字。CandleItem.ts 约定为 number，这里
      // 统一转换，否则 CandleChart 用字符串调用 new Date() 会解析失败并抛
      // "Invalid time value"。
      const rawCandle = envelope.data as (CandleItem & { ts: number | string }) | null
      const normalizedCandle = rawCandle ? { ...rawCandle, ts: Number(rawCandle.ts) } : null
      productState.candles[envelope.channel] = {
        ...channelState,
        data: normalizedCandle,
      } as ChannelState<CandleItem>
    } else if (envelope.channel === 'trades') {
      const existing = productState.trades.data ?? []
      const incoming = Array.isArray(envelope.data) ? envelope.data : [envelope.data]
      const next = [...incoming, ...existing]
        .filter((item): item is TradeData => item !== null && typeof item === 'object' && 'tradeId' in item)
        .filter((item, index, items) => items.findIndex((other) => other.tradeId === item.tradeId) === index)
        .slice(0, 100)
      productState.trades = { status: envelope.type, data: next, receivedAt: envelope.receivedAt }
    } else if (envelope.channel === 'mark-price') {
      productState.markPrice = channelState as ChannelState<MarkPriceData>
    } else if (envelope.channel === 'open-interest') {
      productState.openInterest = channelState as ChannelState<OpenInterestData>
    }
    this.state.set(envelope.instId, { ...productState })
    this.notify()
  }

  private sendActivate(instId: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'activate-product', instId }))
    }
  }

  activateProduct(instId: string): void {
    this.activatedInstIds.add(instId)
    if (!this.state.has(instId)) {
      this.state.set(instId, emptyProductState())
    }
    this.sendActivate(instId)
    this.notify()
  }

  deactivateProduct(instId: string): void {
    this.activatedInstIds.delete(instId)
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'deactivate-product', instId }))
    }
  }

  getProductState(instId: string): ProductRealtimeState {
    return this.state.get(instId) ?? emptyProductState()
  }

  isConnected(): boolean {
    return this.connected
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private notify(): void {
    for (const listener of this.listeners) listener()
  }
}

export const marketDataStore = new MarketDataStore()
