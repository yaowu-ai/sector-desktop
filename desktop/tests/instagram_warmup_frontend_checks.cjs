const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const desktopRoot = path.resolve(__dirname, '..')
const projectRoot = path.resolve(desktopRoot, '..')

function read(...parts) {
  return fs.readFileSync(path.join(...parts), 'utf8')
}

function assertContains(source, expected, label) {
  assert.ok(source.includes(expected), label)
}

function assertNotContains(source, unexpected, label) {
  assert.ok(!source.includes(unexpected), label)
}

const registry = read(desktopRoot, 'src', 'platforms', 'registry.ts')
const taskPage = read(desktopRoot, 'src', 'pages', 'TaskPage.tsx')
const platformPage = read(desktopRoot, 'src', 'pages', 'PlatformPage.tsx')
const api = read(desktopRoot, 'src', 'services', 'api.ts')
const types = read(desktopRoot, 'src', 'services', 'types.ts')
const configRs = read(desktopRoot, 'src-tauri', 'src', 'commands', 'config.rs')
const processRs = read(desktopRoot, 'src-tauri', 'src', 'commands', 'process.rs')
const mainRs = read(desktopRoot, 'src-tauri', 'src', 'main.rs')
const filesRs = read(desktopRoot, 'src-tauri', 'src', 'commands', 'files.rs')
const bridgePy = read(projectRoot, 'src', 'platforms', 'instagram_runner', 'bridge.py')
const runnerPy = read(projectRoot, 'src', 'platforms', 'instagram_runner', 'runner.py')

assertContains(registry, "id: 'instagram'", 'platform registry should include Instagram')
assertContains(registry, "status: 'supported'", 'Instagram should be marked supported')
assertContains(registry, 'automaticExecutionSupported: true', 'Instagram should expose automatic execution')
assertContains(registry, 'INSTAGRAM_CAPABILITIES', 'Instagram should have its own capability matrix')
assertContains(registry, 'instagramWarmup', 'Instagram default config should include warmup settings')

assertContains(types, 'export interface InstagramWarmupSettings', 'desktop service types should model Instagram warmup')
assertContains(types, 'instagramWarmup?: InstagramWarmupSettings', 'config snapshot should include Instagram warmup')
assertContains(types, "'warmup'", 'task run type should include warmup')
assertContains(api, 'saveInstagramWarmupSettings', 'API should expose Instagram warmup save')
assertContains(api, "invoke<SaveResult>('save_instagram_warmup_settings'", 'API should call Tauri save command')

assertContains(taskPage, "currentPlatform === 'instagram'", 'task page should branch on Instagram platform')
assertContains(taskPage, 'InstagramWarmupForm', 'task page should render Instagram form')
assertContains(taskPage, 'saveInstagramWarmupSettings(', 'task page should persist Instagram settings')
assertContains(taskPage, 'normalizeInstagramWarmupSettings', 'task page should normalize Instagram values')
assertContains(taskPage, '启动 Instagram 养号', 'task page should expose Instagram warmup start copy')
assertContains(taskPage, "taskType: isInstagram ? 'warmup' : 'fyp'", 'task page should submit warmup task type for Instagram')
assertContains(taskPage, 'instagramWarmup', 'task page should load Instagram warmup snapshot')
assertNotContains(taskPage, 'account-matrix-ins', 'desktop task page should not embed the standalone ins UI')

assertContains(platformPage, "['tiktok', 'instagram']", 'platform page should expand Instagram details by default')
assertContains(platformPage, 'Instagram 养号已接入桌面端', 'platform page should describe native Instagram support')

assertContains(mainRs, 'save_instagram_warmup_settings', 'Tauri command should be registered')
assertContains(configRs, 'pub fn save_instagram_warmup_settings', 'Tauri config command should save Instagram warmup')
assertContains(configRs, 'platforms.instagram.warmup', 'Tauri config validation should know Instagram warmup schema')
assertContains(configRs, 'default_instagram_warmup_mapping', 'migration should fill missing Instagram warmup defaults')
assertContains(configRs, 'migrate_instagram_runtime_schema', 'migration should initialize Instagram runtime tables')
assertContains(configRs, 'instagram_warmup_payload_to_yaml_mapping', 'config save path should serialize Instagram warmup')
assertContains(processRs, 'platform == "instagram" && capability == "warmupTask"', 'backend should allow Instagram warmup execution')
assertContains(processRs, 'runtime_task_type("instagram_fyp")', 'Rust test should cover Instagram task type mapping')

assertContains(filesRs, 'matches!(platform, "tiktok" | "instagram")', 'Instagram should reuse shared comment pool defaults')
assertContains(bridgePy, 'platform_root(config, "instagram")', 'Python bridge should read Instagram platform config')
assertContains(bridgePy, 'comments.txt', 'Python bridge should reuse the shared comments file')
assertContains(runnerPy, 'platform = "instagram"', 'Python runner should declare Instagram platform')
assertContains(runnerPy, 'requires the BitBrowser provider', 'Python runner should reject unsupported browser providers')
assertContains(runnerPy, 'task_type": "instagram_warmup"', 'Python runner summary should identify Instagram warmup')

console.log('Instagram warmup frontend/source integration checks passed')
