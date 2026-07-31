import type { CapabilityStatus, Platform, PlatformStatus } from '../platforms/types'

export type { Platform } from '../platforms/types'
export type PlatformId = Platform
export type PlatformSupportStatus = PlatformStatus
export type PlatformCapabilityStatus = CapabilityStatus

export type RunStatus =
  | 'idle'
  | 'starting'
  | 'running'
  | 'pause_pending'
  | 'intervention_required'
  | 'completed'
  | 'partial_failed'
  | 'failed'
  | 'stopped'

export type AccountLastStatus = 'ok' | 'error' | 'skip' | 'unknown'

export interface ProjectPaths {
  runtimeMode: 'bundled' | 'source'
  projectRoot: string
  configPath: string
  commentsPath: string
  brandCommentsPath: string
  dataDir: string
  logsDir: string
  actionsDbPath: string
  sessionsLogPath: string
  lockFilePath: string
  srcDir: string
  settingsPath: string
  runtimePath: string
  runtimeManifestPath: string
  runtimeVersion?: string
  pythonExecutable: string
  defaultBrowserProvider: BrowserProviderId
  chromiumExecutable: string
  bitbrowserApiUrl: string
  autoCloseProfile: boolean
  logPollIntervalSeconds: number
}

export interface Account {
  id: string
  platform: Platform
  enabled: boolean
  scheduled: boolean
  ipGroup?: number
  activeHours: [number, number][]
  browserProvider: BrowserProviderId
  browser?: AccountBrowserConfig
  login?: AccountLoginConfig
  bitbrowserProfileId?: string
  notes?: string
  profileOpen?: boolean
  loginCheck?: AccountLoginCheck
  lastRunAt?: string
  lastStatus?: AccountLastStatus
}

export type BrowserProviderId = 'bitbrowser' | 'builtin_chromium'

export interface AccountBrowserConfig {
  provider?: BrowserProviderId
  profileId?: string
  proxyType?: 'http' | 'https' | 'socks5'
  proxy?: string
  userDataDir?: string
}

export interface AccountLoginConfig {
  enabled: boolean
  method: 'password'
  username?: string
  credentialRef?: string
}

export interface AccountLoginCheck {
  status: 'ok' | 'logged_in' | 'logged_out' | 'login_page' | 'mfa' | 'captcha' | 'security_check' | 'unknown' | string
  detail: string
  ts: string
}

export interface LoginPasswordPayload {
  accountId: string
  password: string
}

export interface LoginCredentialStatus {
  accountId: string
  credentialRef?: string
  saved: boolean
  readable: boolean
  error?: string
}

export type AccountSummary = Account

export interface BrowserProfile {
  id: string
  name: string
  platform?: Platform
  proxy?: string
  groupId?: string
  opened: boolean
  boundAccountId?: string
}

export interface ProfileStatus {
  profileId: string
  opened: boolean
  pid?: string
  error?: string
}

export interface ProfileOperationResult {
  profileId: string
  opened: boolean
  cdpEndpoint?: string
  message: string
}

export interface ProxyCheckRequest {
  proxyType: 'http' | 'https' | 'socks5'
  proxy: string
  checkExists?: boolean
}

export interface ParsedProxy {
  host: string
  port: number
  username: string
  masked: string
}

export interface ProxyCheckResult {
  valid: boolean
  used: boolean
  message: string
  proxy?: ParsedProxy
}

export interface CreateProfileRequest {
  name: string
  proxyType: 'http' | 'https' | 'socks5'
  proxy: string
  groupId?: string
  skipProxyCheck?: boolean
  allowUsedProxy?: boolean
}

export interface CreateProfileResult {
  name: string
  profileId: string
  proxy: string
}

export interface BatchCreateProfileRequest {
  prefix: string
  proxyType: 'http' | 'https' | 'socks5'
  proxiesText: string
  groupId?: string
  skipProxyCheck?: boolean
  skipUsed?: boolean
}

export interface BatchCreatedProfile {
  lineNumber: number
  name: string
  profileId: string
  proxy: string
}

export interface BatchProfileIssue {
  lineNumber: number
  name?: string
  proxy: string
  reason: string
}

export interface BatchCreateProfileResult {
  created: BatchCreatedProfile[]
  skipped: BatchProfileIssue[]
  failed: BatchProfileIssue[]
}

