const assert = require('node:assert/strict')
const { test } = require('node:test')
const { webcrypto } = require('node:crypto')
const fs = require('node:fs')
const vm = require('node:vm')
const ts = require('typescript')
const path = require('node:path')

function apiHarness() {
  const calls = [], memory = new Map()
  let response = { success: true, data: { ticket: 't'.repeat(43), expiresAt: Date.now() + 60000 } }
  const source = fs.readFileSync(path.resolve(__dirname, '../src/services/desktopApi.ts'), 'utf8').replaceAll('import.meta.env', '__env')
  const exports = {}
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, {
    exports, __env: { MODE: 'test' }, crypto: webcrypto, Date, Number, URL, AbortSignal,
    window: { localStorage: { getItem: key => memory.get(key), setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key) } },
    fetch: async (url, options) => { calls.push({ url, ...options }); return { ok: true, json: async () => response } },
  })
  return { api: exports, calls, memory, reply: value => { response = value } }
}

test('desktop credential stays on the central API while only a short ticket is returned', async () => {
  const h = apiHarness()
  const session = h.api.buildDesktopSession('sector-user', { accessToken: 'desktop-private', refreshToken: 'refresh-private', expiresIn: 900, user: { userId: '7' } })
  const result = await h.api.issueDesktopWhatsAppTicket({ session, apiBaseUrl: 'https://sector.example/api/desktop',
    nonce: 'n'.repeat(43), workspaceOrigin: 'https://wa.example', parentOrigin: 'tauri://localhost' })
  assert.equal(result.ticket, 't'.repeat(43))
  const request = h.calls[0]
  assert.equal(request.url, 'https://sector.example/api/desktop/whatsapp/ticket')
  assert.equal(request.headers.Authorization, 'Bearer desktop-private')
  assert(!request.body.includes('desktop-private') && !request.body.includes('refresh-private'))
  assert.equal(JSON.parse(request.body).workspaceOrigin, 'https://wa.example')
})
test('refresh preserves isolation context while another desktop login gets a fresh context', () => {
  const h = apiHarness(), response = { accessToken: 't1', expiresIn: 900, user: { userId: '7' } }
  const first = h.api.buildDesktopSession('first', response)
  const refreshed = h.api.applyDesktopAuthResponse(first, { ...response, accessToken: 't2' })
  const nextLogin = h.api.buildDesktopSession('second', { ...response, user: { userId: '8' } })
  assert.equal(first.whatsappContext, refreshed.whatsappContext)
  assert.notEqual(first.whatsappContext, nextLogin.whatsappContext)
  h.api.saveDesktopSession({ ...first, whatsappContext: undefined })
  const restored = h.api.loadDesktopSession()
  assert(restored.whatsappContext)
  assert.equal(h.api.loadDesktopSession().whatsappContext, restored.whatsappContext)
})
test('expired and malformed authority responses never become a bridge ticket', async () => {
  const h = apiHarness(), params = { session: { accessToken: 'private' }, apiBaseUrl: 'https://sector.example/api/desktop',
    nonce: 'n'.repeat(43), workspaceOrigin: 'https://wa.example', parentOrigin: 'tauri://localhost' }
  for (const data of [{ ticket: 'long-term-token', expiresAt: Date.now() + 60000 }, { ticket: 't'.repeat(43), expiresAt: 1 }]) {
    h.reply({ success: true, data })
    await assert.rejects(() => h.api.issueDesktopWhatsAppTicket(params), /无效或已过期/)
  }
})

test('an old desktop entitlement response cannot restore a signed-out user over a new login', async () => {
  const h = apiHarness(), exports = {}, states = []
  let releaseOld, subscriptions = 0
  const subscription = { status: 'active' }, license = { status: 'active' }
  const api = { ...h.api, getDesktopApiBaseUrl: () => 'https://sector.example/api/desktop',
    desktopLogin: async username => ({ accessToken: username, expiresIn: 900, user: { userId: username } }),
    loadCurrentSubscription: () => ++subscriptions === 1 ? new Promise(resolve => { releaseOld = resolve }) : Promise.resolve(subscription),
    activateDesktopDevice: async () => ({}), loadVerifiedCurrentLicense: async () => license,
    readDesktopLicenseLimits: () => ({ scheduler: false }),
  }
  const react = { createContext: () => ({ Provider: 'provider' }), useCallback: fn => fn,
    useContext: () => null, useEffect() {}, useMemo: fn => fn(), useRef: value => ({ current: value }),
    useState: initial => { const index = states.length; states.push(typeof initial === 'function' ? initial() : initial)
      return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value }] },
  }
  const source = fs.readFileSync(path.resolve(__dirname, '../src/app/DesktopAuthContext.tsx'), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, {
    exports, setTimeout, clearTimeout, console,
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail } },
    window: { dispatchEvent() {} },
    require: id => id === 'react' ? react : id === 'react/jsx-runtime' ? { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) }
      : id.includes('desktopApi') ? api : {},
  })
  const auth = exports.DesktopAuthProvider({ children: null }).props.value
  const oldLogin = auth.login({ apiBaseUrl: 'https://sector.example/api/desktop', username: 'old-user', password: 'fixture' })
  await new Promise(setImmediate)
  await auth.logout()
  assert.equal(h.memory.has('account-matrix-desktop-session'), false)
  const newLogin = await auth.login({ apiBaseUrl: 'https://sector.example/api/desktop', username: 'new-user', password: 'fixture' })
  assert.equal(newLogin.authorized, true)
  releaseOld(subscription)
  assert.equal((await oldLogin).authorized, false)
  assert.equal(JSON.parse(h.memory.get('account-matrix-desktop-session')).userId, 'new-user')
  assert.equal(states[1].userId, 'new-user')
})
