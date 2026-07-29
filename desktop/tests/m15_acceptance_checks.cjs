const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const projectRoot = path.resolve(root, '..')
const srcRoot = path.join(root, 'src')
const rustRoot = path.join(root, 'src-tauri', 'src')

function read(...parts) {
  return fs.readFileSync(path.join(...parts), 'utf8')
}

function routeBlock(routesSource, key) {
  const keyIndex = routesSource.indexOf(`key: '${key}'`)
  assert.notEqual(keyIndex, -1, `route ${key} should exist`)
  return routesSource.slice(keyIndex, routesSource.indexOf('}', keyIndex) + 1)
}

function assertContains(source, expected, label) {
  assert.ok(source.includes(expected), label)
}

const routes = read(srcRoot, 'app', 'routes.tsx')
const appShell = read(srcRoot, 'components', 'AppShell.tsx')
const platformSelector = read(srcRoot, 'components', 'PlatformSelector.tsx')
const routeScopeFrame = read(srcRoot, 'components', 'RouteScopeFrame.tsx')
const accountPage = read(srcRoot, 'pages', 'AccountPage.tsx')
const taskPage = read(srcRoot, 'pages', 'TaskPage.tsx')
const targetPage = read(srcRoot, 'pages', 'TargetEngagementPage.tsx')
const commentPage = read(srcRoot, 'pages', 'CommentPoolPage.tsx')
const homePage = read(srcRoot, 'pages', 'HomePage.tsx')
const recordsPage = read(srcRoot, 'pages', 'ExecutionRecordPage.tsx')
const sessionsPage = read(srcRoot, 'pages', 'SessionLogPage.tsx')
const statsPage = read(srcRoot, 'pages', 'StatsPage.tsx')
const api = read(srcRoot, 'services', 'api.ts')
const types = read(srcRoot, 'services', 'types.ts')
const processRs = read(rustRoot, 'commands', 'process.rs')
const configRs = read(rustRoot, 'commands', 'config.rs')
const filesRs = read(rustRoot, 'commands', 'files.rs')
const pythonRunner = read(projectRoot, 'src', 'core', 'runner.py')
const pythonPlatformConfig = read(projectRoot, 'src', 'platform_config.py')

assertContains(platformSelector, 'value={currentPlatform}', 'top platform selector should bind current platform')
assertContains(platformSelector, 'onChange={setCurrentPlatform}', 'top platform selector should switch platform')
assertContains(appShell, '<PlatformSelector onOpenSettings={() => setActiveKey(\'platforms\')} />', 'more platforms should open platform settings')

assert.equal(routes.includes("key: 'platforms'") && routes.includes('platformSettingsRoute'), true)
assert.equal(routeBlock(routes, 'platforms').includes("scope: 'system'"), true)
assert.equal(appShell.includes('items={routes.map'), true, 'left navigation should only use main routes')
assert.equal(appShell.includes('items={appRoutes.map'), false, 'left navigation should not include platform settings')
assert.equal(routes.includes('children:'), false, 'left navigation should not define platform submenu children')

assertContains(accountPage, 'account.platform === currentPlatform', 'account page should filter by current platform')
assertContains(accountPage, 'platform: currentPlatform', 'new/saved account payloads should include current platform')
assertContains(taskPage, 'nextSnapshot.accounts.filter((account) => account.platform === currentPlatform)', 'warmup task should filter accounts by current platform')
assertContains(taskPage, 'saveFypSettings(normalizeFypSettings(values), currentPlatform)', 'warmup settings should save current platform')
assertContains(taskPage, 'platform: currentPlatform', 'warmup run request should include current platform')
assertContains(targetPage, 'queryTargetWatermarks({ platform: currentPlatform })', 'target watermarks should query current platform')
assertContains(targetPage, 'saveTargetEngagementSettings(normalizeTargetSettings(values), currentPlatform)', 'target settings should save current platform')
assertContains(targetPage, 'platform: currentPlatform', 'target run request should include current platform')
assertContains(commentPage, 'loadCommentPools(currentPlatform)', 'comment pools should load current platform')
assertContains(commentPage, 'platform: currentPlatform', 'comment pools should save current platform')
assertContains(api, "invoke<CommentPoolsSnapshot>('load_comment_pools', { platform })", 'comment pool API should send platform')
assertContains(types, 'platform?: Platform', 'comment pool save request should include platform')
assertContains(filesRs, 'platform_comment_paths(&paths, &platform)', 'comment pool backend should resolve platform-specific paths')
assertContains(filesRs, 'save_platform_comment_files_config', 'comment pool backend should persist platform comment files')

for (const [source, pageName] of [
  [homePage, 'home'],
  [recordsPage, 'execution records'],
  [sessionsPage, 'session log'],
  [statsPage, 'stats'],
]) {
  assert.ok(
    source.includes("useState<PlatformFilterValue>('all')") ||
      source.includes("platform: 'all'") ||
      source.includes('DEFAULT_FILTERS'),
    `${pageName} should default to all platforms`,
  )
  assertContains(source, '<PlatformScopeFilter', `${pageName} should expose platform filter`)
}
assertContains(recordsPage, 'queryActionLogs(actionFilter)', 'execution records should query with platform filter')
assertContains(statsPage, 'queryFypStats(request)', 'stats should query fyp with platform filter')
assertContains(statsPage, 'queryTargetStats(request)', 'stats should query target with platform filter')

assert.equal(routeBlock(routes, 'settings').includes("scope: 'system'"), true, 'system settings should be system scoped')
assert.equal(routeBlock(routes, 'diagnostic').includes("scope: 'system'"), true, 'diagnostic should be system scoped')
assertContains(routeScopeFrame, "scope === 'current_platform' && capability", 'current platform routes should gate capabilities')
assertContains(routeScopeFrame, 'supportsCapability(currentPlatform, capability)', 'frontend should reject unsupported capabilities')
assertContains(processRs, 'ensure_platform_capability(&platform, capability)', 'backend should validate platform capability')
assertContains(processRs, 'ensure_platform_can_execute(&platform, capability, &account_ids)', 'backend should reject reserved execution')
assertContains(configRs, 'platform \'{}\' capability \'{}\' is', 'backend capability error should include platform and capability')

assertContains(pythonPlatformConfig, 'DEFAULT_PLATFORM = "tiktok"', 'legacy Python config should default to TikTok')
assertContains(pythonRunner, 'get_runner(account_platform(account)).can_execute()', 'Python runner should skip non-executable platforms')
assertContains(configRs, 'unwrap_or_else(|| "tiktok".to_string())', 'legacy Rust account mapping should default missing platform to TikTok')

console.log('M15 acceptance checks passed')
