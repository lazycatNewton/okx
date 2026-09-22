// HTTP API 客户端：所有请求携带会话 Cookie（credentials: 'include'）。
import type {
  BootstrapResponse,
  CandleItem,
  EconomicCalendarItem,
  EventContractMarketItem,
  M25StatItem,
  ProductItem,
  TradeBar,
} from './types'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = body.detail ?? detail
    } catch {
      // 忽略非 JSON 错误体
    }
    throw new ApiError(resp.status, detail)
  }
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

export { ApiError }

export function login(username: string, password: string): Promise<{ username: string }> {
  return request('/api/session/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function logout(): Promise<{ ok: boolean }> {
  return request('/api/session', { method: 'DELETE' })
}

export function getBootstrap(): Promise<BootstrapResponse> {
  return request('/api/bootstrap')
}

export function listProducts(params: {
  instType?: string
  state?: string
  q?: string
}): Promise<{ items: ProductItem[] }> {
  const search = new URLSearchParams()
  if (params.instType) search.set('instType', params.instType)
  if (params.state) search.set('state', params.state)
  if (params.q) search.set('q', params.q)
  const qs = search.toString()
  return request(`/api/products${qs ? `?${qs}` : ''}`)
}

export function updateSelection(
  instIds: string[],
): Promise<{ accepted: string[]; rejected: string[] }> {
  return request('/api/subscriptions/products', {
    method: 'PUT',
    body: JSON.stringify({ instIds }),
  })
}

export function getCandles(
  instId: string,
  kind: 'trade',
  bar: TradeBar,
  limit = 300,
  options: { before?: number; signal?: AbortSignal } = {},
): Promise<{ items: CandleItem[] }> {
  const search = new URLSearchParams({ kind, bar, limit: String(limit) })
  if (options.before !== undefined) search.set('before', String(options.before))
  return request(`/api/market/${encodeURIComponent(instId)}/candles?${search.toString()}`, { signal: options.signal })
}

// M25：queryKey 为 S01/S04/S05 的永续 instId。
export function getM25Stat(
  queryKey: string,
  metric: 'S01' | 'S04' | 'S05',
  options: { period?: string; unit?: string; limit?: number } = {},
): Promise<{ items: M25StatItem[] }> {
  const search = new URLSearchParams()
  if (options.period) search.set('period', options.period)
  if (options.unit) search.set('unit', options.unit)
  search.set('limit', String(options.limit ?? 100))
  return request(
    `/api/market/${encodeURIComponent(queryKey)}/m25/${metric}?${search.toString()}`,
  )
}

export function getS04Unit(instId: string): Promise<{ unit: string }> {
  return request(`/api/market/${encodeURIComponent(instId)}/m25/s04/unit`)
}

export function setS04Unit(instId: string, unit: string): Promise<{ unit: string }> {
  const search = new URLSearchParams({ unit })
  return request(
    `/api/market/${encodeURIComponent(instId)}/m25/s04/unit?${search.toString()}`,
    { method: 'PUT' },
  )
}

// M22/M23 全局侧边栏：不透明 cursor 分页。
export function getEventContractMarkets(
  cursor?: string | null,
): Promise<{ items: EventContractMarketItem[]; nextCursor: string | null; hasMore: boolean }> {
  const search = new URLSearchParams()
  if (cursor) search.set('cursor', cursor)
  const qs = search.toString()
  return request(`/api/aux/event-contract-markets${qs ? `?${qs}` : ''}`)
}

export function getEconomicCalendar(
  cursor?: string | null,
): Promise<{ items: EconomicCalendarItem[]; nextCursor: string | null; hasMore: boolean }> {
  const search = new URLSearchParams()
  if (cursor) search.set('cursor', cursor)
  const qs = search.toString()
  return request(`/api/aux/economic-calendar${qs ? `?${qs}` : ''}`)
}
