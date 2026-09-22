import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const css = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8')
const index = readFileSync(new URL('../src/index.css', import.meta.url), 'utf8')
const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
test('root uses full viewport width without template border', () => {
  const root = index.match(/#root\s*\{([^}]+)\}/)![1]
  assert.match(root, /width: 100%/)
  assert.match(root, /margin: 0;/)
  assert.doesNotMatch(root, /1126px|border-inline/)
})
test('main shrinks and scrolls below compact header', () => {
  assert.match(css, /\.app-main\s*\{[^}]*min-height: 0;[^}]*overflow: auto;/)
  assert.match(css, /\.app-header h1\s*\{[^}]*margin: 0;[^}]*font-size: 20px;/)
})
test('edge toggle remains outside hidden sidebar and follows width', () => {
  assert.doesNotMatch(app, /☰ 产品/)
  assert.match(app, /productSidebarOpen \? '‹' : '›'/)
  assert.match(css, /\.product-sidebar-toggle\s*\{[^}]*position: fixed;[^}]*left: 0;[^}]*top: 50%;/)
  assert.match(css, /\.product-sidebar-toggle\.is-open\s*\{ left: var\(--product-sidebar-width\);/)
})
