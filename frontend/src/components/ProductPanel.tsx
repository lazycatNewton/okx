import { useProductRealtime } from '../useMarketData'
import { Book5Table } from './Book5Table'
import { CandleChart } from './CandleChart'
import { M25Panel, S04Chart } from './M25Panel'
import { MarkPriceCard, OpenInterestCard } from './SwapSnapshotCards'
import { TickerCard } from './TickerCard'
import { TradesTable } from './TradesTable'

// 一个产品 Tab 对应的完整面板：K 线 + 该产品适用的已选数据面板。
// M10/M13/M25 仅适用于永续；OKX 命名约定永续 instId 以 `-SWAP` 结尾。
export function ProductPanel({ instId }: { instId: string }) {
  const realtime = useProductRealtime(instId)
  const isSwap = instId.endsWith('-SWAP')

  if (!realtime) return null

  return (
    <div className="product-panel">
      <CandleChart instId={instId} realtime={realtime} />
      <div className="product-panel-row">
        <TickerCard state={realtime.ticker} />
        {isSwap && <S04Chart instId={instId} />}
        <Book5Table state={realtime.books5} />
        <TradesTable state={realtime.trades} />
        {isSwap && (
          <>
            <MarkPriceCard state={realtime.markPrice} />
            <OpenInterestCard state={realtime.openInterest} />
          </>
        )}
      </div>
      {isSwap && <M25Panel instId={instId} />}
    </div>
  )
}
