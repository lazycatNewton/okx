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
  return { type: 'price' as const, precision, minMove: 10 ** -precision }
}
