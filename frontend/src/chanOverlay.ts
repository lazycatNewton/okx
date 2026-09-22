// 缠论叠加层的图表适配：把 CandleItem[] 接到 chan.ts 的纯算法，并产出
// Lightweight Charts 图元/标记所需的数据结构。只在指定周期启用（见
// isChanEnabledForBar），只用已闭合 K 线参与计算（Q6：分型需要"确认"，
// 避免结构随实时数据抖动）。
import type { SeriesMarker, Time } from 'lightweight-charts'
import { analyzeChan, type RawBar } from './chan'
import type { ChanStrokeSegment, ChanZhongshuBox } from './chanPrimitives'
import type { CandleItem } from './types'

export type ChanKind = 'trade' | 'mark'

// M02（trade）排除 1s/1m；M11（mark）本身没有 1s，只排除 1m。
const EXCLUDED_BARS: Record<ChanKind, string[]> = {
  trade: ['1s', '1m'],
  mark: ['1m'],
}

export function isChanEnabledForBar(kind: ChanKind, bar: string): boolean {
  return !EXCLUDED_BARS[kind].includes(bar)
}

export interface ChanOverlayResult {
  boxes: ChanZhongshuBox[]
  strokePoints: ChanStrokeSegment[]
  markers: SeriesMarker<Time>[]
}

const EMPTY_RESULT: ChanOverlayResult = { boxes: [], strokePoints: [], markers: [] }

// 中枢至少需要 3 笔重叠、一笔至少 3 根分析 K 线；已闭合 K 线太少时不强行凑，
// 直接不显示（Q4：这是数据事实，不伪造、不标注缺口）。
const MIN_CONFIRMED_BARS = 5

export function computeChanOverlay(chartData: (CandleItem & { time: Time })[]): ChanOverlayResult {
  const confirmed = chartData.filter((item) => item.confirm === '1')
  if (confirmed.length < MIN_CONFIRMED_BARS) return EMPTY_RESULT

  const bars: RawBar[] = confirmed.map((item, index) => ({
    index,
    ts: 0,
    open: Number(item.o),
    high: Number(item.h),
    low: Number(item.l),
    close: Number(item.c),
  }))

  const analysis = analyzeChan(bars)
  const timeAt = (rawIndex: number): Time => confirmed[rawIndex].time

  const boxes: ChanZhongshuBox[] = analysis.zhongshu.map((zhongshu) => ({
    startTime: timeAt(zhongshu.startIndex),
    endTime: timeAt(zhongshu.endIndex),
    zg: zhongshu.zg,
    zd: zhongshu.zd,
  }))

  // 笔是链式的：stroke[i].end 就是 stroke[i+1].start（同一个分型对象），
  // 所以连线只需要 [第一笔起点, 第一笔终点, 第二笔终点, ...]。
  const strokePoints: ChanStrokeSegment[] = []
  analysis.strokes.forEach((stroke, index) => {
    if (index === 0) strokePoints.push({ time: timeAt(stroke.start.index), price: stroke.start.price })
    strokePoints.push({ time: timeAt(stroke.end.index), price: stroke.end.price })
  })

  const markers: SeriesMarker<Time>[] = []
  for (const fractal of analysis.fractals) {
    markers.push({
      time: timeAt(fractal.index),
      position: fractal.kind === 'top' ? 'aboveBar' : 'belowBar',
      shape: fractal.kind === 'top' ? 'arrowDown' : 'arrowUp',
      color: 'rgba(148, 163, 184, 0.9)',
      size: 0.6,
      id: `fractal-${fractal.kind}-${fractal.index}`,
    })
  }
  for (const divergence of analysis.divergences) {
    const isExhaustion = divergence.kind === 'top_exhaustion' || divergence.kind === 'bottom_exhaustion'
    const isTop = divergence.kind === 'top_exhaustion' || divergence.kind === 'top_divergence'
    markers.push({
      time: timeAt(divergence.index),
      position: isTop ? 'aboveBar' : 'belowBar',
      shape: 'square',
      // 背驰（BC）用醒目橙红色实心方块；背离（DIV）用同色系但更淡，视觉上明显区分强度。
      color: isExhaustion ? 'rgba(249, 115, 22, 0.95)' : 'rgba(249, 115, 22, 0.35)',
      size: isExhaustion ? 1.4 : 0.9,
      id: `divergence-${divergence.kind}-${divergence.index}`,
      text: isExhaustion ? (isTop ? 'BC-S' : 'BC-B') : (isTop ? 'DIV-S' : 'DIV-B'),
    })
  }
  markers.sort((a, b) => (a.time as number) - (b.time as number))

  return { boxes, strokePoints, markers }
}
