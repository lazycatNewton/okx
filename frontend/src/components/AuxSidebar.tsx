// M22 事件合约辅助市场 + M23 经济日历：独立全局侧边栏，按时间倒序展示，可加载更早页。
import { useState } from 'react'
import { getEconomicCalendar, getEventContractMarkets } from '../api'
import { formatEt } from '../time'
import type { EconomicCalendarItem, EventContractMarketItem } from '../types'

interface AuxSidebarProps {
  initialEventContractMarkets: EventContractMarketItem[]
  initialEconomicCalendar: EconomicCalendarItem[]
  onClose: () => void
}

type Tab = 'm22' | 'm23'

export function AuxSidebar({
  initialEventContractMarkets,
  initialEconomicCalendar,
  onClose,
}: AuxSidebarProps) {
  const [tab, setTab] = useState<Tab>('m22')
  const [markets, setMarkets] = useState(initialEventContractMarkets)
  const [marketsCursor, setMarketsCursor] = useState<string | null>(null)
  const [marketsHasMore, setMarketsHasMore] = useState(initialEventContractMarkets.length >= 50)
  const [marketsLoading, setMarketsLoading] = useState(false)

  const [calendar, setCalendar] = useState(initialEconomicCalendar)
  const [calendarCursor, setCalendarCursor] = useState<string | null>(null)
  const [calendarHasMore, setCalendarHasMore] = useState(initialEconomicCalendar.length >= 50)
  const [calendarLoading, setCalendarLoading] = useState(false)

  async function loadMoreMarkets() {
    setMarketsLoading(true)
    try {
      const res = await getEventContractMarkets(marketsCursor)
      setMarkets((prev) => [...prev, ...res.items])
      setMarketsCursor(res.nextCursor)
      setMarketsHasMore(res.hasMore)
    } finally {
      setMarketsLoading(false)
    }
  }

  async function loadMoreCalendar() {
    setCalendarLoading(true)
    try {
      const res = await getEconomicCalendar(calendarCursor)
      setCalendar((prev) => [...prev, ...res.items])
      setCalendarCursor(res.nextCursor)
      setCalendarHasMore(res.hasMore)
    } finally {
      setCalendarLoading(false)
    }
  }

  return (
    <aside className="aux-sidebar">
      <div className="aux-sidebar-header">
        <div className="aux-sidebar-tabs">
          <button
            className={tab === 'm22' ? 'aux-tab active' : 'aux-tab'}
            onClick={() => setTab('m22')}
          >
            事件合约市场
          </button>
          <button
            className={tab === 'm23' ? 'aux-tab active' : 'aux-tab'}
            onClick={() => setTab('m23')}
          >
            经济日历
          </button>
        </div>
        <button className="aux-sidebar-close" onClick={onClose} aria-label="关闭侧边栏">
          ×
        </button>
      </div>

      {tab === 'm22' && (
        <div className="aux-sidebar-body">
          {markets.length === 0 && <p className="empty-hint">暂无数据</p>}
          <ul className="aux-list">
            {markets.map((m) => (
              <li key={m.instId} className="aux-list-item">
                <div className="aux-list-item-title">{m.instId}</div>
                <div className="aux-list-item-meta">
                  <span className={`aux-state aux-state-${m.state ?? 'unknown'}`}>{m.state}</span>
                  <span>{m.expTime != null ? formatEt(m.expTime, { dateStyle: 'medium', timeStyle: 'short' }) : '—'}</span>
                </div>
                <div className="aux-list-item-detail">
                  <span>行权价 {m.floorStrike ?? '—'}</span>
                  {m.outcome && <span>结果 {m.outcome}</span>}
                </div>
              </li>
            ))}
          </ul>
          {marketsHasMore && (
            <button className="aux-load-more" onClick={loadMoreMarkets} disabled={marketsLoading}>
              {marketsLoading ? '加载中…' : '加载更早'}
            </button>
          )}
        </div>
      )}

      {tab === 'm23' && (
        <div className="aux-sidebar-body">
          {calendar.length === 0 && (
            <p className="empty-hint">暂无数据（未配置凭证 / 未达 VIP1 / 鉴权或网络故障时为空）</p>
          )}
          <ul className="aux-list">
            {calendar.map((c) => (
              <li key={c.calendarId} className="aux-list-item">
                <div className="aux-list-item-title">{c.event}</div>
                <div className="aux-list-item-meta">
                  <span>{c.region}</span>
                  <span>{c.date != null ? formatEt(c.date, { dateStyle: 'medium', timeStyle: 'short' }) : '—'}</span>
                </div>
                <div className="aux-list-item-detail">
                  <span>重要性 {c.importance ?? '—'}</span>
                  <span>实际 {c.actual ?? '—'}</span>
                  <span>预测 {c.forecast ?? '—'}</span>
                  <span>前值 {c.previous ?? '—'}</span>
                </div>
              </li>
            ))}
          </ul>
          {calendarHasMore && (
            <button className="aux-load-more" onClick={loadMoreCalendar} disabled={calendarLoading}>
              {calendarLoading ? '加载中…' : '加载更早'}
            </button>
          )}
        </div>
      )}
    </aside>
  )
}
