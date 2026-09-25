// A1:CHAN 面板的数据层：把 chan.ts 的结构分析整理成可直接展示的文字摘要。
// 与图表叠加层（chanOverlay.ts）使用同一口径：只取已闭合 K 线（confirm==='1'）。
import { analyzeChan, type DivergenceKind, type RawBar, type StrokeDirection } from './chan.ts'
import type { CandleItem } from './types'

export type PricePosition = 'above' | 'inside' | 'below'

export interface ZhongshuSummary {
  seq: number // 按时间正序编号，最早的中枢为 1
  startTs: number
  endTs: number
  bars: number
  strokeCount: number
  zg: number
  zd: number
  gg: number
  dd: number
  // 统计范围：本中枢起点 → 下一中枢起点之前（最新中枢则到最后一根已闭合 K 线），
  // 即中枢本身加上离开段，背驰判断看的正是离开段。
  exhaustionCount: number
  divergenceCount: number
}

export interface DivergenceSummary {
  ts: number
  kind: DivergenceKind
  price: number
  isTop: boolean
  isExhaustion: boolean
  label: string
  code: string
}

export interface StrokeSummary {
  seq: number
  direction: StrokeDirection
  startTs: number
  endTs: number
  startPrice: number
  endPrice: number
  changePct: number
  bars: number
}

export interface ChanSummary {
  barCount: number
  firstTs: number
  lastTs: number
  lastClose: number
  topFractals: number
  bottomFractals: number
  exhaustionCount: number
  divergenceCount: number
  // 以下列表均为时间倒序（最新在前）
  zhongshu: ZhongshuSummary[]
  divergences: DivergenceSummary[]
  strokes: StrokeSummary[]
  latestStroke: StrokeSummary | null
  position: PricePosition | null // 最新收盘价相对最新中枢 [ZD, ZG]
}

const MIN_CONFIRMED_BARS = 5

const DIVERGENCE_TEXT: Record<DivergenceKind, { label: string; code: string }> = {
  top_exhaustion: { label: '顶背驰', code: 'BC-S' },
  bottom_exhaustion: { label: '底背驰', code: 'BC-B' },
  top_divergence: { label: '顶背离', code: 'DIV-S' },
  bottom_divergence: { label: '底背离', code: 'DIV-B' },
}

export function summarizeChan(items: CandleItem[]): ChanSummary | null {
  const confirmed = items.filter((item) => item.confirm === '1')
  if (confirmed.length < MIN_CONFIRMED_BARS) return null

  const bars: RawBar[] = confirmed.map((item, index) => ({
    index,
    ts: item.ts,
    open: Number(item.o),
    high: Number(item.h),
    low: Number(item.l),
    close: Number(item.c),
  }))
  const analysis = analyzeChan(bars)
  const tsAt = (index: number) => confirmed[index].ts
  const lastIndex = confirmed.length - 1

  const divergences: DivergenceSummary[] = analysis.divergences.map((d) => ({
    ts: tsAt(d.index),
    kind: d.kind,
    price: d.price,
    isTop: d.kind === 'top_exhaustion' || d.kind === 'top_divergence',
    isExhaustion: d.kind === 'top_exhaustion' || d.kind === 'bottom_exhaustion',
    ...DIVERGENCE_TEXT[d.kind],
  }))

  const zhongshu: ZhongshuSummary[] = analysis.zhongshu.map((z, i, all) => {
    const zoneEnd = i + 1 < all.length ? all[i + 1].startIndex - 1 : lastIndex
    const inZone = analysis.divergences.filter((d) => d.index >= z.startIndex && d.index <= zoneEnd)
    return {
      seq: i + 1,
      startTs: tsAt(z.startIndex),
      endTs: tsAt(z.endIndex),
      bars: z.endIndex - z.startIndex + 1,
      strokeCount: z.endStrokeIndex - z.startStrokeIndex + 1,
      zg: z.zg,
      zd: z.zd,
      gg: z.gg,
      dd: z.dd,
      exhaustionCount: inZone.filter((d) => d.kind.endsWith('exhaustion')).length,
      divergenceCount: inZone.filter((d) => d.kind.endsWith('divergence')).length,
    }
  })

  const strokes: StrokeSummary[] = analysis.strokes.map((s, i) => ({
    seq: i + 1,
    direction: s.direction,
    startTs: tsAt(s.start.index),
    endTs: tsAt(s.end.index),
    startPrice: s.start.price,
    endPrice: s.end.price,
    changePct: s.start.price === 0 ? 0 : ((s.end.price - s.start.price) / s.start.price) * 100,
    bars: s.end.index - s.start.index + 1,
  }))

  const lastClose = bars[lastIndex].close
  const latestZhongshu = zhongshu.at(-1)
  const position: PricePosition | null = latestZhongshu
    ? lastClose > latestZhongshu.zg ? 'above' : lastClose < latestZhongshu.zd ? 'below' : 'inside'
    : null

  return {
    barCount: confirmed.length,
    firstTs: confirmed[0].ts,
    lastTs: confirmed[lastIndex].ts,
    lastClose,
    topFractals: analysis.fractals.filter((f) => f.kind === 'top').length,
    bottomFractals: analysis.fractals.filter((f) => f.kind === 'bottom').length,
    exhaustionCount: divergences.filter((d) => d.isExhaustion).length,
    divergenceCount: divergences.filter((d) => !d.isExhaustion).length,
    zhongshu: zhongshu.reverse(),
    divergences: divergences.reverse(),
    strokes: strokes.slice().reverse(),
    latestStroke: strokes.at(-1) ?? null,
    position,
  }
}
