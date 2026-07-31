import { invoke } from '@tauri-apps/api/core'

import type {
  AccountSummary,
  ApiStatus,
  AppInitializationStatus,
  AccountsPayload,
  ActionLog,
  ActionLogFilter,
  BackupResult,
  BatchCreateProfileRequest,
  BatchCreateProfileResult,
  AccountBrowserDiagnosis,
  BrowserProviderCapability,
  BrowserPreviewFrame,
  BuiltinChromiumCleanupResult,
  BuiltinChromiumStatus,
  ConfigPayload,
  ConfigSnapshot,
  CommentPoolsSnapshot,
  ClearLogResult,
  ClearRunLockResult,
  CdpResolveRequest,
  CreateProfileRequest,
  CreateProfileResult,
  FypSettings,
  FypStatsSummary,
  GmailSetupRequest,
  HomeSummary,
  LogChunk,
  LoginCredentialStatus,
  LoginPasswordPayload,
  BrowserProfile,
  ProcessLogChunk,
  ProcessStartResult,
  ProcessStatus,
  ProfileOperationResult,
  ProfileStatus,
  ProxyCheckRequest,
  ProxyCheckResult,
  ProjectPaths,
  RuntimeDiagnostics,
  ResetTargetWatermarkRequest,
  ResetTargetWatermarkResult,
  SaveResult,
  SaveCommentPoolsRequest,
  SaveCommentPoolsResult,
  SchedulerHealth,
  SchedulerProcessStatus,
  SchedulerSettingsPayload,
  SchedulerStartResult,
  SqliteStatus,
  SystemSettingsPayload,
  SystemSettingsSnapshot,
  StopResult,
  SupportBundleResult,
  SyncAccountsRequest,
  SyncApplyResult,
  SyncPreview,
  TargetEngagementRecord,
  TargetEngagementSettings,
  TargetFollowRecord,
  TargetRecordFilter,
  StatsScopeRequest,
  TargetStatsSummary,
  TargetWatermark,
  ValidationResult,
  PythonRunRequest,
  NotifySettings,
  NotifyTestResult,
  Platform,
  PlatformTaskRequest,
  MigrationApplyResult,
  MigrationPreview,
} from './types'

export const PROCESS_STARTED_EVENT = 'account-matrix:process-started'

function notifyProcessStarted(result: ProcessStartResult) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent<ProcessStartResult>(PROCESS_STARTED_EVENT, { detail: result }))
  }
  return result
}

export function getProjectPaths() {
  return invoke<ProjectPaths>('get_project_paths')
}

export function loadAccounts(platform: Platform | 'all' = 'all') {
  return invoke<AccountSummary[]>('load_accounts', { platform })
}

export function loadConfig() {
  return invoke<ConfigSnapshot>('load_config')
}

export function validateConfig(payload: ConfigPayload) {
  return invoke<ValidationResult>('validate_config', { payload })
}

export function backupConfig() {
  return invoke<BackupResult>('backup_config')
}

export function previewConfigMigration() {
  return invoke<MigrationPreview>('preview_config_migration')
}

export function applyConfigMigration() {
  return invoke<MigrationApplyResult>('apply_config_migration')
}

export function saveConfig(payload: ConfigPayload) {
  return invoke<SaveResult>('save_config', { payload })
}

export function saveAccounts(payload: AccountsPayload) {
  return invoke<SaveResult>('save_accounts', { payload })
}

export function getLoginCredentialStatus(accountId: string) {
  return invoke<LoginCredentialStatus>('get_login_credential_status', { accountId })
}

export function saveLoginPassword(payload: LoginPasswordPayload) {
  return invoke<LoginCredentialStatus>('save_login_password', { payload })
}

export function deleteLoginPassword(accountId: string) {
  return invoke<LoginCredentialStatus>('delete_login_password', { accountId })
}

export function saveFypSettings(payload: FypSettings, platform: Platform = 'tiktok') {
  return invoke<SaveResult>('save_fyp_settings', { payload: { ...payload, platform } })
}

