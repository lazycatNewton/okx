import { useEffect, useState } from 'react'
import { marketDataStore, type ProductRealtimeState } from './marketDataStore'

/** 只读取 marketDataStore 的规范化状态；组件本身不管理 WebSocket 连接。 */
export function useProductRealtime(instId: string | null): ProductRealtimeState | null {
  const [, forceRender] = useState(0)

  useEffect(() => {
    const unsubscribe = marketDataStore.subscribe(() => forceRender((n) => n + 1))
    return unsubscribe
  }, [])

  useEffect(() => {
    if (!instId) return
    marketDataStore.activateProduct(instId)
    return () => marketDataStore.deactivateProduct(instId)
  }, [instId])

  if (!instId) return null
  return marketDataStore.getProductState(instId)
}

export function useRealtimeConnected(): boolean {
  const [connected, setConnected] = useState(marketDataStore.isConnected())
  useEffect(() => {
    return marketDataStore.subscribe(() => setConnected(marketDataStore.isConnected()))
  }, [])
  return connected
}
