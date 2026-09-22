import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const css = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8')

test('product selector overlay stays above chart canvases', () => {
  const block = css.match(/\.product-selector-overlay\s*\{([^}]*)\}/)?.[1]
  assert.ok(block, 'missing .product-selector-overlay CSS block')
  const zIndex = Number(block.match(/z-index\s*:\s*(\d+)/)?.[1])
  assert.ok(Number.isFinite(zIndex), 'product selector overlay must declare an explicit z-index')
  assert.ok(zIndex >= 1000, `expected modal layer z-index >= 1000, got ${zIndex}`)
})
