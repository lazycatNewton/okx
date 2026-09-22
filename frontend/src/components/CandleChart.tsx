import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
} from 'lightweight-charts'
import { candlePriceFormat, candleWindowMs } from '../candleData'
import { computeChanOverlay, isChanEnabledForBar, type ChanKind } from '../chanOverlay'
import { ChanStrokePrimitive, ChanZhongshuPrimitive } from '../chanPrimitives'
import { buildCandleLegend } from '../chartDisplay'
import type { ProductRealtimeState } from '../marketDataStore'
import { chartTimeInEt, formatChartTick, formatChartTime } from '../time'
import { useCandleData } from '../useCandleData'
import type { CandleItem, TradeBar } from '../types'

const TRADE_BARS: TradeBar[] = ['1s', '1m', '5m', '15m', '30m', '1D']
const MARK_BARS: TradeBar[] = ['1m', '5m', '15m', '30m', '1D']

interface GenericCandleChartProps {
  instId: string
  realtime: ProductRealtimeState
  kind: ChanKind
  title: string
  defaultBar: TradeBar
  bars: TradeBar[]
  ariaLabelPrefix: string
}

function GenericCandleChart(props: GenericCandleChartProps) {
  const [bar, setBar] = useState<TradeBar>(props.defaultBar)
  return <CandleChartView key={`${props.instId}:${props.kind}:${bar}`} {...props} bar={bar} setBar={setBar} />
}

type ChartCandle = CandleItem & { time: Time }

