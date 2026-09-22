// 缠论（缠中说禅）结构分析：包含处理 → 分型 → 笔 → 中枢 → 背离/背驰。
// 移植自 /Users/lazycatnewton/development-repo/skills/chan/scripts/chan_core.py
// （信号/买卖点判定不在本次移植范围内，见项目 grilling 记录：只需要中枢/笔/分型/背驰）。
//
// 与原 Python 实现的对应关系：
// - KBar            -> RawBar（复用项目已有的 CandleItem 转换而来）
// - AnalysisKBar     -> AnalysisBar（包含处理后的分析 K 线）
// - Fractal          -> Fractal
// - Stroke           -> Stroke
// - Zhongshu         -> Zhongshu
// - MacdPoint        -> MacdPoint
// - Divergence       -> Divergence（DIV 观察 / BC 背驰近似标记）
//
// 只使用已闭合 K 线（confirm==='1'）参与计算：分型判定需要"确认"、避免结构随实时数据抖动。

export interface RawBar {
  index: number
  ts: number
  open: number
  high: number
  low: number
  close: number
}

export interface AnalysisBar {
  index: number
  startIndex: number
  endIndex: number
  highIndex: number
  lowIndex: number
  open: number
  high: number
  low: number
  close: number
}

export type FractalKind = 'top' | 'bottom'
export type StrokeDirection = 'up' | 'down'
export type DivergenceKind = 'top_divergence' | 'bottom_divergence' | 'top_exhaustion' | 'bottom_exhaustion'

export interface Fractal {
  kind: FractalKind
  analysisIndex: number
  index: number // 原始 K 线索引（分型真实高/低点所在的那根原始 K 线）
  price: number
  high: number
  low: number
}

export interface Stroke {
  start: Fractal
  end: Fractal
  direction: StrokeDirection
  startIndex: number
  endIndex: number
  high: number
  low: number
}

export interface Zhongshu {
  startStrokeIndex: number
  endStrokeIndex: number
  startIndex: number // 原始 K 线索引：中枢起点
  endIndex: number // 原始 K 线索引：中枢终点
  zd: number
  zg: number
  gg: number
  dd: number
}

export interface MacdPoint {
  index: number
  dif: number
  dea: number
  hist: number
}

export interface Divergence {
  kind: DivergenceKind
  index: number // 原始 K 线索引
  price: number
}

export interface ChanAnalysis {
  analysisBars: AnalysisBar[]
  fractals: Fractal[]
  strokes: Stroke[]
  zhongshu: Zhongshu[]
  divergences: Divergence[]
}

function analysisBarFromRaw(bar: RawBar, index: number): AnalysisBar {
  return {
    index,
    startIndex: bar.index,
    endIndex: bar.index,
    highIndex: bar.index,
    lowIndex: bar.index,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
  }
}

function kbarDirection(left: AnalysisBar, right: AnalysisBar): StrokeDirection | null {
  if (right.high > left.high && right.low > left.low) return 'up'
  if (right.high < left.high && right.low < left.low) return 'down'
  return null
}

function hasInclusion(left: AnalysisBar, right: AnalysisBar): boolean {
  const leftContainsRight = left.high >= right.high && left.low <= right.low
  const rightContainsLeft = right.high >= left.high && right.low <= left.low
  return leftContainsRight || rightContainsLeft
}

function initialMergeDirection(left: AnalysisBar, right: AnalysisBar): StrokeDirection {
  if (right.close !== left.close) return right.close > left.close ? 'up' : 'down'
  const leftMid = (left.high + left.low) / 2
  const rightMid = (right.high + right.low) / 2
  return rightMid >= leftMid ? 'up' : 'down'
}

function mergeDirection(
  analysisBars: AnalysisBar[],
  incoming: AnalysisBar,
  lastDirection: StrokeDirection | null,
): StrokeDirection {
  if (analysisBars.length >= 2) {
    const direction = kbarDirection(analysisBars[analysisBars.length - 2], analysisBars[analysisBars.length - 1])
    if (direction !== null) return direction
  }
  if (lastDirection !== null) return lastDirection
  return initialMergeDirection(analysisBars[analysisBars.length - 1], incoming)
}

function highSource(left: AnalysisBar, right: AnalysisBar, high: number): number {
  return left.high === high ? left.highIndex : right.highIndex
}

function lowSource(left: AnalysisBar, right: AnalysisBar, low: number): number {
  return left.low === low ? left.lowIndex : right.lowIndex
}

function mergeInclusionBars(left: AnalysisBar, right: AnalysisBar, direction: StrokeDirection): AnalysisBar {
  let high: number
  let low: number
  if (direction === 'up') {
    high = Math.max(left.high, right.high)
    low = Math.max(left.low, right.low)
  } else {
    high = Math.min(left.high, right.high)
    low = Math.min(left.low, right.low)
  }
  return {
    index: left.index,
    startIndex: left.startIndex,
    endIndex: right.endIndex,
    highIndex: highSource(left, right, high),
    lowIndex: lowSource(left, right, low),
    open: left.open,
    high,
    low,
    close: right.close,
  }
}

