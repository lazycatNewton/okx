import type { Book5Data } from '../types'
import type { ChannelState } from '../marketDataStore'

// M05 五档盘口：表格展示，价格由高到低（asks 反序）叠加 bids。
export function Book5Table({ state }: { state: ChannelState<Book5Data> }) {
  if (state.status === 'empty' || !state.data) {
    return (
      <div className="panel book5-table">
        <h3>M05 · 五档盘口</h3>
        <p className="empty-hint">暂无数据</p>
      </div>
    )
  }
  const { asks, bids } = state.data
  const asksDesc = [...asks].reverse()
  return (
    <div className="panel book5-table">
      <h3>M05 · 五档盘口</h3>
      <table>
        <thead>
          <tr>
            <th>价格</th>
            <th>数量</th>
            <th>订单数</th>
          </tr>
        </thead>
        <tbody>
          {asksDesc.map(([px, sz, , count]) => (
            <tr key={`ask-${px}`} className="ask-row">
              <td>{px}</td>
              <td>{sz}</td>
              <td>{count}</td>
            </tr>
          ))}
          <tr className="spread-row">
            <td colSpan={3}>——</td>
          </tr>
          {bids.map(([px, sz, , count]) => (
            <tr key={`bid-${px}`} className="bid-row">
              <td>{px}</td>
              <td>{sz}</td>
              <td>{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
