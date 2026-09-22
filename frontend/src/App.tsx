import { useEffect, useRef, useState } from 'react'
import { nextActiveProduct } from './productNavigation'
import { getBootstrap, logout, updateSelection } from './api'
import { AuxSidebar } from './components/AuxSidebar'
import { LoginScreen } from './components/LoginScreen'
import { ProductPanel } from './components/ProductPanel'
import { ProductSelector } from './components/ProductSelector'
import { ProductSidebar } from './components/ProductSidebar'
import { marketDataStore } from './marketDataStore'
import type { EconomicCalendarItem, EventContractMarketItem } from './types'
import './App.css'

export default function App() {
  const [username, setUsername] = useState<string | null>(null)
  const [selectedInstIds, setSelectedInstIds] = useState<string[]>([])
  const [activeInstId, setActiveInstId] = useState<string | null>(null)
  const [selectorOpen, setSelectorOpen] = useState(false)
  const [bootstrapped, setBootstrapped] = useState(false)
  const [productSidebarOpen, setProductSidebarOpen] = useState(false)
  const [removingProduct, setRemovingProduct] = useState(false)
  const removalLock = useRef(false)
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const [auxSidebarOpen, setAuxSidebarOpen] = useState(false)
  const [initialEventContractMarkets, setInitialEventContractMarkets] = useState<
    EventContractMarketItem[]
  >([])
  const [initialEconomicCalendar, setInitialEconomicCalendar] = useState<EconomicCalendarItem[]>(
    [],
  )

  useEffect(() => {
    // 尝试用已有会话 Cookie 直接恢复（登录后再刷新页面场景）。
    getBootstrap()
      .then((res) => {
        setUsername(res.username)
        setSelectedInstIds(res.selectedInstIds)
        setActiveInstId(res.lastActiveInstId)
        setInitialEventContractMarkets(res.auxSidebar.eventContractMarkets)
        setInitialEconomicCalendar(res.auxSidebar.economicCalendar)
      })
      .catch(() => {
        // 未登录：留在登录页
      })
      .finally(() => setBootstrapped(true))
  }, [])

  useEffect(() => {
    if (!username) return
    marketDataStore.connect()
    return () => marketDataStore.disconnect()
  }, [username])

  async function handleLoggedIn(name: string) {
    setUsername(name)
    const res = await getBootstrap()
    setSelectedInstIds(res.selectedInstIds)
    setActiveInstId(res.lastActiveInstId)
    setInitialEventContractMarkets(res.auxSidebar.eventContractMarkets)
    setInitialEconomicCalendar(res.auxSidebar.economicCalendar)
  }

  async function handleLogout() {
    await logout()
    setUsername(null)
    setSelectedInstIds([])
    setActiveInstId(null)
  }

  function handleSelectionChange(instIds: string[]) {
    setSelectedInstIds(instIds)
    setActiveInstId((current) => nextActiveProduct(selectedInstIds, instIds, current))
  }

  async function handleRemoveProduct(instId: string) {
    if (removalLock.current) return
    removalLock.current = true
    setRemovingProduct(true)
    setSelectionError(null)
    try {
      const result = await updateSelection(selectedInstIds.filter((id) => id !== instId))
      setSelectedInstIds(result.accepted)
      setActiveInstId((current) => nextActiveProduct(selectedInstIds, result.accepted, current))
    } catch (error) {
      setSelectionError(`取消选择失败：${error instanceof Error ? error.message : '请稍后重试'}`)
    } finally {
      removalLock.current = false
      setRemovingProduct(false)
    }
  }

  if (!bootstrapped) return null
  if (!username) return <LoginScreen onLoggedIn={handleLoggedIn} />

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-left">

          <h1>OKX 行情连接服务</h1>
        </div>
        <div className="app-header-right">
          <button onClick={() => setAuxSidebarOpen(true)}>市场/日历</button>
          <span>{username}</span>
          <button onClick={handleLogout}>退出</button>
        </div>
      </header>
      <button
        className={`product-sidebar-toggle${productSidebarOpen ? ' is-open' : ''}`}
        aria-label={productSidebarOpen ? '收起产品侧边栏' : '展开产品侧边栏'}
        aria-expanded={productSidebarOpen}
        aria-controls="product-sidebar"
        onClick={() => setProductSidebarOpen((open) => !open)}
      >
        <span aria-hidden="true">{productSidebarOpen ? '‹' : '›'}</span>
      </button>
      <main className="app-main">
        {activeInstId ? (
          <ProductPanel instId={activeInstId} />
        ) : (
          <p className="empty-hint">尚未选择任何产品</p>
        )}
      </main>
      {(
        <ProductSidebar
          open={productSidebarOpen}
          busy={removingProduct}
          error={selectionError}
          instIds={selectedInstIds}
          activeInstId={activeInstId}
          onSelect={setActiveInstId}
          onRemove={handleRemoveProduct}
          onOpenSelector={() => setSelectorOpen(true)}
          onClose={() => setProductSidebarOpen(false)}
        />
      )}
      {selectorOpen && (
        <ProductSelector
          selectedInstIds={selectedInstIds}
          onSelectionChange={handleSelectionChange}
          onClose={() => setSelectorOpen(false)}
        />
      )}
      {auxSidebarOpen && (
        <AuxSidebar
          initialEventContractMarkets={initialEventContractMarkets}
          initialEconomicCalendar={initialEconomicCalendar}
          onClose={() => setAuxSidebarOpen(false)}
        />
      )}
    </div>
  )
}
