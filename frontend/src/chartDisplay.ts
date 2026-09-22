export interface ZhongshuPriceBoundaries {
  zg: number
  zd: number
}

export interface ZhongshuPriceLabel {
  boundary: 'ZG' | 'ZD'
  price: number
  text: string
}

export interface CandleOhlcStrings {
  o: string
  h: string
  l: string
  c: string
}

export interface CandleLegend {
  open: string
  high: string
  low: string
  close: string
}

function formatBoundaryPrice(price: number): string {
  return Number.isInteger(price) ? String(price) : String(price)
}

export function buildZhongshuPriceLabels(
  box: ZhongshuPriceBoundaries,
): ZhongshuPriceLabel[] {
  return [
    { boundary: 'ZG', price: box.zg, text: `ZG ${formatBoundaryPrice(box.zg)}` },
    { boundary: 'ZD', price: box.zd, text: `ZD ${formatBoundaryPrice(box.zd)}` },
  ]
}

export function buildCandleLegend(candle: CandleOhlcStrings): CandleLegend {
  return {
    open: candle.o,
    high: candle.h,
    low: candle.l,
    close: candle.c,
  }
}
