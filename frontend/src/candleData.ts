import type { CandleItem, TradeBar } from './types'

export function candleWindowMs(bar: TradeBar): number {
  return (bar === '1D' ? 7 * 24 : 2) * 60 * 60 * 1000
}

// 后一个集合优先；已闭合 K 线不能被晚到的未闭合版本回退。
export function mergeCandles(base: CandleItem[], incoming: CandleItem[]): CandleItem[] {
  const byTime = new Map(base.map(item => [item.ts, item]))
  for (const item of incoming) {
    const previous = byTime.get(item.ts)
    if (previous?.confirm === '1' && item.confirm !== '1') continue
    byTime.set(item.ts, item)
  }
  return [...byTime.values()].sort((a, b) => a.ts - b.ts)
}

// OHLC 字符串才是报价精度依据，不能沿用图表库默认的两位小数。
export function candlePriceFormat(items: CandleItem[]) {
  let precision = 0
  for (const item of items) {
    for (const value of [item.o, item.h, item.l, item.c]) {
      const [mantissa, exponent = '0'] = value.toLowerCase().split('e')
      const fraction = mantissa.split('.')[1]?.replace(/0+$/, '') ?? ''
      precision = Math.max(precision, fraction.length - Number(exponent))
    }
  }
  precision = Math.min(16, precision)
  // 1 / 10 ** n 而非 10 ** -n：后者在部分 V8 版本（如 Node 22）上得到 0.000009999… 这类误差值。
  return { type: 'price' as const, precision, minMove: 1 / 10 ** precision }
}

export interface VolumeBar<T> {
  time: T
  value?: number
  color?: string
}

const VOLUME_UP = 'rgba(34, 197, 94, 0.55)'
const VOLUME_DOWN = 'rgba(239, 68, 68, 0.55)'

// 成交量副图统一用官方 `volCcyQuote`（计价货币，USDT 本位即 U）；缺失时输出空白点，
// 保持与价格序列的时间轴一一对应，而不是伪造 0。颜色随该根 K 线涨跌。
export function volumeBar<T>(item: CandleItem & { time: T }): VolumeBar<T> {
  const value = item.volCcyQuote === null ? NaN : Number(item.volCcyQuote)
  if (!Number.isFinite(value)) return { time: item.time }
  return { time: item.time, value, color: Number(item.c) >= Number(item.o) ? VOLUME_UP : VOLUME_DOWN }
}

// instId 的第二段即计价货币：BTC-USDT / BTC-USDT-SWAP → USDT，BTC-USD-SWAP → USD。
export function quoteCurrency(instId: string): string {
  return instId.split('-')[1] ?? ''
}
