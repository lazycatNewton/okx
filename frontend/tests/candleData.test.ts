import assert from 'node:assert/strict'
import test from 'node:test'
import { candlePriceFormat, mergeCandles, quoteCurrency, volumeBar } from '../src/candleData.ts'
import type { CandleItem } from '../src/types.ts'

const candle = (ts: number, c: string, confirm = '0'): CandleItem => ({
  ts, o: '10', h: '20', l: '5', c, vol: '1', volCcy: null, volCcyQuote: null, confirm,
})

test('history and buffered realtime merge into one ordered timeline without losing intermediate bars', () => {
  const realtime = [candle(3000, '13'), candle(2000, '12')]
  const history = [candle(2000, '11'), candle(1000, '10', '1')]
  assert.deepEqual(mergeCandles(history, realtime).map(item => [item.ts, item.c]), [[1000, '10'], [2000, '12'], [3000, '13']])
  assert.equal(history[0].c, '11')
  assert.equal(realtime[0].ts, 3000)
})

test('closed bars cannot regress to an open version from either source', () => {
  const closed = candle(1000, '12', '1')
  const open = candle(1000, '11', '0')
  assert.deepEqual(mergeCandles([closed], [open]), [closed])
  assert.deepEqual(mergeCandles([open], [closed]), [closed])
})

test('late corrections replace the matching old timestamp without moving newer candles', () => {
  const series = [candle(1000, '10', '1'), candle(2000, '11', '1'), candle(3000, '13')]
  assert.deepEqual(mergeCandles(series, [candle(2000, '12', '1')]).map(item => [item.ts, item.c]), [[1000, '10'], [2000, '12'], [3000, '13']])
})

test('price precision handles sub-cent, scientific notation and integer quotes', () => {
  assert.deepEqual(candlePriceFormat([candle(1000, '0.092770')]), { type: 'price', precision: 5, minMove: 0.00001 })
  assert.deepEqual(candlePriceFormat([candle(1000, '1.25e-8')]), { type: 'price', precision: 10, minMove: 1e-10 })
  assert.deepEqual(candlePriceFormat([candle(1000, '100')]), { type: 'price', precision: 0, minMove: 1 })
})

test('volume bars use official volCcyQuote and keep whitespace for missing values', () => {
  const base = { ts: 0, h: '2', l: '0.5', vol: '10', volCcy: '10', confirm: '1' }
  const up = volumeBar({ ...base, time: 1, o: '1', c: '1.5', volCcyQuote: '1234.5' })
  assert.equal(up.value, 1234.5)
  assert.match(up.color ?? '', /34, 197, 94/)
  const down = volumeBar({ ...base, time: 2, o: '1.5', c: '1', volCcyQuote: '10' })
  assert.match(down.color ?? '', /239, 68, 68/)
  assert.deepEqual(volumeBar({ ...base, time: 3, o: '1', c: '1', volCcyQuote: null }), { time: 3 })
})

test('quote currency comes from the second instId segment', () => {
  assert.equal(quoteCurrency('BTC-USDT-SWAP'), 'USDT')
  assert.equal(quoteCurrency('BTC-USDT'), 'USDT')
  assert.equal(quoteCurrency('BTC-USD-SWAP'), 'USD')
})
