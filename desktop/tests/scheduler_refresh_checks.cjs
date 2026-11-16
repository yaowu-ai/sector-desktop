const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

// Execute component hooks and events; UI widgets and external transports are boundaries.
function harness(relative, dependencies) {
  const states = [], effects = [], memos = [], refs = [], timers = new Map(), errors = []
  let cursor = 0, timerId = 0, tree
  const same = (a, b) => a && b && a.length === b.length && a.every((x, i) => x === b[i])
  const react = {
    useState(initial) {
      const i = cursor++
      if (!(i in states)) states[i] = typeof initial === 'function' ? initial() : initial
      return [states[i], value => { states[i] = typeof value === 'function' ? value(states[i]) : value }]
    },
    useRef(initial) { const i = cursor++; return refs[i] ??= { current: initial } },
    useMemo(fn, deps) {
      const i = cursor++
      if (!memos[i] || !same(memos[i].deps, deps)) memos[i] = { deps, value: fn() }
      return memos[i].value
    },
    useCallback(fn, deps) { return react.useMemo(() => fn, deps) },
    useEffect(fn, deps) {
      const i = cursor++
      if (!effects[i] || !same(effects[i].deps, deps)) {
        effects[i]?.cleanup?.()
        effects[i] = { deps, fn, pending: true }
      }
    },
  }
  const jsx = (type, props) => ({ type, props })
  const widgets = new Proxy({
    Form: { useForm: () => [{}], List: 'Form.List' },
    Typography: { Text: 'Text', Title: 'Title', Paragraph: 'Paragraph' },
    Layout: { Header: 'Header', Content: 'Content', Sider: 'Sider' },
    Empty: { PRESENTED_IMAGE_SIMPLE: 'empty' },
    message: { error: error => errors.push(error), success() {}, warning() {} },
  }, { get: (obj, key) => obj[key] ?? String(key) })
  const filename = path.resolve(__dirname, relative)
  const moduleObject = { exports: {} }
  const window = { location: { hash: '#scheduler' }, addEventListener() {}, removeEventListener() {},
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, { fn, delay }); return id },
    clearTimeout(id) { timers.delete(id) }, setInterval() { return ++timerId }, clearInterval() {} }
  const localRequire = id => {
    if (id === 'react') return react
    if (id === 'react/jsx-runtime') return { jsx, jsxs: jsx }
    if (id === 'antd') return widgets
    if (id === 'lucide-react') return new Proxy({}, { get: (_, key) => String(key) })
    if (Object.hasOwn(dependencies, id)) return dependencies[id]
    if (id.includes('refreshQueue')) {
      const m = { exports: {} }
      vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '../src/services/refreshQueue.ts'), 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS },
      }).outputText, { module: m, exports: m.exports, Promise })
      return m.exports
    }
    if (id === 'dayjs') return require('dayjs')
    return new Proxy({}, { get: (_, key) => String(key) })
  }
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, { module: moduleObject, exports: moduleObject.exports, require: localRequire, window, Set, Map, Date, Promise, queueMicrotask })
  const component = Object.values(moduleObject.exports)[0]
  return { errors, timers,
    render(props = {}) {
      cursor = 0
      tree = component(props)
      for (const effect of effects) if (effect?.pending) {
        effect.pending = false
        effect.cleanup = effect.fn()
      }
      return tree
    },
    unmount() { effects.forEach(e => e?.cleanup?.()); },
  }
}
const flush = () => new Promise(resolve => setImmediate(resolve))
function find(node, type) {
  if (!node || typeof node !== 'object') return []
  if (Array.isArray(node)) return node.flatMap(n => find(n, type))
  return [...(node.type === type ? [node] : []), ...Object.values(node.props ?? {}).flatMap(n => find(n, type))]
}