export function saveTargetEngagementSettings(payload: TargetEngagementSettings, platform: Platform = 'tiktok') {
  return invoke<SaveResult>('save_target_engagement_settings', { payload: { ...payload, platform } })
}

export function saveSchedulerSettings(payload: SchedulerSettingsPayload) {
  return invoke<SaveResult>('save_scheduler_settings', { payload })
}

export function loadSystemSettings() {
  return invoke<SystemSettingsSnapshot>('load_system_settings')
}

export function getInitializationStatus() {
  return invoke<AppInitializationStatus | null>('get_initialization_status')
}

export function saveSystemSettings(payload: SystemSettingsPayload) {
  return invoke<SystemSettingsSnapshot>('save_system_settings', { payload })
}

export function saveNotifySettings(payload: NotifySettings) {
  return invoke<SaveResult>('save_notify_settings', { payload })
}

export function testNotification(payload: NotifySettings) {
  return invoke<NotifyTestResult>('test_notification', { payload })
}

export function getRuntimeDiagnostics() {
  return invoke<RuntimeDiagnostics>('get_runtime_diagnostics')
}

export function exportSupportBundle() {
  return invoke<SupportBundleResult>('export_support_bundle')
}

export function queryAccountLogs(accountId: string, limit = 80) {
  return invoke<ActionLog[]>('query_account_logs', { accountId, limit })
}

export function queryActionLogs(filter: ActionLogFilter) {
  return invoke<ActionLog[]>('query_action_logs', { filter })
}

export function queryTargetEngagements(filter: TargetRecordFilter) {
  return invoke<TargetEngagementRecord[]>('query_target_engagements', { filter })
}

export function queryTargetFollows(filter: TargetRecordFilter) {
  return invoke<TargetFollowRecord[]>('query_target_follows', { filter })
}

export function queryTargetWatermarks(filter: TargetRecordFilter = {}) {
  return invoke<TargetWatermark[]>('query_target_watermarks', { filter })
}

export function queryFypStats(filter: StatsScopeRequest = { scope: 'all' }) {
  return invoke<FypStatsSummary>('query_fyp_stats', { filter })
}

export function queryTargetStats(filter: StatsScopeRequest = { scope: 'all' }) {
  return invoke<TargetStatsSummary>('query_target_stats', { filter })
}

export function resetTargetWatermark(request: ResetTargetWatermarkRequest) {
  return invoke<ResetTargetWatermarkResult>('reset_target_watermark', { request })
}

export function loadCommentPools(platform: Platform = 'tiktok') {
  return invoke<CommentPoolsSnapshot>('load_comment_pools', { platform })
}

export function saveCommentPools(request: SaveCommentPoolsRequest) {
  return invoke<SaveCommentPoolsResult>('save_comment_pools', { request })
}

export function checkBitbrowserApi() {
  return invoke<ApiStatus>('check_bitbrowser_api')
}

export function getBrowserProviderMatrix() {
  return invoke<BrowserProviderCapability[]>('get_browser_provider_matrix')
}

export function diagnoseAccountBrowser(accountId: string) {
  return invoke<AccountBrowserDiagnosis>('diagnose_account_browser', { accountId })
}

export function getBuiltinChromiumStatus() {
  return invoke<BuiltinChromiumStatus>('get_builtin_chromium_status')
}

export function cleanupBuiltinChromiumData(accountId: string) {
  return invoke<BuiltinChromiumCleanupResult>('cleanup_builtin_chromium_data', { accountId })
}

export function listBrowserProfiles() {
  return invoke<BrowserProfile[]>('list_browser_profiles')
}

export function getProfileStatus(profileId: string) {
  return invoke<ProfileStatus>('get_profile_status', { profileId })
}

export function openProfile(profileId: string) {
  return invoke<ProfileOperationResult>('open_profile', { profileId })
}

export function closeProfile(profileId: string) {
  return invoke<ProfileOperationResult>('close_profile', { profileId })
}

export function resolveCdpPageWs(request: CdpResolveRequest) {
  return invoke<string>('resolve_cdp_page_ws', { request })
}

