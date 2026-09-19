const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const srcRoot = path.join(root, 'src')

function read(...parts) {
  return fs.readFileSync(path.join(srcRoot, ...parts), 'utf8')
}

const capabilities = read('platforms', 'common', 'capabilities.ts')
const reservedModule = read('platforms', 'common', 'reservedModule.ts')

assert.match(
  read('platforms', 'types.ts'),
  /export interface ReservedPlatformEntry/,
  'reserved module entries should have a shared type',
)
assert.match(
  reservedModule,
  /createReservedPlatformEntry/,
  'reserved modules should use the shared entry factory',
)

for (const platform of ['instagram', 'whatsapp', 'douyin']) {
  const moduleSource = read('platforms', platform, 'index.ts')
  const pageSource = read('platforms', platform, 'pages', 'index.ts')
  const serviceSource = read('platforms', platform, 'services', 'index.ts')

  assert.match(
    moduleSource,
    /createReservedPlatformModule/,
    `${platform} should remain a reserved platform module`,
  )
  assert.match(
    pageSource,
    /createReservedPlatformEntry/,
    `${platform} pages should use the reserved entry factory`,
  )
  assert.match(
    serviceSource,
    /createReservedPlatformEntry/,
    `${platform} services should use the reserved entry factory`,
  )
  assert.doesNotMatch(
    `${pageSource}\n${serviceSource}`,
    /from ['"]\.\.\.['"]|from ['"]\.\.['"]/,
    `${platform} reserved entries must not import their parent module`,
  )
  assert.doesNotMatch(
    `${moduleSource}\n${pageSource}\n${serviceSource}`,
    /tiktok|TikTok|platforms\/tiktok/,
    `${platform} reserved module must not reference TikTok implementation`,
  )
}

assert.match(
  capabilities,
  /export const RESERVED_CAPABILITIES[\s\S]*accountManagement: 'reserved'/,
  'reserved account management capability should not be reported as supported',
)
for (const capability of [
  'browserProfile',
  'warmupTask',
  'scheduler',
  'comments',
  'records',
  'stats',
  'diagnostics',
]) {
  assert.match(
    capabilities,
    new RegExp(`${capability}: 'reserved'`),
    `${capability} should be reserved for non-executable platforms`,
  )
}

console.log('reserved platform module checks passed')
