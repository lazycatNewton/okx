import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildCandleLegend,
  buildZhongshuPriceLabels,
} from '../src/chartDisplay.ts'

test('buildZhongshuPriceLabels returns upper and lower boundary prices', () => {
  assert.deepEqual(buildZhongshuPriceLabels({ zg: 77893.8, zd: 77599 }), [
    { boundary: 'ZG', price: 77893.8, text: 'ZG 77893.8' },
    { boundary: 'ZD', price: 77599, text: 'ZD 77599' },
  ])
})

test('buildCandleLegend preserves original decimal strings', () => {
  assert.deepEqual(
    buildCandleLegend({ o: '77800.10', h: '77999.20', l: '77750.00', c: '77920.30' }),
    {
      open: '77800.10',
      high: '77999.20',
      low: '77750.00',
      close: '77920.30',
    },
  )
})