function CandleChartView({ instId, realtime, kind, title, bar, setBar, bars, ariaLabelPrefix }: GenericCandleChartProps & {
  bar: TradeBar
  setBar: (bar: TradeBar) => void
}) {
  const live = realtime.candles[`candle:${kind}:${bar}`]?.data ?? null
  const { items, loading } = useCandleData(instId, kind, bar, live)
  const [hoveredTime, setHoveredTime] = useState<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | ISeriesApi<'Line'> | null>(null)
  const zhongshuPrimitiveRef = useRef<ChanZhongshuPrimitive | null>(null)
  const strokePrimitiveRef = useRef<ChanStrokePrimitive | null>(null)
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const renderedDataRef = useRef<ChartCandle[]>([])
  const defaultRangeAppliedRef = useRef(false)

  const chartData = useMemo(() => {
    // Lightweight Charts 要求 time 严格递增；API/回补和实时更新交错时可能出现
    // 同一秒的重复记录，因此按真实 UTC 时间去重；纽约时区只用于标签。
    const byTime = new Map<number, CandleItem>()
    for (const item of items) byTime.set(chartTimeInEt(item.ts), item)
    return [...byTime.entries()]
      .sort(([left], [right]) => left - right)
      .map(([time, item]) => ({ ...item, time: time as Time }))
  }, [items])

  const chanEnabled = isChanEnabledForBar(kind, bar)
  const chanOverlay = useMemo(
    () => (chanEnabled ? computeChanOverlay(chartData) : { boxes: [], strokePoints: [], markers: [] }),
    [chanEnabled, chartData],
  )

  const hoveredItem = chartData.find(item => item.time === hoveredTime)
  const hoveredCandle = hoveredItem ? buildCandleLegend(hoveredItem) : null

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const chart = createChart(element, {
      autoSize: true,
      height: 310,
      layout: { background: { type: ColorType.Solid, color: '#111827' }, textColor: '#cbd5e1' },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      crosshair: { mode: 1 },
      localization: { timeFormatter: formatChartTime },
      rightPriceScale: { borderColor: '#334155' },
      timeScale: {
        borderColor: '#334155', timeVisible: true, secondsVisible: bar === '1s',
        tickMarkFormatter: formatChartTick,
        // 秒线的两小时包含约 7200 个点，默认 0.5px 下限会截短可见窗口。
        minBarSpacing: bar === '1s' ? 0.01 : 0.5,
      },
    })
    chartRef.current = chart
    const series = bar === '1s'
      ? chart.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 2 })
      : chart.addSeries(CandlestickSeries, { upColor: '#22c55e', downColor: '#ef4444', borderVisible: false, wickUpColor: '#22c55e', wickDownColor: '#ef4444' })
    seriesRef.current = series

    const zhongshuPrimitive = new ChanZhongshuPrimitive()
    const strokePrimitive = new ChanStrokePrimitive()
    series.attachPrimitive(zhongshuPrimitive)
    series.attachPrimitive(strokePrimitive)
    zhongshuPrimitiveRef.current = zhongshuPrimitive
    strokePrimitiveRef.current = strokePrimitive
    markersPluginRef.current = createSeriesMarkers(series, [])

    const handleCrosshairMove = (param: { time?: Time }) => {
      setHoveredTime(typeof param.time === 'number' ? param.time : null)
    }
    chart.subscribeCrosshairMove(handleCrosshairMove)

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove)
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      zhongshuPrimitiveRef.current = null
      strokePrimitiveRef.current = null
      markersPluginRef.current = null
      renderedDataRef.current = []
      defaultRangeAppliedRef.current = false
    }
  }, [bar])

  useEffect(() => {
    const series = seriesRef.current
    const chart = chartRef.current
    if (!series || !chart) return
    if (chartData.length) series.applyOptions({ priceFormat: candlePriceFormat(chartData) })
    const previous = renderedDataRef.current
    const previousByTime = new Map(previous.map(item => [item.time, item]))
    const lastTime = (previous.at(-1)?.time ?? -Infinity) as number
    const needsReset = previous.length === 0 || chartData.some(item => !previousByTime.has(item.time) && (item.time as number) < lastTime)

    if (needsReset) {
      const visible = defaultRangeAppliedRef.current ? chart.timeScale().getVisibleLogicalRange() : null
      if (bar === '1s') {
        ;(series as ISeriesApi<'Line'>).setData(chartData.map(item => ({ time: item.time, value: Number(item.c) })))
      } else {
        ;(series as ISeriesApi<'Candlestick'>).setData(chartData.map(item => ({ time: item.time, open: Number(item.o), high: Number(item.h), low: Number(item.l), close: Number(item.c) })))
      }
      if (visible && previous.length) {
        // 补入较早时间点会改变逻辑索引；以原可见边界对应的时间锚点保留视图。
        const indexes = new Map(chartData.map((item, index) => [item.time, index]))
        const remap = (value: number) => {
          const anchor = Math.max(0, Math.min(previous.length - 1, Math.floor(value)))
          return (indexes.get(previous[anchor].time) ?? anchor) + value - anchor
        }
        chart.timeScale().setVisibleLogicalRange({ from: remap(visible.from), to: remap(visible.to) })
      }
    } else {
      for (const item of chartData) {
        const old = previousByTime.get(item.time)
        if (old && old.o === item.o && old.h === item.h && old.l === item.l && old.c === item.c) continue
        const historical = (item.time as number) < lastTime
        if (bar === '1s') {
          ;(series as ISeriesApi<'Line'>).update({ time: item.time, value: Number(item.c) }, historical)
        } else {
          ;(series as ISeriesApi<'Candlestick'>).update({ time: item.time, open: Number(item.o), high: Number(item.h), low: Number(item.l), close: Number(item.c) }, historical)
        }
      }
    }
    renderedDataRef.current = chartData
    if (!loading && chartData.length && !defaultRangeAppliedRef.current) {
      const latest = chartData.at(-1)!
      chart.timeScale().setVisibleRange({ from: chartTimeInEt(latest.ts - candleWindowMs(bar)) as Time, to: latest.time })
      defaultRangeAppliedRef.current = true
    }
  }, [bar, chartData, loading])

  useEffect(() => {
    zhongshuPrimitiveRef.current?.setBoxes(chanOverlay.boxes)
    strokePrimitiveRef.current?.setPoints(chanOverlay.strokePoints)
    markersPluginRef.current?.setMarkers(chanOverlay.markers)
    chartRef.current?.timeScale().applyOptions({}) // 触发重绘
  }, [chanOverlay])

  return (
    <section className="panel candle-chart" aria-busy={loading}>
      <div className="candle-chart-header">
        <h3>{title}</h3>
        <div className="bar-selector">
          {bars.map((value) => <button key={value} className={value === bar ? 'active' : ''} onClick={() => setBar(value)}>{value}</button>)}
        </div>
      </div>
      {/* OKX 的 1D 是 UTC+8 开盘口径；本产品的日线由官方 1H 在后端按纽约自然日重采样，
          这里明确标注口径，避免与交易所页面上的日线逐根对不上时产生误解。 */}
      {bar === '1D' && <p className="bar-hint">日线按纽约自然日（00:00 ET）划分</p>}
      <div className="candle-ohlc-legend" aria-live="polite">
        {hoveredCandle ? (
          <>
            <span>收盘 <strong>{hoveredCandle.close}</strong></span>
            <span>开盘 <strong>{hoveredCandle.open}</strong></span>
            <span>最高 <strong>{hoveredCandle.high}</strong></span>
            <span>最低 <strong>{hoveredCandle.low}</strong></span>
          </>
        ) : <span className="candle-ohlc-placeholder">移动光标查看 OHLC</span>}
      </div>
      {loading && items.length === 0 && <p className="empty-hint">加载中…</p>}
      {/* 保留布局尺寸，避免 display:none 使自动宽度为零、首次时间范围随后被拉伸。 */}
      <div ref={containerRef} className="lightweight-chart" aria-label={bar === '1s' ? `${ariaLabelPrefix}秒级价格折线图` : `${ariaLabelPrefix}K线图`} style={{ visibility: loading && items.length === 0 ? 'hidden' : undefined }} />
      {!loading && chanEnabled && chanOverlay.boxes.length === 0 && items.length > 0 && (
        <p className="empty-hint chan-hint">当前数据暂不足以形成缠论中枢（数据事实，非缺陷）</p>
      )}
      <p className="chart-attribution">Chart by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView</a></p>
    </section>
  )
}

export function CandleChart({ instId, realtime }: { instId: string; realtime: ProductRealtimeState }) {
  return (
    <GenericCandleChart
      instId={instId}
      realtime={realtime}
      kind="trade"
      title="M02 · 成交价 K 线（ET）"
      defaultBar="5m"
      bars={TRADE_BARS}
      ariaLabelPrefix=""
    />
  )
}

export function MarkPriceChart({ instId, realtime }: { instId: string; realtime: ProductRealtimeState }) {
  return (
    <GenericCandleChart
      instId={instId}
      realtime={realtime}
      kind="mark"
      title="M11 · 标记价格 K 线（ET）"
      defaultBar="5m"
      bars={MARK_BARS}
      ariaLabelPrefix="标记价格"
    />
  )
}
