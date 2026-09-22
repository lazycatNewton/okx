import { useEffect, useMemo, useRef, useState } from 'react'
import { ColorType, createChart, LineSeries, type IChartApi, type ISeriesApi, type Time } from 'lightweight-charts'
import { getM25Stat, getS04Unit, setS04Unit } from '../api'
import { formatDecimal } from '../detailDisplay'
import { chartTimeInEt, formatChartTick, formatChartTime } from '../time'
import type { M25Period, M25StatItem, S04Unit } from '../types'

const S01_S04_S05_PERIODS: M25Period[] = ['5m', '15m', '1D']
const S04_UNITS: { value: S04Unit; label: string }[] = [
  { value: '0', label: '币' },
  { value: '1', label: '合约' },
  { value: '2', label: 'U' },
]

function dedupeAndSort(items: M25StatItem[]): { time: Time; value: number }[] {
  const byTime = new Map<number, number>()
  for (const item of items) {
    const value = Number((item.longShortAcctRatio ?? item.oi ?? item.buyVol) as string)
    if (Number.isFinite(value)) byTime.set(chartTimeInEt(item.ts), value)
  }
  return [...byTime.entries()].sort(([a], [b]) => a - b).map(([time, value]) => ({ time: time as Time, value }))
}

/** S01/S05 单值统计的小图表：多空比 / 持仓量。 */
function StatLineChart({
  title, queryKey, metric, period, valueKey,
}: {
  title: string
  queryKey: string
  metric: 'S01' | 'S05'
  period: string
  valueKey: string
}) {
  const [items, setItems] = useState<M25StatItem[]>([])
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    let cancelled = false
    getM25Stat(queryKey, metric, { period, limit: 100 }).then((res) => {
      if (!cancelled) setItems(res.items)
    })
    return () => { cancelled = true }
  }, [queryKey, metric, period])

  const chartData = useMemo(() => dedupeAndSort(items), [items])
  const latest = items.at(-1)

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const chart = createChart(element, {
      autoSize: true,
      height: 140,
      layout: { background: { type: ColorType.Solid, color: '#111827' }, textColor: '#cbd5e1' },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      rightPriceScale: { borderColor: '#334155' },
      localization: { timeFormatter: formatChartTime },
      timeScale: { borderColor: '#334155', timeVisible: true, tickMarkFormatter: formatChartTick },
    })
    chartRef.current = chart
    seriesRef.current = chart.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 2 })
    return () => { chart.remove(); chartRef.current = null; seriesRef.current = null }
  }, [])

  useEffect(() => {
    seriesRef.current?.setData(chartData)
    chartRef.current?.timeScale().fitContent()
  }, [chartData])

  return (
    <div className="m25-stat">
      <div className="m25-stat-header">
        <h4>{title}</h4>
        {latest && <span className="m25-stat-latest">{String(latest[valueKey] ?? '')}</span>}
      </div>
      <div ref={containerRef} className="lightweight-chart m25-chart" />
    </div>
  )
}

/** S04 主动买卖量：需要单位选择器（0 币/1 合约/2 U），持久化每个产品最近一次选择。
 * 展示位置与 M01（Ticker）同一行，因此自带周期选择器，不依赖 M25Panel 的 period 状态。 */
export function S04Chart({ instId }: { instId: string }) {
  const [period, setPeriod] = useState<M25Period>('5m')
  const [unit, setUnit] = useState<S04Unit>('1')
  const [items, setItems] = useState<M25StatItem[]>([])

  useEffect(() => {
    getS04Unit(instId).then((res) => setUnit((res.unit as S04Unit) ?? '1'))
  }, [instId])

  useEffect(() => {
    let cancelled = false
    getM25Stat(instId, 'S04', { period, unit, limit: 100 }).then((res) => {
      if (!cancelled) setItems(res.items)
    })
    return () => { cancelled = true }
  }, [instId, period, unit])

  async function handleUnitChange(next: S04Unit) {
    setUnit(next)
    await setS04Unit(instId, next)
  }

  const latest = items.at(-1)

  return (
    <section className="panel numeric-card">
      <div className="panel-heading">
        <h3>S04 · 主动买卖量</h3>
        <div className="bar-selector">
          {S01_S04_S05_PERIODS.map((p) => (
            <button key={p} className={p === period ? 'active' : ''} onClick={() => setPeriod(p)}>{p}</button>
          ))}
        </div>
      </div>
      <div className="unit-selector">
        {S04_UNITS.map((u) => (
          <button key={u.value} className={u.value === unit ? 'active' : ''} onClick={() => handleUnitChange(u.value)}>
            {u.label}
          </button>
        ))}
      </div>
      {period === '1D' && <p className="bar-hint">日线按纽约自然日（00:00 ET）划分</p>}
      {latest ? (
        <div className="m25-stat-grid">
          <div>买入量：{formatDecimal(latest.buyVol)}</div>
          <div>卖出量：{formatDecimal(latest.sellVol)}</div>
        </div>
      ) : <p className="empty-hint">暂无数据</p>}
    </section>
  )
}

/** M25 补充统计面板：S01/S05，均按该永续产品的 instId 查询（S04 见 S04Chart）。 */
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
      {/* S01/S05 的 1D 取纽约自然日 00:00 的读数；见后端 ny_day.py。S04 已上移至与 M01
          同一行的 S04Chart（见 ProductPanel.tsx），自带独立周期选择器。 */}
      {period === '1D' && <p className="bar-hint">日线按纽约自然日（00:00 ET）划分</p>}
      <StatLineChart title="S01 · 多空持仓人数比" queryKey={instId} metric="S01" period={period} valueKey="longShortAcctRatio" />
      <StatLineChart title="S05 · 持仓量历史" queryKey={instId} metric="S05" period={period} valueKey="oi" />
    </section>
  )
}
