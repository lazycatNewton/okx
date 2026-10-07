import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ColorType, createChart, LineSeries, type IChartApi, type ISeriesApi, type Time } from 'lightweight-charts'
import { getM25Stat } from '../api'
import { formatDecimal } from '../detailDisplay'
import { chartTimeInEt, formatChartTick, formatChartTime } from '../time'
import type { M25Period, M25StatItem, S04Unit } from '../types'

const S01_S04_S05_PERIODS: M25Period[] = ['5m', '15m', '1D']
// S04 只采集并展示 `unit=2`（U）。
const S04_UNIT: S04Unit = '2'

// 后端保留官方每个粒度最多可取的 1,440 条，一次取全，图表展示完整保存窗口。
const M25_FETCH_LIMIT = 1440

interface LineSpec {
  field: string
  color: string
}

function toSeries(items: M25StatItem[], field: string): { time: Time; value: number }[] {
  const byTime = new Map<number, number>()
  for (const item of items) {
    const value = Number(item[field] as string)
    if (Number.isFinite(value)) byTime.set(chartTimeInEt(item.ts), value)
  }
  return [...byTime.entries()].sort(([a], [b]) => a - b).map(([time, value]) => ({ time: time as Time, value }))
}

/** M25 统计折线图：一张图可叠加多条线（S04 买入/卖出两条，S01/S05 各一条）。 */
function StatLineChart({ items, lines }: { items: M25StatItem[]; lines: LineSpec[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'>[]>([])
  const fields = lines.map((line) => line.field).join(',')
  const colors = lines.map((line) => line.color).join(',')

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const chart = createChart(element, {
      autoSize: true,
      height: 140,
      layout: { background: { type: ColorType.Solid, color: '#111827' }, textColor: '#cbd5e1' },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      rightPriceScale: { borderColor: '#334155' },
      handleScroll: { vertTouchDrag: false },
      localization: { timeFormatter: formatChartTime },
      timeScale: { borderColor: '#334155', timeVisible: true, tickMarkFormatter: formatChartTick },
    })
    chartRef.current = chart
    seriesRef.current = colors.split(',').map((color) => chart.addSeries(LineSeries, { color, lineWidth: 2 }))
    return () => { chart.remove(); chartRef.current = null; seriesRef.current = [] }
  }, [colors])

  useEffect(() => {
    fields.split(',').forEach((field, index) => seriesRef.current[index]?.setData(toSeries(items, field)))
    chartRef.current?.timeScale().fitContent()
  }, [items, fields, colors])

  return <div ref={containerRef} className="lightweight-chart m25-chart" />
}

function useM25Items(instId: string, metric: 'S01' | 'S04' | 'S05', period: M25Period, unit?: S04Unit) {
  const [items, setItems] = useState<M25StatItem[]>([])
  useEffect(() => {
    let cancelled = false
    getM25Stat(instId, metric, { period, unit, limit: M25_FETCH_LIMIT }).then((res) => {
      if (!cancelled) setItems(res.items)
    })
    return () => { cancelled = true }
  }, [instId, metric, period, unit])
  return items
}

function StatBlock({ title, latest, children }: { title: string; latest: ReactNode; children: ReactNode }) {
  return (
    <div className="m25-stat">
      <div className="m25-stat-header">
        <h4>{title}</h4>
        {latest}
      </div>
      {children}
    </div>
  )
}

/** S01/S05 单值统计：多空比 / 持仓量。 */
function SingleStat({
  title, instId, metric, period, field,
}: {
  title: string
  instId: string
  metric: 'S01' | 'S05'
  period: M25Period
  field: string
}) {
  const items = useM25Items(instId, metric, period)
  const lines = useMemo(() => [{ field, color: '#38bdf8' }], [field])
  const latest = items.at(-1)
  return (
    <StatBlock
      title={title}
      latest={latest && <span className="m25-stat-latest">{String(latest[field] ?? '')}</span>}
    >
      <StatLineChart items={items} lines={lines} />
    </StatBlock>
  )
}

const S04_LINES: LineSpec[] = [
  { field: 'buyVol', color: '#22c55e' },
  { field: 'sellVol', color: '#ef4444' },
]

/** S04 主动买卖量（单位 U）：买入/卖出两条折线。 */
function S04Stat({ instId, period }: { instId: string; period: M25Period }) {
  const items = useM25Items(instId, 'S04', period, S04_UNIT)
  const latest = items.at(-1)

  return (
    <StatBlock
      title="S04 · 主动买卖量（U）"
      latest={
        latest && (
          <span className="m25-stat-latest">
            <span className="s04-buy">买 {formatDecimal(latest.buyVol)}</span>
            <span className="s04-sell">卖 {formatDecimal(latest.sellVol)}</span>
          </span>
        )
      }
    >
      <StatLineChart items={items} lines={S04_LINES} />
    </StatBlock>
  )
}

/** M25 补充统计面板：S01、S04、S05 依次排列，共用周期选择，均按该永续产品的 instId 查询。 */
export function M25Panel({ instId }: { instId: string }) {
  const [period, setPeriod] = useState<M25Period>('5m')

  return (
    <section className="panel m25-panel">
      <div className="panel-heading">
        <h3>M25 · 补充统计（ET）</h3>
        <div className="bar-selector">
          {S01_S04_S05_PERIODS.map((p) => (
            <button key={p} className={p === period ? 'active' : ''} onClick={() => setPeriod(p)}>{p}</button>
          ))}
        </div>
      </div>
      {/* 1D 由后端按纽约自然日从官方 1H 派生：S01/S05 取日界读数，S04 按日求和；见 ny_day.py。 */}
      {period === '1D' && <p className="bar-hint">日线按纽约自然日（00:00 ET）划分</p>}
      <SingleStat title="S01 · 多空持仓人数比" instId={instId} metric="S01" period={period} field="longShortAcctRatio" />
      <S04Stat instId={instId} period={period} />
      <SingleStat title="S05 · 持仓量历史" instId={instId} metric="S05" period={period} field="oi" />
    </section>
  )
}
