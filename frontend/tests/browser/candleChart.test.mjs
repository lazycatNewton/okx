import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'
import { createServer } from 'vite'

const root = fileURLToPath(new URL('../..', import.meta.url))
const start = Date.parse('2026-09-01T00:00:00Z')
const steps = { '1s': 1000, '1m': 60000, '5m': 300000, '15m': 900000, '30m': 1800000, '1D': 86400000 }
const candles = (count = 300, bar = '5m', base = 100) => Array.from({ length: count }, (_, i) => {
  const center = base + Math.sin(i * Math.PI / 6) * 3
  return { ts: start + i * steps[bar], o: (center - 0.25).toFixed(2), h: (center + 0.6).toFixed(2), l: (center - 0.6).toFixed(2), c: (center + 0.25).toFixed(2), vol: '1', volCcy: null, volCcyQuote: null, confirm: '1' }
})
let server, browser, origin, screenshotDir

before(async () => {
  screenshotDir = process.env.CHART_SCREENSHOT_DIR ?? await mkdtemp(join(tmpdir(), 'okx-chart-regression-'))
  server = await createServer({
    root,
    cacheDir: join(screenshotDir, 'vite-cache'),
    server: { host: '127.0.0.1', port: 0, hmr: false, open: false },
    plugins: [{
      name: 'observe-candle-chart', enforce: 'pre',
      transform(source, id) {
        if (!id.endsWith('/src/components/CandleChart.tsx')) return
        const seam = 'const chart = createChart(element, {'
        assert.ok(source.includes(seam), 'update the chart observation seam if construction moves')
        return source.replace(seam, 'const chart = window.captureChart(createChart, element, {')
      },
    }],
  })
  await server.listen()
  origin = `http://127.0.0.1:${server.httpServer.address().port}`
  browser = await chromium.launch({ headless: true })
})
after(async () => { await browser?.close(); await server?.close() })