function reindexAnalysisBars(bars: AnalysisBar[]): AnalysisBar[] {
  return bars.map((bar, index) => ({ ...bar, index }))
}

/** 包含处理：对应 chan_core.py 的 map_kbars。 */
export function mapKBars(bars: RawBar[]): AnalysisBar[] {
  const analysisBars: AnalysisBar[] = []
  let lastDirection: StrokeDirection | null = null

  for (const bar of bars) {
    const current = analysisBarFromRaw(bar, analysisBars.length)
    if (analysisBars.length === 0) {
      analysisBars.push(current)
      continue
    }
    const previous = analysisBars[analysisBars.length - 1]
    if (hasInclusion(previous, current)) {
      const direction = mergeDirection(analysisBars, current, lastDirection)
      analysisBars[analysisBars.length - 1] = mergeInclusionBars(previous, current, direction)
      lastDirection = direction
      continue
    }
    const direction = kbarDirection(previous, current)
    if (direction !== null) lastDirection = direction
    analysisBars.push(current)
  }

  return reindexAnalysisBars(analysisBars)
}

/** 分型识别：对应 chan_core.py 的 detect_fractals。 */
export function detectFractals(analysisBars: AnalysisBar[]): Fractal[] {
  const candidates: Fractal[] = []
  for (let index = 1; index < analysisBars.length - 1; index += 1) {
    const left = analysisBars[index - 1]
    const middle = analysisBars[index]
    const right = analysisBars[index + 1]

    const isTop = middle.high >= Math.max(left.high, right.high) && middle.low >= Math.max(left.low, right.low)
    const isBottom = middle.low <= Math.min(left.low, right.low) && middle.high <= Math.min(left.high, right.high)

    if (isTop) {
      candidates.push({
        kind: 'top',
        analysisIndex: index,
        index: middle.highIndex,
        price: middle.high,
        high: middle.high,
        low: middle.low,
      })
    } else if (isBottom) {
      candidates.push({
        kind: 'bottom',
        analysisIndex: index,
        index: middle.lowIndex,
        price: middle.low,
        high: middle.high,
        low: middle.low,
      })
    }
  }

  const filtered: Fractal[] = []
  for (const fractal of candidates) {
    const last = filtered[filtered.length - 1]
    if (!last || last.kind !== fractal.kind) {
      filtered.push(fractal)
      continue
    }
    if (fractal.kind === 'top' && fractal.price > last.price) filtered[filtered.length - 1] = fractal
    else if (fractal.kind === 'bottom' && fractal.price < last.price) filtered[filtered.length - 1] = fractal
  }
  return filtered
}

/** 笔检测：对应 chan_core.py 的 detect_strokes。 */
export function detectStrokes(fractals: Fractal[], minBasicBars = 3): Stroke[] {
  const strokes: Stroke[] = []
  if (fractals.length === 0) return strokes

  const strongerSameKind = (candidate: Fractal, reference: Fractal): boolean =>
    candidate.kind === 'top' ? candidate.price > reference.price : candidate.price < reference.price

  const buildStroke = (start: Fractal, end: Fractal): Stroke => {
    const direction: StrokeDirection = start.kind === 'bottom' && end.kind === 'top' ? 'up' : 'down'
    return {
      start,
      end,
      direction,
      startIndex: start.index,
      endIndex: end.index,
      high: Math.max(start.price, end.price),
      low: Math.min(start.price, end.price),
    }
  }

  let start = fractals[0]
  for (const end of fractals.slice(1)) {
    if (end.kind === start.kind) {
      if (strongerSameKind(end, start)) {
        if (strokes.length > 0) strokes[strokes.length - 1] = buildStroke(strokes[strokes.length - 1].start, end)
        start = end
      }
      continue
    }
    if (end.analysisIndex - start.analysisIndex + 1 < minBasicBars) continue
    strokes.push(buildStroke(start, end))
    start = end
  }

  return strokes
}

/** 中枢构建：对应 chan_core.py 的 detect_zhongshu。 */
export function detectZhongshu(strokes: Stroke[]): Zhongshu[] {
  const centers: Zhongshu[] = []
  let index = 0
  while (index + 2 < strokes.length) {
    const group = strokes.slice(index, index + 3)
    const zg = Math.min(...group.map((s) => s.high))
    const zd = Math.max(...group.map((s) => s.low))
    if (zg <= zd) {
      index += 1
      continue
    }

    let endStrokeIndex = index + 2
    let gg = Math.max(...group.map((s) => s.high))
    let dd = Math.min(...group.map((s) => s.low))
    let currentZg = zg
    let currentZd = zd

    let probe = endStrokeIndex + 1
    while (probe < strokes.length) {
      const nextZg = Math.min(currentZg, strokes[probe].high)
      const nextZd = Math.max(currentZd, strokes[probe].low)
      if (nextZg <= nextZd) break
      currentZg = nextZg
      currentZd = nextZd
      gg = Math.max(gg, strokes[probe].high)
      dd = Math.min(dd, strokes[probe].low)
      endStrokeIndex = probe
      probe += 1
    }

    centers.push({
      startStrokeIndex: index,
      endStrokeIndex,
      startIndex: strokes[index].startIndex,
      endIndex: strokes[endStrokeIndex].endIndex,
      zd: currentZd,
      zg: currentZg,
      gg,
      dd,
    })
    index = endStrokeIndex + 1
  }
  return centers
}

