import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatDecimal, detailLabel, detailValue } from '../src/detailDisplay.ts'

test('decimal display rounds exactly and preserves large integer precision', () => {
  assert.equal(formatDecimal('9007199254740993.125'), '9007199254740993.13')
  assert.equal(formatDecimal('1.005'), '1.01')
  assert.equal(formatDecimal('9.999'), '10.00')
  assert.equal(formatDecimal('-1.235'), '-1.24')
  assert.equal(formatDecimal('-0.001'), '0.00')
})
test('rates display as percentages with two decimals', () => {
  assert.equal(formatDecimal('0.0001', true), '0.01%')
  assert.equal(formatDecimal('-0.00125', true), '-0.13%')
  assert.equal(formatDecimal('0', true), '0.00%')
})
test('missing and invalid numbers never display misleading zero', () => {
  for (const value of [null, undefined, '', 'NaN', 'abc']) assert.equal(formatDecimal(value), '—')
})
test('detail labels and enum values are understandable Chinese', () => {
  assert.equal(detailLabel('bkPx'), '强平标记价格')
  assert.equal(detailValue('settState', 'settled'), '已结算')
  assert.equal(detailValue('instType', 'SWAP'), '永续合约')
  assert.equal(detailValue('enabled', false), '未启用')
  assert.equal(detailValue('state', 'new_state'), '未知状态（new_state）')
  assert.equal(detailValue('bkLoss', ''), '—')
})