async function fixture(t, { hold = () => false, fail = false, omit = () => false, dataset } = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  t.after(() => context.close())
  const page = await context.newPage()
  page.setDefaultTimeout(5000)
  const errors = [], pending = [], requests = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/*', async route => {
    const url = new URL(route.request().url())
    if (url.origin !== origin) return route.abort()
    if (!url.pathname.startsWith('/api/')) return route.continue()
    assert.ok(url.pathname.endsWith('/candles'), 'fixture must never reach the backend')
    requests.push(url)
    const bar = url.searchParams.get('bar')
    const all = dataset ? dataset(bar) : candles(bar === '1D' ? 80 : bar === '1s' ? 7500 : 300, bar, url.pathname.includes('SECOND') ? 200 : 100)
    const before = Number(url.searchParams.get('before') ?? Infinity)
    const items = all.filter(item => item.ts < before && !omit(item)).slice(-Number(url.searchParams.get('limit') ?? 300))
    const respond = () => route.fulfill(fail ? { status: 503, json: { detail: 'test unavailable' } } : { json: { items } }).catch(() => {})
    if (hold(url)) { pending.push(respond); return }
    await respond()
  })
  await page.goto(`${origin}/tests/browser/chart-fixture.html`)
  await page.waitForFunction(() => typeof window.renderChart === 'function')
  return { page, errors, requests, release: async () => { for (const respond of pending.splice(0)) await respond() } }
}

async function frame(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
}
async function ready(page, count) {
  await page.waitForFunction(count => window.chartRecords.at(-1)?.series[0]?.data().length === count, count)
  await frame(page)
}
async function data(page) { return page.evaluate(() => window.chartRecords.at(-1).series[0].data()) }
async function push(page, candle, bar = '5m') {
  await page.evaluate(({ bar, candle }) => window.pushCandle(bar, candle), { bar, candle })
  await frame(page)
}
async function hover(page, candle) {
  const point = await page.evaluate(candle => {
    const { chart, series } = window.chartRecords.at(-1)
    const element = document.querySelector('.lightweight-chart').getBoundingClientRect()
    return { x: element.x + chart.timeScale().timeToCoordinate(window.chartTimeInEt(candle.ts)), y: element.y + series[0].priceToCoordinate(Number(candle.c)) }
  }, candle)
  await page.mouse.move(point.x, point.y)
  await frame(page)
  return page.locator('.candle-ohlc-legend').innerText()
}

test('default 5m view shows 2 hours, daily view shows 7 days', async t => {
  const { page, errors } = await fixture(t)
  await ready(page, 300)
  const span = () => page.evaluate(() => { const r = window.chartRecords.at(-1).chart.timeScale().getVisibleRange(); return r.to - r.from })
  assert.equal(await span(), 7200)
  const screenshot = join(screenshotDir, 'trade-5m-fixed.png')
  await page.screenshot({ path: screenshot })
  t.diagnostic(`5m screenshot: ${screenshot}`)
  await page.getByRole('button', { name: '1D', exact: true }).click()
  await ready(page, 80)
  assert.equal(await span(), 7 * 86400)
  assert.deepEqual(errors, [])
})

test('switching product clears old prices before the new HTTP response', async t => {
  const { page, errors, release } = await fixture(t, { hold: url => url.pathname.includes('SECOND') })
  await ready(page, 300)
  await page.evaluate(() => window.renderChart({ instId: 'SECOND-USDT', realtime: { candles: {} } }))
  await frame(page)
  const live = { ...candles(301, '5m', 200).at(-1), confirm: '0' }
  await push(page, live)
  const beforeHttp = await data(page)
  assert.ok(beforeHttp.length <= 1 && beforeHttp.every(item => item.close > 190), 'old product candles must not remain in the new series')
  await release()
  await ready(page, 301)
  assert.ok((await data(page)).every(item => item.close > 190))
  assert.deepEqual(errors, [])
})

test('HTTP completing after two realtime bars preserves candles, OHLC and Chan overlay', async t => {
  const { page, errors, release } = await fixture(t, { hold: () => true })
  const live = candles(302).slice(-2)
  for (const candle of live) await push(page, candle)
  await release()
  await ready(page, 302)
  assert.equal((await data(page)).at(-1).close, Number(live.at(-1).c))
  assert.ok((await hover(page, live[0])).includes(`收盘 ${live[0].c}`))
  const overlay = await page.evaluate(items => {
    const record = window.chartRecords.at(-1)
    const expected = window.expectedOverlay(items)
    return { boxes: record.primitives[0].boxes, points: record.primitives[1].points, expectedBoxes: expected.boxes, expectedPoints: expected.strokePoints }
  }, candles(302))
  assert.deepEqual(overlay.boxes, overlay.expectedBoxes)
  assert.deepEqual(overlay.points, overlay.expectedPoints)
  assert.deepEqual(errors, [])
})

test('same-timestamp realtime correction wins over a later stale HTTP response', async t => {
  const { page, errors, release } = await fixture(t, { hold: () => true })
  const live = { ...candles().at(-1), c: '101.01' }
  await push(page, live)
  await release()
  await ready(page, 300)
  assert.equal((await data(page)).at(-1).close, 101.01)
  assert.ok((await hover(page, live)).includes('收盘 101.01'))
  assert.deepEqual(errors, [])
})

test('late historical correction updates both chart and OHLC without resetting a panned view', async t => {
  const { page, errors } = await fixture(t)
  await ready(page, 300)
  const range = { from: 250.25, to: 280.75 }
  await page.evaluate(range => window.chartRecords.at(-1).chart.timeScale().setVisibleLogicalRange(range), range)
  const correction = { ...candles()[270], c: '101.01' }
  await push(page, correction)
  assert.equal((await data(page))[270].close, 101.01)
  assert.ok((await hover(page, correction)).includes('收盘 101.01'))
  await push(page, candles(301).at(-1))
  assert.deepEqual(await page.evaluate(() => window.chartRecords.at(-1).chart.timeScale().getVisibleLogicalRange()), range)
  assert.deepEqual(errors, [])
})

test('late response from an old period cannot overwrite the new period', async t => {
  const { page, errors, release } = await fixture(t, { hold: url => url.searchParams.get('bar') === '5m' })
  await page.getByRole('button', { name: '15m', exact: true }).click()
  await ready(page, 300)
  const expected = await data(page)
  await release()
  await frame(page)
  assert.deepEqual(await data(page), expected)
  assert.deepEqual(errors, [])
})

test('switching period never draws old-interval candles while the new history is pending', async t => {
  const { page, errors, release } = await fixture(t, { hold: url => url.searchParams.get('bar') === '15m' })
  await ready(page, 300)
  await page.getByRole('button', { name: '15m', exact: true }).click()
  const live = candles(301, '15m').at(-1)
  await push(page, live, '15m')
  await ready(page, 1)
  const beforeHttp = await data(page)
  assert.equal(beforeHttp.length, 1)
  assert.equal(beforeHttp[0].time, await page.evaluate(ts => window.chartTimeInEt(ts), live.ts))
  await release()
  await ready(page, 301)
  const rendered = await data(page)
  assert.ok(rendered.every((item, i) => i === 0 || item.time - rendered[i - 1].time === 900))
  assert.deepEqual(errors, [])
})

test('inserting a missing earlier candle keeps timestamps ordered and the visible time window stable', async t => {
  const missing = candles()[270]
  const { page, errors } = await fixture(t, { omit: item => item.ts === missing.ts })
  await ready(page, 299)
  await page.evaluate(() => {
    const scale = window.chartRecords.at(-1).chart.timeScale()
    scale.setVisibleLogicalRange({ from: 250.25, to: 280.75 })
  })
  // 图表在下一帧应用可见范围；先等用户的平移完成，再注入缺失 K 线。
  await frame(page)
  const range = await page.evaluate(() => window.chartRecords.at(-1).chart.timeScale().getVisibleRange())
  await push(page, missing)
  await ready(page, 300)
  const rendered = await data(page)
  assert.ok(rendered.every((item, i) => i === 0 || item.time - rendered[i - 1].time === 300))
  assert.deepEqual(await page.evaluate(() => window.chartRecords.at(-1).chart.timeScale().getVisibleRange()), range)
  const legend = await hover(page, missing)
  assert.ok(legend.includes(`收盘 ${missing.c}`), `missing candle OHLC did not match: ${legend}`)
  assert.deepEqual(errors, [])
})

test('failed history load still renders subsequent realtime data without unhandled errors', async t => {
  const { page, errors } = await fixture(t, { fail: true })
  await frame(page)
  await push(page, candles(1).at(-1))
  await ready(page, 1)
  assert.deepEqual(errors, [])
})

test('1s history pages through local API to cover the default two-hour window', async t => {
  const { page, errors, requests } = await fixture(t)
  await ready(page, 300)
  await page.getByRole('button', { name: '1s', exact: true }).click()
  await page.waitForFunction(() => window.chartRecords.at(-1)?.series[0]?.data().length >= 7200)
  await page.locator('.candle-chart[aria-busy="false"]').waitFor()
  await frame(page)
  const span = await page.evaluate(() => { const r = window.chartRecords.at(-1).chart.timeScale().getVisibleRange(); return r.to - r.from })
  assert.ok(span >= 7199 && span <= 7200, `1s visible span was ${span} seconds`)
  assert.ok(requests.some(url => url.searchParams.get('bar') === '1s' && url.searchParams.has('before')))
  assert.deepEqual(errors, [])
})

test('price labels retain actual sub-cent OHLC precision', async t => {
  // 真实本地数据中 1INCH-USDT 的报价含五位小数，默认两位会全部变成 0.09。
  const items = candles(25).map(item => ({ ...item, o: '0.09277', h: '0.09284', l: '0.09271', c: '0.09283' }))
  const { page } = await fixture(t, { dataset: () => items })
  await ready(page, items.length)
  const labels = await page.evaluate(() => {
    const formatter = window.chartRecords.at(-1).series[0].priceFormatter()
    return [0.09277, 0.09284, 0.09271, 0.09283].map(price => formatter.format(price))
  })
  assert.deepEqual(labels, ['0.09277', '0.09284', '0.09271', '0.09283'])
})

test('returning to the chart reloads missing bars and final OHLC from local history', async t => {
  const complete = candles(30)
  // HTTP 初次读取发生在回填之前；前一根只收到部分高低价/收盘，且中间漏了两根。
  let available = complete.slice(0, 25)
  available[24] = { ...available[24], h: '100.1', l: '99.9', o: '100', c: '100', confirm: '0' }
  const { page, errors } = await fixture(t, { dataset: () => available })
  await ready(page, 25)
  await push(page, complete[27])
  available = complete
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await ready(page, 30)
  assert.deepEqual((await data(page)).map(item => item.close), complete.map(item => Number(item.c)))
  assert.deepEqual(errors, [])
})

test('New York fall-back hour never deletes or reorders real candles', async t => {
  const items = candles(72).map((item, i) => ({ ...item, ts: Date.parse('2026-11-01T04:00:00Z') + i * 300_000 }))
  const { page, errors } = await fixture(t, { dataset: () => items })
  await ready(page, 72)
  const rendered = await data(page)
  assert.ok(rendered.every((item, i) => i === 0 || item.time - rendered[i - 1].time === 300))
  assert.deepEqual(rendered.map(item => item.close), items.map(item => Number(item.c)))
  assert.deepEqual(errors, [])
})

test('candle body and wick pixel heights match OHLC on every candle period', async t => {
  const dataset = bar => candles(25, bar).map((item, i) => ({
    ...item, o: i === 23 ? '104' : '100', c: i === 22 ? '104' : '100',
    h: i === 22 ? '106' : i === 23 ? '105' : '101', l: i === 22 ? '98' : '99',
  }))
  const { page, errors } = await fixture(t, { dataset })
  for (const bar of ['5m', '1m', '15m', '30m', '1D']) {
    await page.getByRole('button', { name: bar, exact: true }).click()
    await ready(page, 25)
    const geometry = await page.evaluate(item => {
      const { chart, series } = window.chartRecords.at(-1)
      const canvas = document.querySelector('.lightweight-chart canvas')
      const ratio = canvas.width / canvas.getBoundingClientRect().width
      const context = canvas.getContext('2d')
      const x = chart.timeScale().timeToCoordinate(window.chartTimeInEt(item.ts)) * ratio
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data
      const green = (x, y) => {
        const i = (y * canvas.width + x) * 4
        return pixels[i] === 34 && pixels[i + 1] === 197 && pixels[i + 2] === 94
      }
      const extent = offset => {
        const ys = []
        for (let y = 0; y < canvas.height; y++) {
          if ([-1, 0, 1].some(dx => green(Math.round(x + offset * ratio) + dx, y))) ys.push(y)
        }
        return ys.length ? ys.at(-1) - ys[0] : null
      }
      const y = price => series[0].priceToCoordinate(Number(price)) * ratio
      return { body: extent(4), wick: extent(0), expectedBody: Math.abs(y(item.o) - y(item.c)), expectedWick: y(item.l) - y(item.h) }
    }, dataset(bar)[22])
    assert.ok(geometry.body !== null && Math.abs(geometry.body - geometry.expectedBody) <= 2, `${bar} body ${JSON.stringify(geometry)}`)
    assert.ok(geometry.wick !== null && Math.abs(geometry.wick - geometry.expectedWick) <= 2, `${bar} wick ${JSON.stringify(geometry)}`)
    assert.ok((await hover(page, dataset(bar)[22])).includes('最高 106'))
    await page.mouse.move(0, 0)
  }
  assert.deepEqual(errors, [])
})

test('every bar shows a volCcyQuote volume pane that follows volume-only realtime updates', async t => {
  const withVolume = bar => candles(bar === '1D' ? 80 : bar === '1s' ? 7500 : 300, bar)
    .map((item, i) => ({ ...item, volCcyQuote: String(1000 + (i % 10) * 100) }))
  const { page, errors } = await fixture(t, { dataset: withVolume })
  const volume = () => page.evaluate(() => {
    const { chart, series } = window.chartRecords.at(-1)
    return { panes: chart.panes().length, pane: series[1]?.getPane().paneIndex(), data: series[1]?.data() ?? [] }
  })
  for (const [bar, count] of [['5m', 300], ['1s', 7500], ['1m', 300], ['15m', 300], ['30m', 300], ['1D', 80]]) {
    if (bar !== '5m') await page.getByRole('button', { name: bar, exact: true }).click()
    await ready(page, count)
    const { panes, pane, data: bars } = await volume()
    assert.equal(panes, 2, `${bar} has a volume pane`)
    assert.equal(pane, 1, `${bar} volume lives in pane 1`)
    assert.equal(bars.length, count, `${bar} volume bars align with prices`)
    assert.equal(bars.at(-1).value, Number(withVolume(bar).at(-1).volCcyQuote))
  }
  const screenshot = join(screenshotDir, 'trade-1D-volume.png')
  await page.screenshot({ path: screenshot })
  t.diagnostic(`1D volume screenshot: ${screenshot}`)

  // 当天未闭合日线：价格不变、只有成交量增长时，副图也必须刷新。
  const previous = withVolume('1D').at(-1)
  const today = { ...previous, ts: previous.ts + 86400000, confirm: '0', volCcyQuote: '500' }
  await push(page, today, '1D')
  assert.equal((await volume()).data.at(-1).value, 500)
  await push(page, { ...today, volCcyQuote: '999999' }, '1D')
  assert.equal((await volume()).data.at(-1).value, 999999)
  assert.ok((await hover(page, today)).includes('成交量 999999.00 USDT'))
  assert.deepEqual(errors, [])
})

test('A1:CHAN panel collapses by button and stays collapsed across bar switches', async t => {
  const { page, errors } = await fixture(t)
  await ready(page, 300)
  const panel = page.locator('section.chan-panel')
  const toggle = panel.getByRole('button', { name: /收起|展开/ })
  await page.waitForFunction(() => document.querySelector('.chan-stats') !== null)
  assert.equal(await toggle.getAttribute('aria-expanded'), 'true')

  await toggle.click()
  assert.equal(await toggle.getAttribute('aria-expanded'), 'false')
  assert.equal(await panel.locator('.chan-stats').count(), 0)
  assert.ok(!(await panel.locator('#chan-panel-body').isVisible()))
  const collapsedHeight = (await panel.boundingBox()).height
  const screenshot = join(screenshotDir, 'chan-collapsed.png')
  await page.screenshot({ path: screenshot })
  t.diagnostic(`collapsed screenshot: ${screenshot}`)

  // 切换周期会重新挂载面板，收起状态必须保留。
  await page.getByRole('button', { name: '15m', exact: true }).click()
  await ready(page, 300)
  assert.equal(await panel.getByRole('button', { name: /展开/ }).getAttribute('aria-expanded'), 'false')
  assert.equal(await panel.locator('.chan-stats').count(), 0)

  await panel.getByRole('button', { name: /展开/ }).click()
  await page.waitForFunction(() => document.querySelector('.chan-stats') !== null)
  assert.ok((await panel.boundingBox()).height > collapsedHeight * 3)
  assert.deepEqual(errors, [])
})
