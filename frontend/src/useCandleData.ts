import { useEffect, useRef, useState } from 'react'
import { getCandles } from './api'
import { candleWindowMs, mergeCandles } from './candleData'
import type { CandleItem, TradeBar } from './types'

// 调用方按 instId/kind/bar 设置组件 key：每个数据集拥有独立状态和请求生命周期。
export function useCandleData(instId: string, kind: 'trade' | 'mark', bar: TradeBar, live: CandleItem | null) {
  const [items, setItems] = useState<CandleItem[]>([])
  const [loading, setLoading] = useState(true)
  const bufferedLive = useRef(new Map<number, CandleItem>())

  useEffect(() => {
    const controller = new AbortController()
    let inFlight = false
    async function loadHistory() {
      if (inFlight || controller.signal.aborted) return
      inFlight = true
      bufferedLive.current.clear()
      let before: number | undefined
      let cutoff: number | undefined
      try {
        while (!controller.signal.aborted) {
          const response = await getCandles(instId, kind, bar, 300, { before, signal: controller.signal })
          if (controller.signal.aborted || response.items.length === 0) break
          const page = mergeCandles([], response.items)
          // REST 修正先前遗留的未闭合高低/收盘价，覆盖旧状态；只有请求期间
          // 到达的 WS 才优先于本次响应。不能让所有旧 current 永远盖过回填结果。
          const updates = [...bufferedLive.current.values()]
          setItems(current => mergeCandles(mergeCandles(current, page), updates))
          cutoff ??= page.at(-1)!.ts - candleWindowMs(bar)
          const oldest = page[0].ts
          // 单页 300 根秒线不足 2 小时；只向本产品历史接口补取默认窗口。
          if (bar !== '1s' || oldest <= cutoff || page.length < 300 || (before !== undefined && oldest >= before)) break
          before = oldest
        }
      } catch {
        // 历史暂不可用时保留已收到的数据，实时更新继续使用同一份状态。
      } finally {
        inFlight = false
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void loadHistory()
    const refresh = () => { if (!document.hidden) void loadHistory() }
    // 后端回填/断线补数完成后，已打开的图表也必须重新读取；仅靠最新一根 WS
    // 快照无法补回断线期间的中间 K 线。这里只连接本产品后端，不直接访问 OKX。
    const timer = window.setInterval(refresh, 30_000)
    window.addEventListener('focus', refresh)
    window.addEventListener('online', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      controller.abort()
      window.clearInterval(timer)
      window.removeEventListener('focus', refresh)
      window.removeEventListener('online', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [instId, kind, bar])

  useEffect(() => {
    // 外部实时流只暴露最新一根；必须累积到历史状态，不能仅从当前 props 派生。
    if (live) {
      bufferedLive.current.set(live.ts, live)
      // oxlint-disable-next-line react/set-state-in-effect
      setItems(current => mergeCandles(current, [live]))
    }
  }, [live])

  return { items, loading }
}
