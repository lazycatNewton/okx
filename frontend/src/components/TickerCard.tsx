import type { TickerData } from '../types'
import type { ChannelState } from '../marketDataStore'
import { formatEt } from '../time'
import { detailValue } from '../detailDisplay'

// M01 ticker：行情概览数值卡片。核心字段先展示，详情可展开。
export function TickerCard({ state }: { state: ChannelState<TickerData> }) {
  if (state.status === 'empty' || !state.data) {
    return (
      <div className="panel ticker-card">
        <h3>M01 · 最新行情</h3>
        <p className="empty-hint">暂无数据</p>
      </div>
    )
  }
  const t = state.data
  return (
    <div className="panel ticker-card">
      <h3>M01 · 最新行情</h3>
      <dl className="metric-grid">
        <div><dt>最新成交价</dt><dd className="last">{t.last}</dd></div>
        <div><dt>买一价（当前最高买入报价）</dt><dd>{t.bidPx}</dd></div>
        <div><dt>卖一价（当前最低卖出报价）</dt><dd>{t.askPx}</dd></div>
        <div><dt>24小时最高价</dt><dd>{t.high24h}</dd></div>
        <div><dt>24小时最低价</dt><dd>{t.low24h}</dd></div>
        <div><dt>24小时成交量（{t.instType === 'SWAP' ? '张' : '交易币'}）</dt><dd>{t.vol24h}</dd></div>
      </dl>
      <details>
        <summary>详情</summary>
        <dl className="detail-grid">
          <dt>最新成交数量</dt>
          <dd>{t.lastSz}</dd>
          <dt>买一挂单量</dt>
          <dd>{t.bidSz}</dd>
          <dt>卖一挂单量</dt>
          <dd>{t.askSz}</dd>
          <dt>24小时开盘价</dt>
          <dd>{t.open24h}</dd>
          <dt>24小时成交量（{t.instType === 'SWAP' ? '交易币' : '计价币'}）</dt>
          <dd>{t.volCcy24h}</dd>
          <dt>当日开盘价（UTC+0）</dt>
          <dd>{t.sodUtc0}</dd>
          <dt>当日开盘价（UTC+8）</dt>
          <dd>{t.sodUtc8}</dd>
          <dt>产品类型</dt>
          <dd>{detailValue('instType', t.instType)}</dd>
          <dt>数据产生时间</dt>
          <dd>{formatEt(Number(t.ts), { dateStyle: 'medium', timeStyle: 'medium' })}</dd>
        </dl>
      </details>
    </div>
  )
}
