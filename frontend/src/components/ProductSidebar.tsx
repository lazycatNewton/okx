// 左侧产品导航侧边栏：已选产品列表（可滚动）+ 底部固定"+"新增按钮。
// 覆盖层浮出模式，和右侧 AuxSidebar 同一套视觉/交互语言（默认收起，点击头部按钮滑出）。
interface ProductSidebarProps {
  open: boolean
  busy: boolean
  error: string | null
  instIds: string[]
  activeInstId: string | null
  onSelect: (instId: string) => void
  onRemove: (instId: string) => void
  onOpenSelector: () => void
  onClose: () => void
}

export function ProductSidebar({
  open,
  busy,
  error,
  instIds,
  activeInstId,
  onSelect,
  onRemove,
  onOpenSelector,
  onClose,
}: ProductSidebarProps) {
  function handleRemove(instId: string) {
    // 立即断开该产品的 WS 连接、移出选择列表；不删除已采集的历史数据，
    // 下次登录 bootstrap 不再返回该产品、不再显示（后端语义已在
    // updateSelection() / SelectionDataRuntime 中验证过）。误触成本是漏掉
    // 一段行情数据，因此加一次轻量确认。
    if (!window.confirm(`取消选择 ${instId}？将断开该产品的实时连接（已保存的数据不会被删除）。`)) return
    onRemove(instId)
  }

  return (
    <aside id="product-sidebar" aria-label="产品导航" inert={!open} aria-hidden={!open} className={`product-sidebar${open ? ' is-open' : ''}`}>
      <div className="product-sidebar-header">
        <h2>已选产品</h2>
        <button className="product-sidebar-close" onClick={onClose} aria-label="收起产品侧边栏">
          ×
        </button>
      </div>
      <ul className="product-sidebar-list">
        {instIds.length === 0 && <li className="empty-hint">尚未选择任何产品</li>}
        {instIds.map((instId) => (
          <li key={instId} className={instId === activeInstId ? 'product-sidebar-item active' : 'product-sidebar-item'}>
            <button
              className="product-sidebar-remove"
              disabled={busy}
              onClick={() => handleRemove(instId)}
              aria-label={`取消选择 ${instId}`}
            >
              ×
            </button>
            <button className="product-sidebar-name" aria-current={instId === activeInstId ? 'page' : undefined} onClick={() => onSelect(instId)}>
              {instId}
            </button>
          </li>
        ))}
      </ul>
      {error && <p className="product-sidebar-error" role="alert">{error}</p>}
      <button className="product-sidebar-add" disabled={busy} onClick={onOpenSelector} aria-label="选择产品">
        +
      </button>
    </aside>
  )
}
