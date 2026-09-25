import assert from 'node:assert/strict'
import test from 'node:test'
import { summarizeChan } from '../src/chanSummary.ts'
import type { CandleItem } from '../src/types.ts'

const start = Date.parse('2026-09-01T00:00:00Z')
function candles(count: number, amplitude = 3): CandleItem[] {
  return Array.from({ length: count }, (_, i) => {
    // 振幅逐渐放大的正弦：既能形成中枢，又会出现创新高/新低的背离候选。
    const center = 100 + Math.sin(i * Math.PI / 6) * (amplitude + i * 0.02)
    return {
      ts: start + i * 300_000,
      o: (center - 0.25).toFixed(2), h: (center + 0.6).toFixed(2),
      l: (center - 0.6).toFixed(2), c: (center + 0.25).toFixed(2),
      vol: '1', volCcy: null, volCcyQuote: null, confirm: '1',
    }
  })
}

test('too few closed bars yields no summary instead of a fabricated structure', () => {
  assert.equal(summarizeChan(candles(4)), null)
})

test('unclosed latest bar is excluded, matching the chart overlay', () => {
  const items = candles(300)
  items[299] = { ...items[299], confirm: '0' }
  const summary = summarizeChan(items)!
  assert.equal(summary.barCount, 299)
  assert.equal(summary.lastTs, items[298].ts)
})

test('every list is newest-first and counts are internally consistent', () => {
  const summary = summarizeChan(candles(300))!
  assert.ok(summary.zhongshu.length > 0, 'fixture should form at least one zhongshu')
  assert.ok(summary.strokes.length > 0)
  const descending = (values: number[]) => values.every((v, i) => i === 0 || values[i - 1] >= v)
  assert.ok(descending(summary.zhongshu.map((z) => z.startTs)))
  assert.ok(descending(summary.zhongshu.map((z) => z.seq)))
  assert.ok(descending(summary.strokes.map((s) => s.endTs)))
  assert.ok(descending(summary.divergences.map((d) => d.ts)))
  assert.equal(summary.latestStroke?.seq, summary.strokes[0].seq)
  assert.equal(summary.exhaustionCount + summary.divergenceCount, summary.divergences.length)
  for (const z of summary.zhongshu) {
    assert.ok(z.zd <= z.zg && z.dd <= z.zd && z.gg >= z.zg)
    assert.ok(z.startTs <= z.endTs)
  }
})

test('per-zhongshu divergence counts never exceed the global totals', () => {
  const summary = summarizeChan(candles(300))!
  const bc = summary.zhongshu.reduce((n, z) => n + z.exhaustionCount, 0)
  const div = summary.zhongshu.reduce((n, z) => n + z.divergenceCount, 0)
  assert.ok(bc <= summary.exhaustionCount)
  assert.ok(div <= summary.divergenceCount)
})
