import { useMemo, useState, type ReactNode } from 'react'
import { candlePriceFormat } from '../candleData'
import { summarizeChan, type PricePosition } from '../chanSummary'
import { PROJECT_TIME_ZONE } from '../time'
import type { CandleItem, TradeBar } from '../types'

const STROKES_COLLAPSED = 8

const POSITION_TEXT: Record<PricePosition, string> = {
  above: '位于最新中枢上方（> ZG）',
  inside: '位于最新中枢内部（ZD–ZG）',
  below: '位于最新中枢下方（< ZD）',
}

function makeTimeFormatter(bar: TradeBar) {
  const format = new Intl.DateTimeFormat('zh-CN', {
    timeZone: PROJECT_TIME_ZONE,
    hourCycle: 'h23',
    ...(bar === '1D'
      ? { year: 'numeric', month: '2-digit', day: '2-digit' }
      : { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }),
  })
  return (ts: number) => format.format(new Date(ts))
}

function formatDuration(ms: number): string {
  const minutes = Math.round(ms / 60_000)
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const rest = minutes % 60
  const parts = [days && `${days}天`, hours && `${hours}小时`, rest && `${rest}分`].filter(Boolean)
  return parts.length ? parts.join('') : '0分'
}

function formatPct(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

export function ChanPanel({ bar, items, enabled, loading }: {
  bar: TradeBar
  items: CandleItem[]
  enabled: boolean
  loading: boolean
}) {
  const [showAllStrokes, setShowAllStrokes] = useState(false)
  const summary = useMemo(() => (enabled ? summarizeChan(items) : null), [enabled, items])
  const precision = useMemo(() => candlePriceFormat(items.filter((i) => i.confirm === '1')).precision, [items])
  const fmtTime = useMemo(() => makeTimeFormatter(bar), [bar])
  const price = (value: number) => value.toFixed(precision)

  let body: ReactNode
  if (!enabled) {
    body = <p className="empty-hint">{bar} 周期不做缠论计算；切换到 5m / 15m / 30m / 1D 查看。</p>
  } else if (loading && !summary) {
    // 切换周期后实时推送可能先于历史接口到达：只有一根未闭合 K 线时不能误报「数据不足」。
    body = <p className="empty-hint">加载中…</p>
  } else if (!summary) {
    body = <p className="empty-hint">已闭合 K 线不足，暂无法形成缠论结构（数据事实，非缺陷）。</p>
  } else {
    const { latestStroke } = summary
    const strokes = showAllStrokes ? summary.strokes : summary.strokes.slice(0, STROKES_COLLAPSED)
    body = (
      <>
        <p className="chan-range">
          样本 {fmtTime(summary.firstTs)} → {fmtTime(summary.lastTs)}（ET），共 {summary.barCount} 根已闭合 K 线
        </p>

        <dl className="chan-stats">
          <div><dt>中枢</dt><dd>{summary.zhongshu.length}</dd></div>
          <div><dt>笔</dt><dd>{summary.strokes.length}</dd></div>
          <div><dt>顶 / 底分型</dt><dd>{summary.topFractals} / {summary.bottomFractals}</dd></div>
          <div><dt>背驰 BC</dt><dd className={summary.exhaustionCount ? 'chan-hot' : ''}>{summary.exhaustionCount}</dd></div>
          <div><dt>背离 DIV</dt><dd>{summary.divergenceCount}</dd></div>
        </dl>

        {latestStroke && (
          <div className="chan-now">
            <span className={`chan-dir chan-${latestStroke.direction}`}>
              {latestStroke.direction === 'up' ? '▲ 向上笔' : '▼ 向下笔'}
            </span>
            <span>
              最新一笔 {price(latestStroke.startPrice)} → {price(latestStroke.endPrice)}
              <b className={`chan-${latestStroke.direction}`}> {formatPct(latestStroke.changePct)}</b>
              ，止于 {fmtTime(latestStroke.endTs)}
            </span>
            {summary.position && (
              <span>收盘 {price(summary.lastClose)} {POSITION_TEXT[summary.position]}</span>
            )}
          </div>
        )}

        <h4 className="chan-section-title">中枢 <small>最新在前</small></h4>
        {summary.zhongshu.length === 0 ? (
          <p className="empty-hint">暂未形成中枢（至少需要 3 笔重叠）。</p>
        ) : (
          <ol className="chan-list">
            {summary.zhongshu.map((z) => (
              <li key={z.seq} className="chan-zs">
                <div className="chan-zs-head">
                  <strong>中枢 {z.seq}</strong>
                  <span>{fmtTime(z.startTs)} – {fmtTime(z.endTs)}</span>
                  <span className="chan-muted">持续 {formatDuration(z.endTs - z.startTs)} · {z.bars} 根 · {z.strokeCount} 笔</span>
                </div>
                <div className="chan-zs-body">
                  <span>区间 ZD {price(z.zd)} – ZG {price(z.zg)}</span>
                  <span className="chan-muted">振幅 {((z.zg - z.zd) / z.zd * 100).toFixed(2)}%</span>
                  <span className="chan-muted">极值 DD {price(z.dd)} / GG {price(z.gg)}</span>
                  <span>
                    本段背驰 <b className={z.exhaustionCount ? 'chan-hot' : ''}>{z.exhaustionCount}</b>
                    {' · '}背离 <b>{z.divergenceCount}</b>
                  </span>
                </div>
              </li>
            ))}
          </ol>
        )}

        <h4 className="chan-section-title">背驰 / 背离 <small>最新在前</small></h4>
        {summary.divergences.length === 0 ? (
          <p className="empty-hint">暂无背驰或背离。</p>
        ) : (
          <ol className="chan-list chan-timeline">
            {summary.divergences.map((d) => (
              <li key={`${d.kind}-${d.ts}`}>
                <span className="chan-time">{fmtTime(d.ts)}</span>
                <span className={`chan-tag ${d.isExhaustion ? 'is-bc' : 'is-div'}`}>{d.code}</span>
                <span className={d.isTop ? 'chan-down' : 'chan-up'}>{d.label}</span>
                <span className="chan-muted">@ {price(d.price)}</span>
              </li>
            ))}
          </ol>
        )}

        <h4 className="chan-section-title">笔 <small>最新在前</small></h4>
        <table className="chan-strokes">
          <thead>
            <tr><th>#</th><th>方向</th><th>起止（ET）</th><th>价格</th><th>幅度</th><th>K 线</th></tr>
          </thead>
          <tbody>
            {strokes.map((s) => (
              <tr key={s.seq}>
                <td className="chan-muted">{s.seq}</td>
                <td className={`chan-${s.direction}`}>{s.direction === 'up' ? '▲ 上' : '▼ 下'}</td>
                <td>{fmtTime(s.startTs)} – {fmtTime(s.endTs)}</td>
                <td>{price(s.startPrice)} → {price(s.endPrice)}</td>
                <td className={`chan-${s.direction}`}>{formatPct(s.changePct)}</td>
                <td className="chan-muted">{s.bars}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {summary.strokes.length > STROKES_COLLAPSED && (
          <button className="chan-more" onClick={() => setShowAllStrokes((v) => !v)}>
            {showAllStrokes ? '收起' : `展开全部 ${summary.strokes.length} 笔`}
          </button>
        )}
      </>
    )
  }

  return (
    <section className="panel chan-panel" aria-label="A1 缠论结构">
      <div className="panel-heading">
        <h3>A1:CHAN · 缠论结构（{bar}，ET）</h3>
        <span className="chan-muted">仅已闭合 K 线参与计算</span>
      </div>
      {body}
    </section>
  )
}
