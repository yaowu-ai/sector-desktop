const assert = require('node:assert/strict')
const fs = require('node:fs')
const Module = require('node:module')
const path = require('node:path')
const ts = require('typescript')

const root = path.resolve(__dirname, '..')
const srcRoot = path.join(root, 'src')
const originalResolveFilename = Module._resolveFilename

Module._resolveFilename = function resolveTsFilename(request, parent, isMain, options) {
  try {
    return originalResolveFilename.call(this, request, parent, isMain, options)
  } catch (error) {
    if (request.startsWith('.') && parent?.filename) {
      const base = path.resolve(path.dirname(parent.filename), request)
      for (const extension of ['.ts', '.tsx']) {
        if (fs.existsSync(base + extension)) {
          return base + extension
        }
      }
      for (const extension of ['.ts', '.tsx']) {
        if (fs.existsSync(path.join(base, `index${extension}`))) {
          return path.join(base, `index${extension}`)
        }
      }
    }
    throw error
  }
}

for (const extension of ['.ts', '.tsx']) {
  require.extensions[extension] = (module, filename) => {
    const source = fs.readFileSync(filename, 'utf8')
    const output = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        jsx: ts.JsxEmit.ReactJSX,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
      },
      fileName: filename,
    }).outputText
    module._compile(output, filename)
  }
}

function readSource(relativePath) {
  return fs.readFileSync(path.join(srcRoot, relativePath), 'utf8')
}

function assertRoute(source, key, scope, capability) {
  const keyIndex = source.indexOf(`key: '${key}'`)
  assert.notEqual(keyIndex, -1, `route ${key} should exist`)
  const routeBlock = source.slice(keyIndex, source.indexOf('}', keyIndex) + 1)
  assert.match(routeBlock, new RegExp(`scope: '${scope}'`), `route ${key} should have ${scope} scope`)
  if (capability) {
    assert.match(
      routeBlock,
      new RegExp(`capability: '${capability}'`),
      `route ${key} should declare ${capability}`,
    )
  }
}

const registry = require(path.join(srcRoot, 'platforms', 'registry.ts'))
assert.deepEqual(registry.PLATFORM_IDS, ['tiktok', 'instagram', 'whatsapp', 'douyin'])
assert.equal(registry.getPlatformDefinition('tiktok').status, 'supported')
assert.equal(registry.getPlatformDefinition('instagram').status, 'reserved')
assert.equal(registry.supportsCapability('tiktok', 'warmupTask'), true)
assert.equal(registry.supportsCapability('instagram', 'warmupTask'), false)
assert.equal(registry.getCapabilityStatus('instagram', 'warmupTask'), 'reserved')
assert.equal(registry.isExecutablePlatform('tiktok'), true)
assert.equal(registry.isExecutablePlatform('instagram'), false)
assert.match(
  registry.getAutomaticExecutionDisabledReason('instagram', 'scheduler'),
  /V1/,
)

const platformContext = require(path.join(srcRoot, 'app', 'PlatformContext.tsx'))
assert.equal(platformContext.PLATFORM_STORAGE_KEY, 'account-matrix-current-platform')
assert.equal(platformContext.DEFAULT_PLATFORM, 'tiktok')
assert.equal(platformContext.resolveInitialPlatform(null), 'tiktok')
assert.equal(platformContext.resolveInitialPlatform(''), 'tiktok')
assert.equal(platformContext.resolveInitialPlatform('instagram'), 'instagram')
assert.equal(platformContext.resolveInitialPlatform('unknown'), 'tiktok')

const pageScope = require(path.join(srcRoot, 'app', 'pageScope.tsx'))
assert.equal(pageScope.DEFAULT_PLATFORM_FILTER, 'all')
assert.equal(pageScope.resolveRoutePlatformFilter('current_platform', 'instagram', 'all'), 'instagram')
assert.equal(pageScope.resolveRoutePlatformFilter('all_platforms', 'instagram', 'all'), 'all')
assert.equal(pageScope.resolveRoutePlatformFilter('system', 'instagram', 'tiktok'), 'tiktok')

const routeScopeFrame = readSource(path.join('components', 'RouteScopeFrame.tsx'))
assert.match(routeScopeFrame, /DEFAULT_PLATFORM_FILTER/)
assert.match(routeScopeFrame, /resolveRoutePlatformFilter/)

const routes = readSource(path.join('app', 'routes.tsx'))
assertRoute(routes, 'home', 'all_platforms')
assertRoute(routes, 'accounts', 'current_platform', 'accountManagement')
assertRoute(routes, 'tasks', 'current_platform', 'warmupTask')
assertRoute(routes, 'records', 'all_platforms', 'records')
assertRoute(routes, 'stats', 'all_platforms', 'stats')
assertRoute(routes, 'settings', 'system')
assert.equal(routes.includes('currentPlatform'), false, 'left navigation routes should not depend on platform')

console.log('M14 frontend checks passed')
