import { test } from 'node:test'
import assert from 'node:assert/strict'
import { nextActiveProduct } from '../src/productNavigation.ts'

test('deleting active product prefers next neighbor', () => {
  assert.equal(nextActiveProduct(['A', 'B', 'C'], ['A', 'C'], 'B'), 'C')
})
test('deleting last product falls back to previous neighbor', () => {
  assert.equal(nextActiveProduct(['A', 'B', 'C'], ['A', 'B'], 'C'), 'B')
})
test('deleting another product keeps active product', () => {
  assert.equal(nextActiveProduct(['A', 'B', 'C'], ['B', 'C'], 'C'), 'C')
})
test('empty selection has no active product', () => {
  assert.equal(nextActiveProduct(['A'], [], 'A'), null)
})
test('only accepted products can become active', () => {
  assert.equal(nextActiveProduct(['A', 'B', 'C', 'D'], ['A', 'D'], 'B'), 'D')
})
