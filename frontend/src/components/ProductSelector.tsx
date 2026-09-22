import { useEffect, useState } from 'react'
import { listProducts, updateSelection } from '../api'
import type { ProductItem } from '../types'

interface Props {
  selectedInstIds: string[]
  onSelectionChange: (instIds: string[]) => void
  onClose: () => void
}

export function ProductSelector({ selectedInstIds, onSelectionChange, onClose }: Props) {
  const [instType, setInstType] = useState<'SPOT' | 'SWAP'>('SPOT')
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<ProductItem[]>([])
  const [pending, setPending] = useState<string[]>(selectedInstIds)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    listProducts({ instType, q: query || undefined })
      .then((res) => setItems(res.items))
      .finally(() => setLoading(false))
  }, [instType, query])

  function toggle(instId: string, selectable: boolean) {
    if (!selectable) return
    setPending((prev) =>
      prev.includes(instId) ? prev.filter((id) => id !== instId) : [...prev, instId],
    )
  }

  async function handleSave() {
    const result = await updateSelection(pending)
    onSelectionChange(result.accepted)
    onClose()
  }

  return (
    <div className="product-selector-overlay">
      <div className="product-selector">
        <header>
          <h2>选择产品</h2>
          <button onClick={onClose}>关闭</button>
        </header>
        <div className="product-selector-controls">
          <select value={instType} onChange={(e) => setInstType(e.target.value as 'SPOT' | 'SWAP')}>
            <option value="SPOT">现货</option>
            <option value="SWAP">永续</option>
          </select>
          <input
            placeholder="按 instId 搜索"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {loading ? (
          <p>加载中…</p>
        ) : (
          <ul className="product-list">
            {items.map((item) => (
              <li
                key={item.instId}
                className={item.selectable ? '' : 'not-selectable'}
                onClick={() => toggle(item.instId, item.selectable)}
              >
                <input
                  type="checkbox"
                  checked={pending.includes(item.instId)}
                  disabled={!item.selectable}
                  readOnly
                />
                <span className="inst-id">{item.instId}</span>
                <span className="state">{item.state}</span>
              </li>
            ))}
          </ul>
        )}
        <footer>
          <button onClick={handleSave}>保存选择（{pending.length}）</button>
        </footer>
      </div>
    </div>
  )
}