export interface SyncAccountsRequest {
  prefix: string
  start: number
  end: number
  morningStart: number
  morningEnd: number
  eveningStart: number
  eveningEnd: number
  firstIpGroup: number
}

export interface SyncPreview {
  accountsToAdd: Account[]
  existingAccounts: string[]
  missingProfiles: string[]
  duplicateProfiles: string[]
  canApply: boolean
}

export interface SyncApplyResult {
  preview: SyncPreview
  saveResult: SaveResult
}

export interface FypSettings {
  fypBrowseMinutes: [number, number]
  likeProbability: number
  followsPerSession: [number, number]
  comment: {
    enabled: boolean
    commentsPerSession: [number, number]
    minVideoComments: number
    probability: number
  }
}

export interface TargetEngagementSettings {
  enabled: boolean
  handles: string[]
  participants: string[]
  firstRunLatestN: number
  maxVideosPerRun: number
  likeProbability: number
  commentProbability: number
  commentsFile: string
  follow: boolean
  followProbability: number
}

export interface TargetWatermark {
  platform: Platform
  ourAccount: string
  handle: string
  maxVideoId?: string
  latestTs?: string
  videos: number
  likes: number
  comments: number
}

export interface TargetAccountStats {
  platform: Platform
  accountId: string
  videos: number
  likes: number
  comments: number
  follows: number
  handles: string[]
}

export interface TargetHandleStats {
  handle: string
  videos: number
  likes: number
  comments: number
  follows: number
  accounts: string[]
}

export interface TargetStatsSummary {
  scope: string
  label: string
  byAccount: TargetAccountStats[]
  byHandle: TargetHandleStats[]
}

export type StatsScope = 'all' | 'today' | 'recent_days' | 'custom'

export interface StatsScopeRequest {
  scope?: StatsScope
  platform?: Platform | 'all'
  accountId?: string
  days?: number
  startTs?: string
  endTs?: string
}

export interface FypAccountStats {
  platform: Platform
  accountId: string
  ok: number
  err: number
  skip: number
  videos: number
  likes: number
  follows: number
  comments: number
}

export interface FypStatsTotal {
  accounts: number
  ok: number
  err: number
  skip: number
  videos: number
  likes: number
  follows: number
  comments: number
}

export interface FypStatsSummary {
  scope: string
  label: string
  byAccount: FypAccountStats[]
  total: FypStatsTotal
}

export interface ResetTargetWatermarkRequest {
  accountId?: string
  handle?: string
}

export interface ResetTargetWatermarkResult {
  deletedRows: number
}

export interface SchedulerJob {
  id: string
  accountId?: string
  nextRun?: string
  status?: string
}

export interface RunLockStatus {
  path: string
  exists: boolean
  pid?: number
  active: boolean
}

export interface IpGroupConflict {
  ipGroup: number
  leftAccountId: string
  rightAccountId: string
  leftActiveHours: [number, number][]
  rightActiveHours: [number, number][]
}

export interface SchedulerHealth {
  status: 'stopped' | 'starting' | 'running' | 'error'
  processId?: number
  jobs: SchedulerJob[]
  nextRun?: string
  nextAccountId?: string
  lockHeldExternally?: boolean
  todayScheduleCount: number
  firesPerDay: number
  runLock: RunLockStatus
  ipGroupConflicts: IpGroupConflict[]
  error?: string
}

export interface SchedulerProcessStatus {
  status: 'stopped' | 'starting' | 'running' | 'error'
  processId?: number
  command: string[]
  healthUrl: string
  error?: string
}

export interface ApiStatus {
  available: boolean
  apiUrl: string
  checkedAt: string
  error?: string
}

export interface BrowserProviderCapability {
  provider: BrowserProviderId
  label: string
  implemented: boolean
  productionReady: boolean
  canLaunch: boolean
  canClose: boolean
  providesCdpEndpoint: boolean
  requiresProfileId: boolean
  supportsTiktok: boolean
  riskLevel: 'stable' | 'production_optional' | 'advanced'
  notes: string
}

export interface ProviderDiagnosticCheck {
  name: string
  status: 'ok' | 'warning' | 'error'
  detail: string
}

export interface AccountBrowserDiagnosis {
  accountId: string
  provider: BrowserProviderId
  status: 'ok' | 'warning' | 'error'
  checks: ProviderDiagnosticCheck[]
}

