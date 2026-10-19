const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const sourcePath = path.resolve(__dirname, '../src/app/DesktopAccountStatsReporter.tsx')
const source = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText

function harness() {
  const effects = []
  const timers = new Map()
  const sent = []
  let timerId = 0
  let failRead = false
  let resolveRead
  let deferred = false
  const auth = { session: { userId: '1', accessToken: 'first-token' }, apiBaseUrl: 'https://example.invalid/api/desktop',
    device: { status: 'active' }, license: { status: 'active' } }
  const metrics = { accountCount: 3, successCount: 2, commentEvidenceCount: 1,
    followingCount: 1, followersCount: 0, likedCount: 1, likesCount: 0 }
  const ref = { current: auth }
  const module = { exports: {} }
  vm.runInNewContext(source, { module, exports: module.exports, Date,
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, { fn, delay }); return id },
    clearTimeout(id) { timers.delete(id) },
    require(id) {
      if (id === 'react') return { useEffect(fn) { effects.push(fn) }, useRef() { return ref } }
      if (id === './DesktopAuthContext') return { useDesktopAuth: () => auth }
      if (id === '../services/api') return { queryAccountCoverage: async (platform) => {
        assert.equal(platform, 'tiktok')
        if (failRead) throw new Error('SQLite busy')
        if (deferred) return new Promise((resolve) => { resolveRead = resolve })
        return metrics
      } }
      if (id === '../services/desktopApi') return { reportDesktopAccountStats: async (data) => { sent.push(data) } }
      throw new Error(`Unexpected import: ${id}`)
    },
  }, { filename: sourcePath })
  return { auth, metrics, timers, sent, effects, component: module.exports.DesktopAccountStatsReporter,
    failRead: () => { failRead = true }, defer: () => { deferred = true }, resolve: () => resolveRead(metrics) }
}

const flush = () => new Promise((resolve) => setImmediate(resolve))

async function checkTransport() {
  const filename = path.resolve(__dirname, '../src/services/desktopApi.ts')
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8').replaceAll('import.meta.env', '__env'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const sent = []
  const module = { exports: {} }
  vm.runInNewContext(compiled, { module, exports: module.exports, require, AbortSignal, URL,
    __env: { MODE: 'test' }, window: { localStorage: { getItem: () => 'device-known' } },
    fetch: async (url, options) => {
      sent.push({ url, options })
      return { ok: true, json: async () => ({ success: true, data: { recorded: true, metricDate: '2026-10-19' } }) }
    },
  }, { filename })
  const metrics = { accountCount: 3, successCount: 2, commentEvidenceCount: 1,
    followingCount: 1, followersCount: 0, likedCount: 1, likesCount: 0 }
  await module.exports.reportDesktopAccountStats({ session: { accessToken: 'fresh-token' },
    apiBaseUrl: 'https://example.invalid/api/desktop/', observedAt: '2026-10-19T04:00:00Z', metrics })
  assert.equal(sent[0].url, 'https://example.invalid/api/desktop/account-stats/report')
  assert.equal(sent[0].options.headers.Authorization, 'Bearer fresh-token')
  assert.equal(sent[0].options.method, 'POST')
  assert.deepEqual(JSON.parse(sent[0].options.body), {
    deviceFingerprint: 'device-known', observedAt: '2026-10-19T04:00:00Z', metrics,
  })
  assert.ok(sent[0].options.signal)
}

async function main() {
  await checkTransport()
  const h = harness()
  h.component()
  const stop = h.effects[0]()
  await flush()
  assert.equal(h.sent.length, 1)
  assert.equal(h.sent[0].metrics.likedCount, 1)
  assert.equal([...h.timers.values()][0].delay, 3_600_000)
  h.auth.session = { userId: '1', accessToken: 'refreshed-token' }
  const next = [...h.timers.values()][0]
  h.timers.clear(); await next.fn(); await flush()
  assert.equal(h.sent.at(-1).session.accessToken, 'refreshed-token')
  h.failRead()
  const retry = [...h.timers.values()][0]
  h.timers.clear(); await retry.fn(); await flush()
  assert.equal([...h.timers.values()][0].delay, 60_000)
  assert.equal(h.sent.length, 2)
  stop()
  assert.equal(h.timers.size, 0)

  const cancelled = harness()
  cancelled.defer(); cancelled.component()
  const cleanup = cancelled.effects[0]()
  cleanup(); cancelled.resolve(); await flush()
  assert.equal(cancelled.sent.length, 0)
  assert.equal(cancelled.timers.size, 0)

  const unauthorized = harness()
  unauthorized.auth.license.status = 'revoked'
  unauthorized.component()
  unauthorized.effects[0]()
  await flush()
  assert.equal(unauthorized.sent.length, 0)
  console.log('Account statistics reporter: login, hourly upload, fresh token, retry, cancellation and authorization passed')
}
main().catch((error) => { console.error(error); process.exitCode = 1 })