function ema(values: number[], period: number): number[] {
  if (values.length === 0) return []
  const alpha = 2 / (period + 1)
  const result = [values[0]]
  for (const value of values.slice(1)) {
    result.push(alpha * value + (1 - alpha) * result[result.length - 1])
  }
  return result
}

/** MACD：对应 chan_core.py 的 calculate_macd。 */
export function calculateMacd(bars: RawBar[], fast = 12, slow = 26, signal = 9): MacdPoint[] {
  const closes = bars.map((b) => b.close)
  const emaFast = ema(closes, fast)
  const emaSlow = ema(closes, slow)
  const difValues = emaFast.map((v, i) => v - emaSlow[i])
  const deaValues = ema(difValues, signal)
  return bars.map((bar, i) => ({
    index: bar.index,
    dif: difValues[i],
    dea: deaValues[i],
    hist: 2 * (difValues[i] - deaValues[i]),
  }))
}

function macdArea(macd: MacdPoint[], startIndex: number, endIndex: number, direction: StrokeDirection): number {
  const lo = Math.min(startIndex, endIndex)
  const hi = Math.max(startIndex, endIndex)
  const segment = macd.slice(lo, hi + 1)
  if (direction === 'up') return segment.reduce((sum, p) => sum + Math.max(p.hist, 0), 0)
  return Math.abs(segment.reduce((sum, p) => sum + Math.min(p.hist, 0), 0))
}

/** 背离/背驰：对应 chan_core.py 的 detect_divergences。 */
export function detectDivergences(
  fractals: Fractal[],
  strokes: Stroke[],
  centers: Zhongshu[],
  macd: MacdPoint[],
): Divergence[] {
  const divergences: Divergence[] = []
  let lastTop: Fractal | null = null
  let lastBottom: Fractal | null = null
  const centerCount = centers.length

  for (const fractal of fractals) {
    const point = macd[fractal.index]
    if (!point) continue
    if (fractal.kind === 'top') {
      if (lastTop !== null) {
        const previous = macd[lastTop.index]
        if (previous && fractal.price > lastTop.price && point.dif < previous.dif) {
          const kind: DivergenceKind = centerCount >= 2 ? 'top_exhaustion' : 'top_divergence'
          divergences.push({ kind, index: fractal.index, price: fractal.price })
        }
      }
      lastTop = fractal
    } else {
      if (lastBottom !== null) {
        const previous = macd[lastBottom.index]
        if (previous && fractal.price < lastBottom.price && point.dif > previous.dif) {
          const kind: DivergenceKind = centerCount >= 2 ? 'bottom_exhaustion' : 'bottom_divergence'
          divergences.push({ kind, index: fractal.index, price: fractal.price })
        }
      }
      lastBottom = fractal
    }
  }

  if (centerCount >= 2) {
    const sameDirection: Partial<Record<StrokeDirection, Stroke>> = {}
    for (const stroke of strokes) {
      const previous = sameDirection[stroke.direction]
      if (previous) {
        const previousArea = macdArea(macd, previous.startIndex, previous.endIndex, previous.direction)
        const currentArea = macdArea(macd, stroke.startIndex, stroke.endIndex, stroke.direction)
        if (currentArea < previousArea) {
          if (stroke.direction === 'up' && stroke.end.price > previous.end.price) {
            divergences.push({ kind: 'top_exhaustion', index: stroke.endIndex, price: stroke.end.price })
          } else if (stroke.direction === 'down' && stroke.end.price < previous.end.price) {
            divergences.push({ kind: 'bottom_exhaustion', index: stroke.endIndex, price: stroke.end.price })
          }
        }
      }
      sameDirection[stroke.direction] = stroke
    }
  }

  const deduped = new Map<string, Divergence>()
  for (const divergence of divergences) deduped.set(`${divergence.kind}:${divergence.index}`, divergence)
  return [...deduped.values()].sort((a, b) => a.index - b.index || a.kind.localeCompare(b.kind))
}

/** 完整分析入口：对应 chan_core.py 的 analyze_chan（不含买卖点判定，见模块注释）。 */
export function analyzeChan(bars: RawBar[]): ChanAnalysis {
  const analysisBars = mapKBars(bars)
  const fractals = detectFractals(analysisBars)
  const strokes = detectStrokes(fractals)
  const zhongshu = detectZhongshu(strokes)
  const macd = calculateMacd(bars)
  const divergences = detectDivergences(fractals, strokes, zhongshu, macd)
  return { analysisBars, fractals, strokes, zhongshu, divergences }
}
