const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const root = path.resolve(__dirname, '..')
const sourcePath = path.join(root, 'src', 'services', 'desktopApi.ts')

function loadDesktopApi(env) {
  const source = fs
    .readFileSync(sourcePath, 'utf8')
    .replaceAll('import.meta.env', '__env')

  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    },
    fileName: sourcePath,
  }).outputText

  const storage = new Map()
  const module = { exports: {} }
  const context = {
    __env: env,
    exports: module.exports,
    module,
    require,
    window: {
      localStorage: {
        getItem(key) {
          return storage.has(key) ? storage.get(key) : null
        },
        setItem(key, value) {
          storage.set(key, String(value))
        },
        removeItem(key) {
          storage.delete(key)
        },
      },
    },
  }

  vm.runInNewContext(compiled, context, { filename: sourcePath })
  return { api: module.exports, storage }
}

const prodBaseUrl = 'https://sector.mechlabs.cn/api/desktop'
const qasBaseUrl = 'https://qasector.mechlabs.cn/api/desktop'
const storageKey = 'account-matrix-desktop-api-base-url'

{
  const { api, storage } = loadDesktopApi({
    MODE: 'production',
    VITE_DESKTOP_API_BASE_URL: prodBaseUrl,
  })
  storage.set(storageKey, qasBaseUrl)

  assert.equal(
    api.getDesktopApiBaseUrl(),
    prodBaseUrl,
    'production desktop must ignore a persisted QAS API base URL',
  )
  assert.equal(
    storage.get(storageKey),
    prodBaseUrl,
    'production desktop should replace the stale QAS API base with the prod default',
  )
}

{
  const { api, storage } = loadDesktopApi({
    MODE: 'production',
  })

  assert.equal(
    api.getDesktopApiBaseUrl(),
    prodBaseUrl,
    'production desktop must fall back to the prod API base URL when VITE_DESKTOP_API_BASE_URL is missing',
  )

  api.saveDesktopApiBaseUrl('http://localhost:3000/api/desktop')

  assert.equal(
    storage.get(storageKey),
    prodBaseUrl,
    'production desktop must not persist localhost when the build-time API env is missing',
  )
}

{
  const { api, storage } = loadDesktopApi({
    MODE: 'production',
    VITE_DESKTOP_API_BASE_URL: prodBaseUrl,
  })
  storage.set(storageKey, 'http://localhost:3000/api/desktop')

  assert.equal(
    api.getDesktopApiBaseUrl(),
    prodBaseUrl,
    'production desktop must ignore a persisted localhost API base URL',
  )
}

{
  const { api, storage } = loadDesktopApi({
    MODE: 'development',
    VITE_DESKTOP_API_BASE_URL: prodBaseUrl,
  })
  storage.set(storageKey, qasBaseUrl)

  assert.equal(
    api.getDesktopApiBaseUrl(),
    qasBaseUrl,
    'non-production desktop builds should continue to allow API base overrides',
  )
}

console.log('desktop API base URL checks passed')
