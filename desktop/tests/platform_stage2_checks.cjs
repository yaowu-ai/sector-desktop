const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const srcRoot = path.join(root, 'src')

function read(...parts) {
  return fs.readFileSync(path.join(srcRoot, ...parts), 'utf8')
}

function routeBlock(routesSource, key) {
  const keyIndex = routesSource.indexOf(`key: '${key}'`)
  assert.notEqual(keyIndex, -1, `route ${key} should exist`)
  return routesSource.slice(keyIndex, routesSource.indexOf('}', keyIndex) + 1)
}

const routes = read('app', 'routes.tsx')
const routePermissions = read('app', 'routePermissions.ts')
const appShell = read('components', 'AppShell.tsx')
const pageSources = [
  read('platforms', 'tiktok', 'pages', 'HomePage.tsx'),
  read('platforms', 'tiktok', 'pages', 'ExecutionRecordPage.tsx'),
  read('platforms', 'tiktok', 'pages', 'SessionLogPage.tsx'),
  read('platforms', 'tiktok', 'pages', 'StatsPage.tsx'),
  read('pages', 'DiagnosticPage.tsx'),
]

for (const key of [
  'home',
  'profile-stats',
  'accounts',
  'browser',
  'tasks',
  'target-engagement',
  'scheduler',
  'comments',
  'records',
  'sessions',
  'stats',
  'gmail',
  'diagnostic',
]) {
  const block = routeBlock(routes, key)
  assert.match(block, /scope: 'current_platform'/, `${key} must be current-platform scoped`)
}

for (const key of [
  'profile',
  'plans',
  'license-devices',
  'contact',
  'notifications',
  'about',
  'settings',
]) {
  assert.match(
    routePermissions,
    new RegExp(`['"]${key}['"]`),
    `${key} must remain a system menu route`,
  )
}

assert.match(
  routePermissions,
  /return routes\.filter\(\(route\) => SYSTEM_MENU_ROUTE_KEYS\.has\(route\.key\)\)/,
  'reserved platforms must expose only system menu routes',
)
assert.match(
  appShell,
  /filterRoutesByPlatformAvailability\(/,
  'AppShell must apply platform availability to the left menu',
)
assert.match(
  appShell,
  /buildSiderMenuItems\(visibleRoutes/,
  'left menu must be built from platform-filtered routes',
)

for (const source of pageSources) {
  assert.match(source, /usePlatformContext/, 'TikTok pages must use the global platform context')
  assert.doesNotMatch(
    source,
    /title=\{\`\$\{currentPlatformDefinition\.localeName\} \//,
    'page headers must not duplicate the global platform prefix',
  )
  assert.doesNotMatch(
    source,
    /PlatformScopeFilter|PlatformFilterValue|platformFilter|selectedPlatform/,
    'TikTok pages must not expose an independent platform selector',
  )
  assert.doesNotMatch(
    source,
    /Instagram|WhatsApp|抖音|全部平台/,
    'TikTok pages must not contain other platform filter options',
  )
}

console.log('platform stage 2 checks passed')
