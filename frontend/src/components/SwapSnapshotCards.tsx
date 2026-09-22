import type { MarkPriceData, OpenInterestData } from '../types'
import type { ChannelState } from '../marketDataStore'
import { formatEt } from '../time'
import { detailValue, formatDecimal } from '../detailDisplay'

// M10 标记价格：仅永续，数值卡片。
export function MarkPriceCard({ state }: { state: ChannelState<MarkPriceData> }) {
  if (state.status === 'empty' || !state.data) {
    return (
      <div className="panel numeric-card">
        <h3>M10 · 标记价格</h3>
        <p className="empty-hint">暂无数据</p>
      </div>
    )
  }
  const d = state.data
  return (
    <div className="panel numeric-card">
      <h3>M10 · 标记价格</h3>
      <dl className="metric-grid">
        <div><dt>当前标记价格（与最新成交价分别展示）</dt><dd className="numeric-core">{d.markPx}</dd></div>
      </dl>
      <details>
        <summary>详情</summary>
        <dl className="detail-grid">
          <dt>产品类型</dt>
          <dd>{detailValue('instType', d.instType)}</dd>
          <dt>数据更新时间</dt>
          <dd>{formatEt(Number(d.ts), { dateStyle: 'medium', timeStyle: 'medium' })}</dd>
        </dl>
      </details>
    </div>
  )
}

// M13 持仓总量：仅永续，数值卡片。
export function OpenInterestCard({ state }: { state: ChannelState<OpenInterestData> }) {
  if (state.status === 'empty' || !state.data) {
    return (
      <div className="panel numeric-card">
        <h3>M13 · 持仓总量</h3>
        <p className="empty-hint">暂无数据</p>
      </div>
    )
  }
  const d = state.data
  return (
    <div className="panel numeric-card">
      <h3>M13 · 持仓总量</h3>
      <div className="numeric-core">{formatDecimal(d.oi)} 张</div>
      <div className="numeric-grid">
        <div>持仓币数量：{formatDecimal(d.oiCcy)} 币</div>
        <div>持仓折合美元：{formatDecimal(d.oiUsd)} USD</div>
      </div>
      <details>
        <summary>详情</summary>
        <dl className="detail-grid">
          <dt>产品类型</dt>
          <dd>{detailValue('instType', d.instType)}</dd>
          <dt>数据更新时间</dt>
          <dd>{formatEt(Number(d.ts), { dateStyle: 'medium', timeStyle: 'medium' })}</dd>
        </dl>
      </details>
    </div>
  )
}
