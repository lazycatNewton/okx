import assert from 'node:assert/strict'
import test from 'node:test'
import { candlePriceFormat, mergeCandles } from '../src/candleData.ts'
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