async function schedulerPage() {
  const platform = { currentPlatform: 'tiktok' }, requests = [], histories = []
  let failHistory = false
  let browserRefreshes = 0
  const h = harness('../src/platforms/tiktok/pages/SchedulerPage.tsx', {
    '../../../app/PlatformContext': { usePlatformContext: () => platform },
    '../../../app/DesktopAuthContext': { useDesktopAuth: () => ({ license: {} }) },
    '../../../app/BrowserStatusContext': { useBrowserStatuses: () => ({
      bitbrowser: null, ixbrowser: null, refresh: async () => { browserRefreshes++ },
    }) },
    '../../../services/desktopApi': { readDesktopLicenseLimits: () => ({ scheduler: true }) },
    '../../../services/api': { getSchedulerSnapshot: () => new Promise((resolve, reject) => requests.push({ resolve, reject })) },
    '../services': { querySchedulerJobRuns: async query => {
      histories.push(query)
      if (failHistory) throw new Error('history failed before health returned')
      return []
    } },
    '../..': { isExecutablePlatform: p => p === 'tiktok', getPlatformLabel: p => p,
      getAutomaticExecutionDisabledReason: () => '当前平台暂不支持调度' },
  })
  const snapshot = id => ({ config: { accounts: [{ id, platform: platform.currentPlatform, enabled: true, scheduled: true,
    activeHours: [[9, 12]], browserProvider: 'builtin_chromium' }], schedulerSettings: { firesPerDay: 3 } },
    process: { status: 'stopped' }, health: { status: 'stopped', jobs: [], ipGroupConflicts: [], runLock: {} } })
  h.render()
  assert.equal(requests.length, 1)
  assert.equal(h.timers.size, 0, 'no new poll until the active request finishes')
  platform.currentPlatform = 'instagram'
  h.render()
  assert.equal(requests.length, 1, 'scope changes must queue, not overlap the previous request')
  requests[0].resolve(snapshot('obsolete'))
  await flush()
  assert.equal(requests.length, 2)
  assert.ok(find(h.render(), 'Table').every(t => t.props.dataSource.length === 0), 'discard the previous scope response')
  requests[1].resolve(snapshot('latest'))
  await flush()
  const tree = h.render()
  assert.equal(find(tree, 'Table').at(-1).props.dataSource[0].id, 'latest')
  assert.deepEqual(histories.map(q => q.platform), ['tiktok', 'instagram'])
  assert.equal(browserRefreshes, 0, 'polls reuse shell browser statuses')
  const timer = [...h.timers.values()][0]
  assert.equal(timer.delay, 10000)
  h.timers.clear()
  timer.fn()
  requests.at(-1).reject(new Error('history busy'))
  await flush()
  assert.equal(h.errors.length, 1)
  assert.equal(h.timers.size, 1, 'recover polling after an error')
  failHistory = true
  const retry = [...h.timers.values()][0]
  h.timers.clear()
  retry.fn()
  await flush()
  assert.equal(h.timers.size, 0, 'a failed sibling must not release the active health request')
  requests.at(-1).resolve(snapshot('still-current'))
  await flush()
  assert.equal(h.errors.length, 2)
  assert.equal(h.timers.size, 1)
  h.unmount()
  assert.equal(h.timers.size, 0)
}

async function browserSharing() {
  let configReads = 0, bitProbes = 0, ixProbes = 0, finish
  const routes = [{ key: 'scheduler', label: '调度计划', element: 'page' }]
  const context = { Provider: 'BrowserProvider' }
  const h = harness('../src/components/AppShell.tsx', {
    '../app/BrowserStatusContext': { BrowserStatusContext: context },
    '../app/DesktopAuthContext': { useDesktopAuth: () => ({ session: null }) },
    '../app/DesktopNotificationsContext': { useDesktopNotifications: () => ({ unreadCount: 0 }) },
    '../app/PlatformContext': { usePlatformContext: () => ({ currentPlatformDefinition: { capabilities: {} } }) },
    '../app/routePermissions': { filterRoutesByRole: r => r, filterRoutesByPlatformAvailability: r => r,
      normalizeDesktopUserRole: () => 'technician', DESKTOP_USER_ROLES: { technician: 'technician' } },
    '../app/routes': { appRoutes: routes, routes },
    '../services/api': {
      loadSchedulerConfig: () => { configReads++; return new Promise(resolve => { finish = resolve }) },
      checkBitbrowserApi: async () => { bitProbes++; return { available: true } },
      checkIxbrowserApi: async () => { ixProbes++; return { available: true } },
      getCurrentRunStatus: async () => ({ status: 'idle' }),
    },
  })
  let tree = h.render()
  const refresh = find(tree, 'BrowserProvider')[0].props.value.refresh
  const first = refresh(), second = refresh()
  assert.equal(first, second, 'shell and page must join the same in-flight browser check')
  assert.equal(configReads, 1)
  finish({ accounts: [{ browserProvider: 'bitbrowser' }] })
  await Promise.all([first, second]); await flush()
  tree = h.render()
  assert.equal(bitProbes, 1)
  assert.equal(ixProbes, 0, 'do not probe an unused provider')
  assert.equal(find(tree, 'BrowserProvider')[0].props.value.bitbrowser.available, true)
  const third = find(tree, 'BrowserProvider')[0].props.value.refresh()
  finish({ accounts: [{ browserProvider: 'builtin_chromium' }] })
  await third
  tree = h.render()
  assert.equal(find(tree, 'BrowserProvider')[0].props.value.bitbrowser, null, 'configuration changes invalidate the old provider status')
  assert.equal(bitProbes, 1)
  h.unmount()
}

Promise.resolve().then(schedulerPage).then(browserSharing)
  .then(() => console.log('scheduler components: serial polling, stale scope, error recovery and shared provider probes passed'))
  .catch(error => { console.error(error); process.exitCode = 1 })