export interface BuiltinChromiumStatus {
  available: boolean
  executablePath?: string
  dataRoot: string
  checkedAt: string
  error?: string
}

export interface BuiltinChromiumCleanupResult {
  accountId: string
  userDataDir: string
  removed: boolean
  message: string
}

export interface DiagnosticCheck {
  name: string
  status: 'ok' | 'warning' | 'error'
  detail: string
}

export interface RuntimeDiagnostics {
  status: 'ok' | 'warning' | 'error'
  checkedAt: string
  runtimeMode: 'bundled' | 'source'
  runtimeVersion?: string
  runtimeManifest?: unknown
  runtimeDiagnostic?: unknown
  paths: ProjectPaths
  checks: DiagnosticCheck[]
}

export interface SupportBundleResult {
  path: string
  diagnostics: RuntimeDiagnostics
}

export interface ProcessStatus {
  status: RunStatus
  processId?: number
  taskType?: string
  accountId?: string
  startedAt?: string
  endedAt?: string
  error?: string
  command: string[]
  queuedAccounts: string[]
  completedAccounts: string[]
  browserPreview?: BrowserPreview
  authIntervention?: AuthIntervention
  stdoutLength: number
  stderrLength: number
}

export interface AuthIntervention {
  accountId: string
  platform: Platform
  state: 'mfa' | 'captcha' | 'security_check' | 'unknown' | 'login_page' | 'logged_out'
  detail: string
  reason: string
  url?: string
  checkedAt: string
}

export interface BrowserPreview {
  accountId: string
  profileId: string
  cdpEndpoint: string
  openedAt: string
}

export interface CdpResolveRequest {
  cdpEndpoint: string
}

export interface BrowserPreviewFrame {
  dataUrl: string
}

export interface LogChunk {
  offset: number
  nextOffset: number
  content: string
  exists: boolean
}

export interface CommentPool {
  kind: 'general' | 'brand'
  path: string
  rawText: string
  comments: string[]
  commentLines: number
  blankLines: number
  duplicates: string[]
}

export interface CommentPoolsSnapshot {
  platform: Platform
  general: CommentPool
  brand: CommentPool
}

export interface SaveCommentPoolsRequest {
  platform?: Platform
  generalText: string
  brandText: string
}

export interface SaveCommentPoolsResult {
  general: CommentPool
  brand: CommentPool
  backupPaths: string[]
  warnings: string[]
}

export interface HomeSummary {
  tiktokEnabledAccounts: number
  bitbrowser: ApiStatus
  todayPlannedTasks: number
  todayCompletedAccounts: number
  todayFailedAccounts: number
  todayTargetInteractions: number
}

export interface TaskRun {
  id: string
  taskType: 'fyp' | 'target_engagement' | 'tiktok_register' | 'scheduler' | 'gmail' | 'diagnostic'
  status: RunStatus
  accountIds: string[]
  startedAt?: string
  endedAt?: string
  stdoutOffset?: number
  stderrOffset?: number
  error?: string
}

export interface AccountRun {
  accountId: string
  status: AccountLastStatus
  startedAt?: string
  endedAt?: string
  videos?: number
  likes?: number
  follows?: number
  comments?: number
  error?: string
}

export interface ActionLog {
  id: number
  platform: Platform
  accountId: string
  action: string
  status: string
  detail: string
  ts: string
}

export interface ActionLogFilter {
  platform?: Platform | 'all'
  accountId?: string
  action?: string
  status?: string
  startTs?: string
  endTs?: string
  limit?: number
}

export interface TargetRecordFilter {
  platform?: Platform | 'all'
  accountId?: string
  handle?: string
  startTs?: string
  endTs?: string
  limit?: number
}

export interface TargetEngagementRecord {
  platform: Platform
  ourAccount: string
  handle: string
  videoId: string
  liked: boolean
  commented: boolean
  ts: string
}

export interface TargetFollowRecord {
  platform: Platform
  ourAccount: string
  handle: string
  followed: boolean
  ts: string
}

export interface StatsSummary {
  scope: 'all' | 'today' | 'recent_days' | 'custom'
  accounts: number
  sessions: number
  ok: number
  failed: number
  skipped: number
  videos: number
  likes: number
  follows: number
  comments: number
  targetVideos: number
  targetLikes: number
  targetComments: number
  targetFollows: number
}

