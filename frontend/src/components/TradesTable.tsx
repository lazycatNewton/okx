import type { ChannelState } from '../marketDataStore'
import type { TradeData } from '../types'
import { formatEt } from '../time'

export function TradesTable({ state }: { state: ChannelState<TradeData[]> }) {
  const trades = state.data ?? []
  return (
    <section className="panel trades-table">
      <div className="panel-heading"><h3>M03 · 最新成交</h3><span>{trades.length}</span></div>
      {trades.length === 0 ? <p className="empty-hint">暂无成交数据</p> : (
        <div className="trade-list">
          {trades.map((trade) => (
            <div className={`trade-row ${trade.side}`} key={trade.tradeId}>
              <time>{formatEt(Number(trade.ts), { hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })}</time>
              <span>{trade.side === 'buy' ? '买入' : '卖出'}</span>
              <strong>{trade.px}</strong>
              <span>{trade.sz}</span>
              <span>×{trade.count}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