export function captureBrowserPreview(request: CdpResolveRequest) {
  return invoke<BrowserPreviewFrame>('capture_browser_preview', { request })
}

export function checkProxy(request: ProxyCheckRequest) {
  return invoke<ProxyCheckResult>('check_proxy', { request })
}

export function createSingleBrowserProfile(request: CreateProfileRequest) {
  return invoke<CreateProfileResult>('create_single_browser_profile', { request })
}

export function createBatchBrowserProfiles(request: BatchCreateProfileRequest) {
  return invoke<BatchCreateProfileResult>('create_batch_browser_profiles', { request })
}

export function syncAccountsDryRun(request: SyncAccountsRequest) {
  return invoke<SyncPreview>('sync_accounts_dry_run', { request })
}

export function syncAccountsApply(request: SyncAccountsRequest) {
  return invoke<SyncApplyResult>('sync_accounts_apply', { request })
}

export function getCurrentRunStatus() {
  return invoke<ProcessStatus>('get_current_run_status')
}

export function runPythonScript(request: PythonRunRequest) {
  return invoke<ProcessStartResult>('run_python_script', { request }).then(notifyProcessStarted)
}

export function runGmailSetup(request: GmailSetupRequest) {
  return invoke<ProcessStartResult>('run_gmail_setup', { request }).then(notifyProcessStarted)
}

export function getStdoutChunk(offset: number) {
  return invoke<ProcessLogChunk>('get_stdout_chunk', { request: { offset } })
}

export function getStderrChunk(offset: number) {
  return invoke<ProcessLogChunk>('get_stderr_chunk', { request: { offset } })
}

export function stopCurrentRun(force: boolean) {
  return invoke<StopResult>('stop_current_run', { force })
}

export function continueAuthIntervention() {
  return invoke<StopResult>('continue_auth_intervention')
}

export function skipAuthIntervention() {
  return invoke<StopResult>('skip_auth_intervention')
}

export function tailSessionLog(offset: number) {
  return invoke<LogChunk>('tail_session_log', { request: { offset } })
}

export function clearSessionLog() {
  return invoke<ClearLogResult>('clear_session_log')
}

export function getHomeSummary() {
  return invoke<HomeSummary>('get_home_summary')
}

export function getSqliteStatus() {
  return invoke<SqliteStatus>('get_sqlite_status')
}

export function runAccountScript(accountId: string) {
  return invoke<ProcessStartResult>('run_account_script', { accountId }).then(notifyProcessStarted)
}

export function runOneAccount(accountId: string) {
  return invoke<ProcessStartResult>('run_one_account', { accountId }).then(notifyProcessStarted)
}

export function runAllAccounts() {
  return invoke<ProcessStartResult>('run_all_accounts').then(notifyProcessStarted)
}

export function runSelectedAccounts(accountIds: string[]) {
  return invoke<ProcessStartResult>('run_selected_accounts', { accountIds }).then(notifyProcessStarted)
}

export function runPlatformTask(request: PlatformTaskRequest) {
  return invoke<ProcessStartResult>('run_platform_task', { request }).then(notifyProcessStarted)
}

export function runTikTokRegister(accountId: string) {
  return invoke<ProcessStartResult>('run_tiktok_register', { accountId }).then(notifyProcessStarted)
}

export function runTikTokRegisterBatch(accountIds: string[]) {
  return invoke<ProcessStartResult>('run_tiktok_register_batch', { accountIds }).then(notifyProcessStarted)
}

export function startScheduler() {
  return invoke<SchedulerStartResult>('start_scheduler')
}

export function stopScheduler() {
  return invoke<StopResult>('stop_scheduler')
}

export function getSchedulerProcessStatus() {
  return invoke<SchedulerProcessStatus>('get_scheduler_process_status')
}

export function getSchedulerHealth() {
  return invoke<SchedulerHealth>('get_scheduler_health')
}

export function clearRunLock() {
  return invoke<ClearRunLockResult>('clear_run_lock')
}

export function exportLogFile(filename: string, content: string) {
  return invoke<{ cancelled: boolean; path?: string | null }>('export_log_file', {
    request: { filename, content },
  })
}