export interface GmailSetupRequest {
  browserName?: string
  email?: string
  password?: string
  newPassword?: string
  query?: string
  emailFile?: string
  timeoutSeconds: number
  termsTimeoutSeconds: number
  keepOpenOnError: boolean
}

export interface DiagnosticRequest {
  accountId: string
  kind: 'like' | 'comment'
  minComments?: number
  maxScroll?: number
  noPost?: boolean
}

export interface NotifySettings {
  enabled: boolean
  type: 'serverchan' | 'bark' | 'webhook'
  serverchan?: {
    sendkey?: string
  }
  bark?: {
    url?: string
  }
  webhook?: {
    url?: string
  }
}

export interface SystemSettingsPayload {
  runtimeMode?: 'bundled' | 'source'
  projectRoot: string
  pythonExecutable: string
  defaultBrowserProvider: BrowserProviderId
  chromiumExecutable: string
  bitbrowserApiUrl: string
  dataDir: string
  configPath: string
  commentsPath: string
  brandCommentsPath: string
  runtimePath?: string
  runtimeManifestPath?: string
  autoCloseProfile: boolean
  logPollIntervalSeconds: number
}

export type SystemSettingsSnapshot = SystemSettingsPayload & {
  settingsPath: string
  logsDir: string
  runtimePath: string
  runtimeManifestPath: string
  runtimeVersion?: string
  initializedAppVersion?: string
}

export interface AppInitializationStatus {
  initializedAppVersion: string
  settingsDir: string
  configDir: string
  backupsDir: string
  dataDir: string
  logsDir: string
  settingsPath: string
  settingsCreated: boolean
  templatesCopied: string[]
  runtimeMode: 'bundled' | 'source'
}

export interface NotifyTestResult {
  notifyType: NotifySettings['type']
  message: string
}

export interface SqliteStatus {
  path: string
  exists: boolean
  actionLog: boolean
  targetEngagements: boolean
  targetFollows: boolean
}

export interface SchedulerSettings {
  firesPerDay: number
}

export interface SchedulerAccountSettings {
  id: string
  scheduled: boolean
  ipGroup?: number
  activeHours: [number, number][]
}

export interface SchedulerSettingsPayload {
  firesPerDay: number
  accounts: SchedulerAccountSettings[]
}

export interface ConfigSnapshot {
  paths: ProjectPaths
  rawYaml: string
  accounts: Account[]
  fypSettings?: FypSettings
  targetEngagement?: TargetEngagementSettings
  schedulerSettings?: SchedulerSettings
  notify?: NotifySettings
  validation: ValidationResult
}

export interface ConfigPayload {
  rawYaml: string
}

export interface AccountsPayload {
  platform?: Platform | 'all'
  accounts: Account[]
}

export interface PlatformTaskRequest {
  platform: Platform
  taskType: TaskRun['taskType'] | 'target'
  accountIds: string[]
  mode?: 'all' | 'single' | 'selected'
}

export interface ValidationIssue {
  path: string
  message: string
}

export interface ValidationResult {
  valid: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
}

export interface BackupResult {
  backupPath: string
}

export interface SaveResult {
  savedPath: string
  backupPath: string
  validation: ValidationResult
}

export interface MigrationOperation {
  key: string
  label: string
  detail: string
  pending: boolean
}

export interface MigrationPreview {
  required: boolean
  operations: MigrationOperation[]
  warnings: string[]
}

export interface MigrationApplyResult {
  preview: MigrationPreview
  backupPaths: string[]
  savedPath: string
  validation: ValidationResult
}

export interface ScriptRunResult {
  accountId: string
  command: string[]
  exitCode: number | null
  stdout: string
  stderr: string
}

export interface ProcessStartResult {
  processId?: number
  command: string[]
  status: RunStatus
  taskType: string
  accountId?: string
}

export interface ProcessLogChunk {
  offset: number
  nextOffset: number
  content: string
}

export interface StopResult {
  status: RunStatus
  processId?: number
  message: string
}

export interface ClearRunLockResult {
  path: string
  cleared: boolean
  message: string
}

export interface ClearLogResult {
  path: string
  cleared: boolean
}

export interface PythonRunRequest {
  scriptName: string
  args: string[]
  mode?: string
}

export interface SchedulerStartResult {
  processId: number
  command: string[]
  status: RunStatus | 'running'
}
