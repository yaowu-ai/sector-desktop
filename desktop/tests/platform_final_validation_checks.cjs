const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const srcRoot = path.join(root, 'src')

function read(...parts) {
  return fs.readFileSync(path.join(srcRoot, ...parts), 'utf8')
}

function collectSourceFiles(directory) {
  return fs
    .readdirSync(directory, { withFileTypes: true })
    .flatMap((entry) => {
      const fullPath = path.join(directory, entry.name)
      if (entry.isDirectory()) return collectSourceFiles(fullPath)
      return /\.(ts|tsx)$/.test(entry.name) ? [fullPath] : []
    })
}

const legacyBusinessPages = [
  'AccountPage.tsx',
  'BrowserProfilePage.tsx',
  'CommentPoolPage.tsx',
  'ExecutionRecordPage.tsx',
  'GmailSetupPage.tsx',
  'HomePage.tsx',
  'ProfileStatsPage.tsx',
  'SchedulerPage.tsx',
  'SessionLogPage.tsx',
  'StatsPage.tsx',
  'TargetEngagementPage.tsx',
  'TaskPage.tsx',
]

for (const fileName of legacyBusinessPages) {
  assert.equal(
    fs.existsSync(path.join(srcRoot, 'pages', fileName)),
    false,
    `legacy business page should be removed from src/pages: ${fileName}`,
  )
}

assert.equal(
  fs.existsSync(path.join(srcRoot, 'services', 'platforms.ts')),
  false,
  'legacy shared platform service facade should be removed',
)

const sourceFiles = collectSourceFiles(srcRoot)
const source = sourceFiles
  .map((filePath) => fs.readFileSync(filePath, 'utf8'))
  .join('\n')

for (const staleReference of [
  'PlatformScopeFilter',
  'DEFAULT_PLATFORM_FILTER',
  'resolveRoutePlatformFilter',
  'setPlatformFilter',
  "scope === 'all_platforms'",
]) {
  assert.equal(
    source.includes(staleReference),
    false,
    `stale platform filter reference should be absent: ${staleReference}`,
  )
}

const routes = read('app', 'routes.tsx')
assert.equal(routes.includes("scope: 'all_platforms'"), false)
assert.match(
  routes,
  /scope: 'current_platform'/,
  'business routes should use current platform scope',
)
assert.match(routes, /scope: 'system'/, 'system routes should remain system scoped')

for (const platform of ['instagram', 'whatsapp', 'douyin']) {
  const moduleSource = read('platforms', platform, 'index.ts')
  assert.match(moduleSource, /implementation: 'reserved'|createReservedPlatformModule/)
  assert.doesNotMatch(moduleSource, /platforms\/tiktok|from ['"][^'"]*tiktok/)
}

console.log('platform final validation checks passed')
