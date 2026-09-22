import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { CandleChart } from '../../src/components/CandleChart'
import { chartTimeInEt } from '../../src/time'
import { computeChanOverlay } from '../../src/chanOverlay'
import '../../src/App.css'

// 此入口仅由测试服务器使用；图表 API 的观察点由测试 Vite 插件注入。
window.chartRecords = []
window.captureChart = (create, element, options) => {
  const chart = create(element, options)
  const record = { chart, series: [], primitives: [] }
  const addSeries = chart.addSeries.bind(chart)
  chart.addSeries = (...args) => {
    const series = addSeries(...args)
    const attach = series.attachPrimitive.bind(series)
    series.attachPrimitive = primitive => { record.primitives.push(primitive); attach(primitive) }
    record.series.push(series)
    return series
  }
  window.chartRecords.push(record)
  return chart
}
window.chartTimeInEt = chartTimeInEt
window.expectedOverlay = items => computeChanOverlay(items.map(item => ({ ...item, time: chartTimeInEt(item.ts) })))
const root = createRoot(document.getElementById('root'))
let props = { instId: 'FIRST-USDT', realtime: { candles: {} } }
window.renderChart = patch => {
  props = { ...props, ...patch }
  root.render(<StrictMode><CandleChart {...props} /></StrictMode>)
}
window.pushCandle = (bar, candle) => window.renderChart({
  realtime: { candles: { [`candle:trade:${bar}`]: { data: candle } } },
})
window.renderChart({})
