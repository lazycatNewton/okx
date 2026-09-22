import assert from 'node:assert/strict'
import test from 'node:test'
import { chartTimeInEt, formatChartTick, formatChartTime } from '../src/time.ts'
import { TickMarkType } from 'lightweight-charts'

test('fall-back keeps distinct UTC keys while labels identify EDT and EST', () => {
  const before = chartTimeInEt(Date.parse('2026-11-01T05:30:00Z'))
  const after = chartTimeInEt(Date.parse('2026-11-01T06:30:00Z'))
  assert.equal(after - before, 3600)
  assert.match(formatChartTime(before), /01:30:00 EDT/)
  assert.match(formatChartTime(after), /01:30:00 EST/)
})

test('New York midnight remains midnight in summer and winter axis labels', () => {
  for (const value of ['2026-09-16T04:00:00Z', '2026-01-16T05:00:00Z']) {
    assert.equal(formatChartTick(chartTimeInEt(Date.parse(value)), TickMarkType.Time), '00:00')
  }
})

test('UTC midnight does not introduce a New York date boundary at 20:00', () => {
  const time = chartTimeInEt(Date.parse('2026-09-02T00:00:00Z'))
  assert.equal(formatChartTick(time, TickMarkType.DayOfMonth), '20:00')
})
