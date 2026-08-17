use chrono::Local;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value as JsonValue};
use serde_yaml::{Mapping, Value};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Write;
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use crate::paths::{normalize, project_paths, ProjectPaths};
use crate::security::{redact_line, redact_text};

const CONFIG_SCHEMA_VERSION: i64 = 1;
const DEFAULT_BROWSER_PROVIDER: &str = "bitbrowser";
const DEFAULT_LOGIN_METHOD: &str = "password";
const LOGIN_CREDENTIAL_PREFIX: &str = "account-login/";
const AI_COMMENT_CREDENTIAL_PREFIX: &str = "ai-comment/";
const DEFAULT_AI_COMMENT_PROVIDER: &str = "kimi_moonshot";
const DEFAULT_AI_COMMENT_BASE_URL: &str = "https://api.moonshot.cn/v1";
const DEFAULT_AI_COMMENT_MODEL: &str = "kimi-k2.6";
const DEFAULT_AI_COMMENT_TIMEOUT_SECONDS: i64 = 5;
const DEFAULT_AI_COMMENT_MAX_LENGTH: i64 = 80;
const DEFAULT_AI_COMMENT_LANGUAGE: &str = "auto";
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[derive(Debug, Deserialize)]
struct ConfigYaml {
    schema_version: Option<i64>,
    defaults: Option<DefaultsYaml>,
    browser: Option<BrowserDefaultsYaml>,
    bitbrowser: Option<BitbrowserYaml>,
    scheduler: Option<SchedulerYaml>,
    target_accounts: Option<TargetAccountsYaml>,
    platforms: Option<HashMap<String, PlatformYaml>>,
    ai_comment: Option<AiCommentYaml>,
    notify: Option<NotifyYaml>,
    accounts: Option<Vec<AccountYaml>>,
}

#[derive(Debug, Deserialize)]
struct PlatformYaml {
    warmup: Option<DailyActionsYaml>,
    target_engagement: Option<TargetAccountsYaml>,
    comments: Option<PlatformCommentsYaml>,
    scheduler: Option<SchedulerYaml>,
}

#[derive(Debug, Deserialize)]
struct DefaultsYaml {
    daily_actions: Option<DailyActionsYaml>,
    active_hours: Option<Vec<[f64; 2]>>,
}

#[derive(Debug, Deserialize)]
struct DailyActionsYaml {
    fyp_browse_minutes: Option<[f64; 2]>,
    like_probability: Option<f64>,
    follows_per_session: Option<[i64; 2]>,
    comment: Option<CommentYaml>,
}

#[derive(Debug, Deserialize)]
struct CommentYaml {
    enabled: Option<bool>,
    comments_per_session: Option<[i64; 2]>,
    min_video_comments: Option<i64>,
    probability: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct BitbrowserYaml {
    api_url: Option<String>,
}

#[derive(Debug, Deserialize)]
struct BrowserDefaultsYaml {
    default_provider: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
struct AccountBrowserYaml {
    provider: Option<String>,
    profile_id: Option<String>,
    proxy_type: Option<String>,
    proxy: Option<String>,
    user_data_dir: Option<String>,
    bitbrowser: Option<AccountBrowserBitbrowserYaml>,
}

#[derive(Debug, Deserialize, Clone)]
struct AccountLoginYaml {
    enabled: Option<bool>,
    method: Option<String>,
    username: Option<String>,
    credential_ref: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
struct AccountBrowserBitbrowserYaml {
    profile_id: Option<String>,
}

#[derive(Debug, Deserialize)]
struct SchedulerYaml {
    fires_per_day: Option<i64>,
    active_hours: Option<Vec<[f64; 2]>>,
}

#[derive(Debug, Deserialize)]
struct PlatformCommentsYaml {
    general_file: Option<String>,
    target_file: Option<String>,
}

#[derive(Debug, Deserialize)]
struct AiCommentYaml {
    enabled: Option<bool>,
    provider: Option<String>,
    base_url: Option<String>,
    model: Option<String>,
    timeout_seconds: Option<i64>,
    max_comment_length: Option<i64>,
    fallback_to_pool: Option<bool>,
    language: Option<String>,
    blocked_words: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
struct TargetAccountsYaml {
    enabled: Option<bool>,
    handles: Option<Vec<String>>,
    participants: Option<Vec<String>>,
    first_run_latest_n: Option<i64>,
    max_videos_per_run: Option<i64>,
    like_probability: Option<f64>,
    comment_probability: Option<f64>,
    comments_file: Option<String>,
    follow: Option<bool>,
    follow_probability: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct NotifyYaml {
    enabled: Option<bool>,
    #[serde(rename = "type")]
    notify_type: Option<String>,
    serverchan: Option<ServerChanYaml>,
    bark: Option<UrlHolderYaml>,
    webhook: Option<UrlHolderYaml>,
}

#[derive(Debug, Deserialize)]
struct ServerChanYaml {
    sendkey: Option<String>,
}

#[derive(Debug, Deserialize)]
struct UrlHolderYaml {
    url: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
struct AccountYaml {
    id: String,
    platform: Option<String>,
    enabled: Option<bool>,
    scheduled: Option<bool>,
    ip_group: Option<i64>,
    active_hours: Option<Vec<[f64; 2]>>,
    browser_provider: Option<String>,
    browser: Option<AccountBrowserYaml>,
    login: Option<AccountLoginYaml>,
    bitbrowser_profile_id: Option<String>,
    notes: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConfigPayload {
    raw_yaml: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountsPayload {
    pub platform: Option<String>,
    pub accounts: Vec<AccountInput>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FypSettingsPayload {
    pub platform: Option<String>,
    pub fyp_browse_minutes: [f64; 2],
    pub like_probability: f64,
    pub follows_per_session: [i64; 2],
    pub comment: FypCommentPayload,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FypCommentPayload {
    pub enabled: bool,
    pub comments_per_session: [i64; 2],
    pub min_video_comments: i64,
    pub probability: f64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TargetEngagementPayload {
    pub platform: Option<String>,
    pub enabled: bool,
    pub handles: Vec<String>,
    pub participants: Vec<String>,
    pub first_run_latest_n: i64,
    pub max_videos_per_run: i64,
    pub like_probability: f64,
    pub comment_probability: f64,
    pub comments_file: String,
    pub follow: bool,
    pub follow_probability: f64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerSettingsPayload {
    pub fires_per_day: i64,
    pub accounts: Vec<SchedulerAccountSettingsPayload>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerAccountSettingsPayload {
    pub id: String,
    pub scheduled: bool,
    pub ip_group: Option<i64>,
    pub active_hours: Vec<[f64; 2]>,
}

#[derive(Debug, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct NotifySettingsPayload {
    pub enabled: bool,
    #[serde(rename = "type")]
    pub notify_type: String,
    pub serverchan: Option<NotifySecretPayload>,
    pub bark: Option<NotifyUrlPayload>,
    pub webhook: Option<NotifyUrlPayload>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct NotifySecretPayload {
    pub sendkey: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct NotifyUrlPayload {
    pub url: Option<String>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AccountInput {
    pub id: String,
    pub platform: String,
    pub enabled: bool,
    pub scheduled: Option<bool>,
    pub ip_group: Option<i64>,
    pub active_hours: Vec<[f64; 2]>,
    pub browser_provider: Option<String>,
    pub browser: Option<AccountBrowserInput>,
    pub login: Option<AccountLoginInput>,
    pub bitbrowser_profile_id: Option<String>,
    pub notes: Option<String>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AccountBrowserInput {
    pub provider: Option<String>,
    pub profile_id: Option<String>,
    pub proxy_type: Option<String>,
    pub proxy: Option<String>,
    pub user_data_dir: Option<String>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AccountLoginInput {
    pub enabled: bool,
    pub method: Option<String>,
    pub username: Option<String>,
    pub credential_ref: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LoginPasswordPayload {
    pub account_id: String,
    pub password: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AiCommentSettingsPayload {
    pub enabled: bool,
    pub provider: String,
    pub base_url: String,
    pub model: String,
    pub timeout_seconds: i64,
    pub max_comment_length: i64,
    pub fallback_to_pool: Option<bool>,
    pub language: String,
    pub blocked_words: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AiCommentApiKeyPayload {
    pub provider: Option<String>,
    pub api_key: String,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct LoginCredentialStatus {
    account_id: String,
    credential_ref: Option<String>,
    saved: bool,
    readable: bool,
    error: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AiCommentSettings {
    enabled: bool,
    provider: String,
    base_url: String,
    model: String,
    timeout_seconds: i64,
    max_comment_length: i64,
    fallback_to_pool: bool,
    language: String,
    blocked_words: Vec<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AiCommentApiKeyStatus {
    provider: String,
    credential_ref: String,
    saved: bool,
    readable: bool,
    error: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AiCommentTestPayload {
    pub settings: AiCommentSettingsPayload,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AiCommentPreviewPayload {
    pub settings: AiCommentSettingsPayload,
    pub title: String,
    pub description: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AiCommentGenerationResult {
    ok: bool,
    comment: String,
    source: String,
    reason: String,
    #[serde(rename = "latencyMs", alias = "latency_ms")]
    latency_ms: i64,
    error: Option<String>,
    provider: String,
    model: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConfigSnapshot {
    paths: ProjectPaths,
    raw_yaml: String,
    config: Value,
    accounts: Vec<Account>,
    fyp_settings: Option<FypSettings>,
    target_engagement: Option<TargetEngagementSettings>,
    scheduler_settings: SchedulerSettings,
    ai_comment: AiCommentSettings,
    notify: Option<NotifySettings>,
    validation: ValidationResult,
}

impl ConfigSnapshot {
    pub fn bitbrowser_api_url(&self) -> Option<String> {
        self.config
            .get("bitbrowser")
            .and_then(|bitbrowser| bitbrowser.get("api_url"))
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToString::to_string)
    }

    pub fn chromium_executable(&self) -> Option<String> {
        self.config
            .get("browser")
            .and_then(|browser| {
                browser
                    .get("chromium_executable")
                    .or_else(|| browser.get("chromium_executable_path"))
                    .or_else(|| {
                        browser.get("builtin_chromium").and_then(|builtin| {
                            builtin
                                .get("executable_path")
                                .or_else(|| builtin.get("chromium_executable"))
                        })
                    })
            })
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToString::to_string)
            .or_else(|| {
                self.config
                    .get("builtin_chromium")
                    .and_then(|builtin| {
                        builtin
                            .get("executable_path")
                            .or_else(|| builtin.get("chromium_executable"))
                    })
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
                    .map(ToString::to_string)
            })
    }

    pub fn accounts(&self) -> &[Account] {
        &self.accounts
    }

    pub fn ai_comment_enabled(&self) -> bool {
        self.ai_comment.enabled
    }

    pub fn ai_comment_provider(&self) -> &str {
        &self.ai_comment.provider
    }

    pub fn scheduler_fires_per_day(&self) -> Option<i64> {
        platform_section(&self.config, "tiktok", "scheduler")
            .and_then(|scheduler| scheduler.get("fires_per_day"))
            .and_then(Value::as_i64)
            .or_else(|| {
                self.config
                    .get("scheduler")
                    .and_then(|scheduler| scheduler.get("fires_per_day"))
                    .and_then(Value::as_i64)
            })
    }
}

impl Account {
    pub fn id(&self) -> &str {
        &self.id
    }

    pub fn platform(&self) -> &str {
        &self.platform
    }

    pub fn enabled(&self) -> bool {
        self.enabled
    }

    pub fn scheduled(&self) -> bool {
        self.scheduled
    }

    pub fn bitbrowser_profile_id(&self) -> Option<&str> {
        self.bitbrowser_profile_id.as_deref()
    }

    pub fn browser_user_data_dir(&self) -> Option<&str> {
        self.browser
            .as_ref()
            .and_then(|browser| browser.user_data_dir.as_deref())
    }

    pub fn browser_proxy_type(&self) -> Option<&str> {
        self.browser
            .as_ref()
            .and_then(|browser| browser.proxy_type.as_deref())
    }

    pub fn browser_proxy(&self) -> Option<&str> {
        self.browser
            .as_ref()
            .and_then(|browser| browser.proxy.as_deref())
    }

    pub fn browser_provider(&self) -> &str {
        &self.browser_provider
    }

    pub fn login_enabled(&self) -> bool {
        self.login.enabled
    }

    pub fn login_username(&self) -> Option<&str> {
        self.login.username.as_deref()
    }

    pub fn ip_group(&self) -> Option<i64> {
        self.ip_group
    }

    pub fn active_hours(&self) -> &[[f64; 2]] {
        &self.active_hours
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Account {
    id: String,
    platform: String,
    enabled: bool,
    scheduled: bool,
    ip_group: Option<i64>,
    active_hours: Vec<[f64; 2]>,
    browser_provider: String,
    browser: Option<AccountBrowser>,
    login: AccountLogin,
    bitbrowser_profile_id: Option<String>,
    notes: Option<String>,
    profile_open: Option<bool>,
    login_check: Option<AccountLoginCheck>,
    last_run_at: Option<String>,
    last_status: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountBrowser {
    provider: String,
    profile_id: Option<String>,
    proxy_type: Option<String>,
    proxy: Option<String>,
    user_data_dir: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountLogin {
    enabled: bool,
    method: String,
    username: Option<String>,
    credential_ref: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountLoginCheck {
    status: String,
    detail: String,
    ts: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FypSettings {
    fyp_browse_minutes: [f64; 2],
    like_probability: f64,
    follows_per_session: [i64; 2],
    comment: FypCommentSettings,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FypCommentSettings {
    enabled: bool,
    comments_per_session: [i64; 2],
    min_video_comments: i64,
    probability: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TargetEngagementSettings {
    enabled: bool,
    handles: Vec<String>,
    participants: Vec<String>,
    first_run_latest_n: i64,
    max_videos_per_run: i64,
    like_probability: f64,
    comment_probability: f64,
    comments_file: String,
    follow: bool,
    follow_probability: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerSettings {
    fires_per_day: i64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NotifySettings {
    enabled: bool,
    #[serde(rename = "type")]
    notify_type: String,
    serverchan: Option<ServerChanSettings>,
    bark: Option<UrlHolderSettings>,
    webhook: Option<UrlHolderSettings>,
}

#[derive(Debug, Serialize)]
pub struct ServerChanSettings {
    sendkey: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct UrlHolderSettings {
    url: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ValidationResult {
    valid: bool,
    errors: Vec<ValidationIssue>,
    warnings: Vec<ValidationIssue>,
}

#[derive(Debug, Serialize, Clone)]
pub struct ValidationIssue {
    path: String,
    message: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BackupResult {
    pub backup_path: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SaveResult {
    saved_path: String,
    backup_path: String,
    validation: ValidationResult,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct MigrationPreview {
    required: bool,
    operations: Vec<MigrationOperation>,
    warnings: Vec<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct MigrationOperation {
    key: String,
    label: String,
    detail: String,
    pending: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MigrationApplyResult {
    preview: MigrationPreview,
    backup_paths: Vec<String>,
    saved_path: String,
    validation: ValidationResult,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountLog {
    id: i64,
    account_id: String,
    action: String,
    status: String,
    detail: String,
    ts: String,
}

#[tauri::command]
pub fn get_project_paths() -> Result<ProjectPaths, String> {
    project_paths()
}

#[tauri::command]
pub fn load_config() -> Result<ConfigSnapshot, String> {
    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    config_snapshot(paths, raw_yaml)
}

#[tauri::command]
pub fn load_accounts(platform: Option<String>) -> Result<Vec<Account>, String> {
    let platform = normalized_platform_filter(platform.as_deref())?;
    let accounts = load_config()?.accounts;
    Ok(match platform {
        Some(platform) => accounts
            .into_iter()
            .filter(|account| account.platform() == platform)
            .collect(),
        None => accounts,
    })
}

#[tauri::command]
pub fn validate_config(payload: ConfigPayload) -> ValidationResult {
    validate_raw_yaml(&payload.raw_yaml)
}

#[tauri::command]
pub fn backup_config() -> Result<BackupResult, String> {
    backup_config_file()
}

#[tauri::command]
pub fn preview_config_migration() -> Result<MigrationPreview, String> {
    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;
    build_migration_preview(&config_value, &paths)
}

#[tauri::command]
pub fn apply_config_migration() -> Result<MigrationApplyResult, String> {
    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;
    let _preview = build_migration_preview(&config_value, &paths)?;

    let mut backup_paths = Vec::new();
    backup_paths.push(backup_config_file()?.backup_path);
    if let Some(db_backup) = backup_actions_db(&paths.actions_db_path)? {
        backup_paths.push(db_backup);
    }

    apply_config_value_migration(&mut config_value, &paths)?;
    migrate_actions_db(&paths.actions_db_path)?;

    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;
    let preview = build_migration_preview(&config_value, &paths)?;

    Ok(MigrationApplyResult {
        preview,
        backup_paths,
        saved_path: paths.config_path,
        validation,
    })
}

#[tauri::command]
pub fn save_config(payload: ConfigPayload) -> Result<SaveResult, String> {
    let validation = validate_raw_yaml(&payload.raw_yaml);
    if !validation.valid {
        return Err(format!(
            "config validation failed with {} error(s)",
            validation.errors.len()
        ));
    }

    let paths = project_paths()?;
    let backup = backup_config_file()?;
    fs::write(&paths.config_path, payload.raw_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;

    Ok(SaveResult {
        saved_path: paths.config_path,
        backup_path: backup.backup_path,
        validation,
    })
}

#[tauri::command]
pub fn save_accounts(payload: AccountsPayload) -> Result<SaveResult, String> {
    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;
    let platform = normalized_platform_filter(payload.platform.as_deref())?;

    if let Some(platform) = platform.as_deref() {
        ensure_platform_capability(platform, "accountManagement")?;
    }
    for account in &payload.accounts {
        let account_platform = normalize_platform(&account.platform, "accounts.platform")?;
        ensure_platform_capability(&account_platform, "accountManagement")?;
        if let Some(platform) = platform.as_deref() {
            if account_platform != platform {
                return Err(format!(
                    "account '{}' belongs to platform '{}' but request.platform is '{}'",
                    account.id.trim(),
                    account_platform,
                    platform
                ));
            }
        }
    }

    let account_values = payload
        .accounts
        .iter()
        .map(account_input_to_yaml_value)
        .collect::<Result<Vec<_>, _>>()?;

    match &mut config_value {
        Value::Mapping(mapping) => {
            let accounts_key = Value::String("accounts".to_string());
            if let Some(platform) = platform.as_deref() {
                let mut next_accounts = mapping
                    .get(&accounts_key)
                    .and_then(Value::as_sequence)
                    .cloned()
                    .unwrap_or_default()
                    .into_iter()
                    .filter(|account| yaml_account_platform(account) != platform)
                    .collect::<Vec<_>>();
                next_accounts.extend(account_values);
                mapping.insert(accounts_key, Value::Sequence(next_accounts));
            } else {
                mapping.insert(accounts_key, Value::Sequence(account_values));
            }
        }
        _ => {
            return Err("accounts.yaml root must be a mapping".to_string());
        }
    }

    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    let backup = backup_config_file()?;
    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;

    Ok(SaveResult {
        saved_path: paths.config_path,
        backup_path: backup.backup_path,
        validation,
    })
}

#[tauri::command]
pub fn get_login_credential_status(account_id: String) -> Result<LoginCredentialStatus, String> {
    let account_id = normalize_account_id(&account_id)?;
    let credential_ref = load_account_credential_ref(&account_id)?;
    Ok(login_credential_status(
        &account_id,
        credential_ref.as_deref(),
    ))
}

#[tauri::command]
pub fn save_login_password(payload: LoginPasswordPayload) -> Result<LoginCredentialStatus, String> {
    let account_id = normalize_account_id(&payload.account_id)?;
    if payload.password.is_empty() {
        return Err("login password must not be empty".to_string());
    }

    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;
    let credential_ref = load_account_credential_ref_from_value(&config_value, &account_id)?
        .unwrap_or_else(|| {
            format!(
                "{}{}",
                LOGIN_CREDENTIAL_PREFIX,
                sanitize_credential_component(&account_id)
            )
        });

    set_account_credential_ref(&mut config_value, &account_id, &credential_ref)?;
    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    let encrypted = protect_login_secret(&credential_ref, &payload.password)?;
    let credential_path = credential_ref_path(&credential_ref)?;
    if let Some(parent) = credential_path.parent() {
        fs::create_dir_all(parent).map_err(|err| {
            format!(
                "failed to create login credential directory {}: {}",
                normalize(parent),
                err
            )
        })?;
    }
    fs::write(&credential_path, encrypted).map_err(|err| {
        format!(
            "failed to write encrypted login credential {}: {}",
            normalize(&credential_path),
            err
        )
    })?;

    let _backup = backup_config_file()?;
    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;
    Ok(login_credential_status(&account_id, Some(&credential_ref)))
}

#[tauri::command]
pub fn delete_login_password(account_id: String) -> Result<LoginCredentialStatus, String> {
    let account_id = normalize_account_id(&account_id)?;
    let credential_ref = load_account_credential_ref(&account_id)?;
    if let Some(credential_ref) = credential_ref.as_deref() {
        delete_login_secret(credential_ref)?;
        let credential_path = credential_ref_path(credential_ref)?;
        if credential_path.exists() {
            fs::remove_file(&credential_path).map_err(|err| {
                format!(
                    "failed to delete encrypted login credential {}: {}",
                    normalize(&credential_path),
                    err
                )
            })?;
        }
    }
    Ok(login_credential_status(
        &account_id,
        credential_ref.as_deref(),
    ))
}

#[tauri::command]
pub fn load_ai_comment_settings() -> Result<AiCommentSettings, String> {
    Ok(load_config()?.ai_comment)
}

#[tauri::command]
pub fn save_ai_comment_settings(payload: AiCommentSettingsPayload) -> Result<SaveResult, String> {
    validate_ai_comment_settings_payload(&payload)?;

    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;

    let Value::Mapping(root) = &mut config_value else {
        return Err("accounts.yaml root must be a mapping".to_string());
    };
    root.insert(
        Value::String("ai_comment".to_string()),
        ai_comment_payload_to_yaml_value(&payload)?,
    );

    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    let backup = backup_config_file()?;
    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;

    Ok(SaveResult {
        saved_path: paths.config_path,
        backup_path: backup.backup_path,
        validation,
    })
}

#[tauri::command]
pub fn save_ai_comment_api_key(
    payload: AiCommentApiKeyPayload,
) -> Result<AiCommentApiKeyStatus, String> {
    let provider = normalize_ai_comment_provider(payload.provider.as_deref())?;
    if payload.api_key.trim().is_empty() {
        return Err("AI comment API Key must not be empty".to_string());
    }
    let credential_ref = ai_comment_credential_ref(&provider)?;
    let encrypted = protect_ai_comment_secret(&credential_ref, payload.api_key.trim())?;
    let credential_path = ai_comment_credential_ref_path(&credential_ref)?;
    if let Some(parent) = credential_path.parent() {
        fs::create_dir_all(parent).map_err(|err| {
            format!(
                "failed to create AI comment credential directory {}: {}",
                normalize(parent),
                err
            )
        })?;
    }
    fs::write(&credential_path, encrypted).map_err(|err| {
        format!(
            "failed to write encrypted AI comment credential {}: {}",
            normalize(&credential_path),
            err
        )
    })?;
    Ok(ai_comment_api_key_status_for_provider(&provider))
}

#[tauri::command]
pub fn delete_ai_comment_api_key(provider: Option<String>) -> Result<AiCommentApiKeyStatus, String> {
    let provider = normalize_ai_comment_provider(provider.as_deref())?;
    let credential_ref = ai_comment_credential_ref(&provider)?;
    delete_ai_comment_secret(&credential_ref)?;
    let credential_path = ai_comment_credential_ref_path(&credential_ref)?;
    if credential_path.exists() {
        fs::remove_file(&credential_path).map_err(|err| {
            format!(
                "failed to delete encrypted AI comment credential {}: {}",
                normalize(&credential_path),
                err
            )
        })?;
    }
    Ok(ai_comment_api_key_status_for_provider(&provider))
}

#[tauri::command]
pub fn get_ai_comment_api_key_status(
    provider: Option<String>,
) -> Result<AiCommentApiKeyStatus, String> {
    let provider = normalize_ai_comment_provider(provider.as_deref())?;
    Ok(ai_comment_api_key_status_for_provider(&provider))
}

#[tauri::command]
pub fn test_ai_comment_connection(
    payload: AiCommentTestPayload,
) -> Result<AiCommentGenerationResult, String> {
    validate_ai_comment_settings_payload(&payload.settings)?;
    run_ai_comment_generation(
        &payload.settings,
        "A short TikTok video about a useful everyday tip",
        "The creator demonstrates a simple idea in a natural, friendly style.",
    )
}

#[tauri::command]
pub fn preview_ai_comment(
    payload: AiCommentPreviewPayload,
) -> Result<AiCommentGenerationResult, String> {
    validate_ai_comment_settings_payload(&payload.settings)?;
    let title = payload.title.trim();
    let description = payload.description.as_deref().unwrap_or("").trim();
    if title.is_empty() && description.is_empty() {
        return Ok(AiCommentGenerationResult {
            ok: false,
            comment: String::new(),
            source: "ai".to_string(),
            reason: "missing_context".to_string(),
            latency_ms: 0,
            error: None,
            provider: payload.settings.provider.trim().to_string(),
            model: payload.settings.model.trim().to_string(),
        });
    }
    run_ai_comment_generation(&payload.settings, title, description)
}

#[tauri::command]
pub fn save_fyp_settings(payload: FypSettingsPayload) -> Result<SaveResult, String> {
    let platform = normalize_platform(payload.platform.as_deref().unwrap_or("tiktok"), "platform")?;
    ensure_platform_capability(&platform, "warmupTask")?;

    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;

    set_platform_section(
        &mut config_value,
        &platform,
        "warmup",
        fyp_payload_to_yaml_mapping(&payload)?,
    )?;

    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    let backup = backup_config_file()?;
    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;

    Ok(SaveResult {
        saved_path: paths.config_path,
        backup_path: backup.backup_path,
        validation,
    })
}

#[tauri::command]
pub fn save_target_engagement_settings(
    payload: TargetEngagementPayload,
) -> Result<SaveResult, String> {
    let platform = normalize_platform(payload.platform.as_deref().unwrap_or("tiktok"), "platform")?;
    ensure_platform_capability(&platform, "targetEngagement")?;

    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;

    set_platform_section(
        &mut config_value,
        &platform,
        "target_engagement",
        target_payload_to_yaml_mapping(&payload)?,
    )?;

    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    let backup = backup_config_file()?;
    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;

    Ok(SaveResult {
        saved_path: paths.config_path,
        backup_path: backup.backup_path,
        validation,
    })
}

#[tauri::command]
pub fn save_scheduler_settings(payload: SchedulerSettingsPayload) -> Result<SaveResult, String> {
    if payload.fires_per_day < 0 {
        return Err("scheduler.fires_per_day must be greater than or equal to 0".to_string());
    }
    for account in &payload.accounts {
        if account.id.trim().is_empty() {
            return Err("scheduler account id must not be empty".to_string());
        }
        if account.active_hours.is_empty() {
            return Err(format!("{} active_hours must not be empty", account.id));
        }
        for (index, range) in account.active_hours.iter().enumerate() {
            if range[0] < 0.0 || range[1] > 24.0 || range[0] >= range[1] {
                return Err(format!(
                    "{} active_hours[{}] must satisfy 0 <= start < end <= 24",
                    account.id, index
                ));
            }
        }
    }

    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;

    let mut scheduler_mapping =
        existing_platform_section_mapping(&config_value, "tiktok", "scheduler");
    scheduler_mapping.insert(
        Value::String("fires_per_day".to_string()),
        serde_yaml::to_value(payload.fires_per_day)
            .map_err(|err| format!("failed to serialize fires_per_day: {}", err))?,
    );
    set_platform_section(&mut config_value, "tiktok", "scheduler", scheduler_mapping)?;

    let Value::Mapping(root) = &mut config_value else {
        return Err("accounts.yaml root must be a mapping".to_string());
    };

    let account_settings = payload
        .accounts
        .iter()
        .map(|account| (account.id.trim().to_string(), account))
        .collect::<HashMap<_, _>>();
    let accounts_key = Value::String("accounts".to_string());
    let Some(accounts_value) = root.get_mut(&accounts_key) else {
        return Err("accounts must exist".to_string());
    };
    let Value::Sequence(accounts) = accounts_value else {
        return Err("accounts must be a list".to_string());
    };

    let mut seen_account_ids = HashSet::new();
    for account_value in accounts {
        let Value::Mapping(account_mapping) = account_value else {
            continue;
        };
        let id_key = Value::String("id".to_string());
        let Some(account_id) = account_mapping
            .get(&id_key)
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToString::to_string)
        else {
            continue;
        };
        let Some(settings) = account_settings.get(account_id.as_str()) else {
            continue;
        };
        seen_account_ids.insert(account_id);

        match settings.ip_group {
            Some(ip_group) => {
                account_mapping.insert(
                    Value::String("ip_group".to_string()),
                    serde_yaml::to_value(ip_group)
                        .map_err(|err| format!("failed to serialize ip_group: {}", err))?,
                );
            }
            None => {
                account_mapping.remove(&Value::String("ip_group".to_string()));
            }
        }
        account_mapping.insert(
            Value::String("active_hours".to_string()),
            serde_yaml::to_value(&settings.active_hours)
                .map_err(|err| format!("failed to serialize active_hours: {}", err))?,
        );
        account_mapping.insert(
            Value::String("scheduled".to_string()),
            Value::Bool(settings.scheduled),
        );
    }

    let missing = account_settings
        .keys()
        .filter(|account_id| !seen_account_ids.contains(*account_id))
        .cloned()
        .collect::<Vec<_>>();
    if !missing.is_empty() {
        return Err(format!(
            "scheduler settings reference missing accounts: {}",
            missing.join(", ")
        ));
    }

    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    let backup = backup_config_file()?;
    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;

    Ok(SaveResult {
        saved_path: paths.config_path,
        backup_path: backup.backup_path,
        validation,
    })
}

pub fn append_accounts_to_config(new_accounts: Vec<AccountInput>) -> Result<SaveResult, String> {
    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;

    match &mut config_value {
        Value::Mapping(mapping) => {
            let accounts_key = Value::String("accounts".to_string());
            if !mapping.contains_key(&accounts_key) {
                mapping.insert(accounts_key.clone(), Value::Sequence(Vec::new()));
            }
            let Some(account_values) = mapping.get_mut(&accounts_key) else {
                return Err("failed to access accounts list".to_string());
            };
            let Value::Sequence(existing_accounts) = account_values else {
                return Err("accounts must be a list".to_string());
            };

            for account in new_accounts {
                existing_accounts.push(account_input_to_yaml_value(&account)?);
            }
        }
        _ => return Err("accounts.yaml root must be a mapping".to_string()),
    }

    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    let backup = backup_config_file()?;
    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;

    Ok(SaveResult {
        saved_path: paths.config_path,
        backup_path: backup.backup_path,
        validation,
    })
}

pub fn save_platform_comment_files_config(
    platform: &str,
    general_file: &str,
    target_file: &str,
) -> Result<BackupResult, String> {
    let platform = normalize_platform(platform, "platform")?;
    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;

    let mut comments_mapping = Mapping::new();
    comments_mapping.insert(
        Value::String("general_file".to_string()),
        Value::String(
            file_name(general_file)
                .unwrap_or(general_file.trim())
                .to_string(),
        ),
    );
    comments_mapping.insert(
        Value::String("target_file".to_string()),
        Value::String(
            file_name(target_file)
                .unwrap_or(target_file.trim())
                .to_string(),
        ),
    );
    set_platform_section(&mut config_value, &platform, "comments", comments_mapping)?;

    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    let backup = backup_config_file()?;
    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;

    Ok(backup)
}

#[tauri::command]
pub fn save_notify_settings(payload: NotifySettingsPayload) -> Result<SaveResult, String> {
    if !matches!(
        payload.notify_type.as_str(),
        "serverchan" | "bark" | "webhook"
    ) {
        return Err("notify.type must be serverchan, bark, or webhook".to_string());
    }

    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let mut config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;

    let Value::Mapping(root) = &mut config_value else {
        return Err("accounts.yaml root must be a mapping".to_string());
    };

    root.insert(
        Value::String("notify".to_string()),
        notify_payload_to_yaml_value(&payload)?,
    );

    let next_yaml = serde_yaml::to_string(&config_value)
        .map_err(|err| format!("failed to serialize accounts.yaml: {}", err))?;
    let validation = validate_raw_yaml(&next_yaml);
    if !validation.valid {
        return Err(format_validation_errors(&validation));
    }

    let backup = backup_config_file()?;
    fs::write(&paths.config_path, next_yaml)
        .map_err(|err| format!("failed to write {}: {}", paths.config_path, err))?;

    Ok(SaveResult {
        saved_path: paths.config_path,
        backup_path: backup.backup_path,
        validation,
    })
}

#[tauri::command]
pub fn query_account_logs(
    account_id: String,
    limit: Option<usize>,
) -> Result<Vec<AccountLog>, String> {
    let paths = project_paths()?;
    let db_path = PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(vec![]);
    }

    let safe_limit = limit.unwrap_or(80).clamp(1, 500) as i64;
    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    let mut stmt = conn
        .prepare(
            "SELECT id, account_id, action, status, detail, ts
             FROM action_log
             WHERE account_id = ?1
             ORDER BY ts DESC, id DESC
             LIMIT ?2",
        )
        .map_err(|err| format!("failed to prepare account log query: {}", err))?;

    let rows = stmt
        .query_map(params![account_id, safe_limit], |row| {
            Ok(AccountLog {
                id: row.get(0)?,
                account_id: row.get(1)?,
                action: row.get(2)?,
                status: row.get(3)?,
                detail: redact_line(&row.get::<_, String>(4)?, &[]),
                ts: row.get(5)?,
            })
        })
        .map_err(|err| format!("failed to query account logs: {}", err))?;

    let mut logs = Vec::new();
    for row in rows {
        logs.push(row.map_err(|err| format!("failed to read account log row: {}", err))?);
    }

    Ok(logs)
}

fn config_snapshot(paths: ProjectPaths, raw_yaml: String) -> Result<ConfigSnapshot, String> {
    let config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;
    let config: ConfigYaml = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;
    let mut validation = validate_config_model(&config);
    validate_no_plaintext_login_passwords(&config_value, &mut validation.errors);
    validate_no_plaintext_ai_comment_api_key(&config_value, &mut validation.errors);
    validation.valid = validation.errors.is_empty();

    let default_browser_provider = config_default_browser_provider(&config);
    let mut accounts = map_accounts(
        config.accounts.as_deref().unwrap_or(&[]),
        &default_browser_provider,
    );
    enrich_accounts_with_recent_runs(&mut accounts, &paths.actions_db_path);

    Ok(ConfigSnapshot {
        paths,
        accounts,
        fyp_settings: map_fyp_settings(resolve_tiktok_warmup(&config)),
        target_engagement: map_target_engagement(resolve_tiktok_target_engagement(&config)),
        scheduler_settings: map_scheduler_settings(resolve_tiktok_scheduler(&config)),
        ai_comment: map_ai_comment_settings(config.ai_comment.as_ref()),
        notify: map_notify(config.notify.as_ref()),
        raw_yaml,
        config: config_value,
        validation,
    })
}

fn backup_config_file() -> Result<BackupResult, String> {
    let paths = project_paths()?;
    let source = PathBuf::from(&paths.config_path);
    if !source.exists() {
        return Err(format!("config file does not exist: {}", paths.config_path));
    }

    let backup_dir = source
        .parent()
        .ok_or_else(|| {
            format!(
                "failed to resolve config directory for {}",
                paths.config_path
            )
        })?
        .join("backups");
    fs::create_dir_all(&backup_dir).map_err(|err| {
        format!(
            "failed to create backup directory {}: {}",
            normalize(&backup_dir),
            err
        )
    })?;

    let filename = format!("accounts.{}.yaml", Local::now().format("%Y%m%d-%H%M%S"));
    let target = backup_dir.join(filename);
    fs::copy(&source, &target).map_err(|err| {
        format!(
            "failed to backup {} to {}: {}",
            paths.config_path,
            normalize(&target),
            err
        )
    })?;

    Ok(BackupResult {
        backup_path: normalize(&target),
    })
}

fn normalize_account_id(account_id: &str) -> Result<String, String> {
    let trimmed = account_id.trim();
    if trimmed.is_empty() {
        return Err("account id must not be empty".to_string());
    }
    Ok(trimmed.to_string())
}

fn load_account_credential_ref(account_id: &str) -> Result<Option<String>, String> {
    let paths = project_paths()?;
    let raw_yaml = fs::read_to_string(&paths.config_path)
        .map_err(|err| format!("failed to read {}: {}", paths.config_path, err))?;
    let config_value: Value = serde_yaml::from_str(&raw_yaml)
        .map_err(|err| format!("failed to parse {}: {}", paths.config_path, err))?;
    load_account_credential_ref_from_value(&config_value, account_id)
}

fn load_account_credential_ref_from_value(
    config_value: &Value,
    account_id: &str,
) -> Result<Option<String>, String> {
    let accounts = config_value
        .get("accounts")
        .and_then(Value::as_sequence)
        .ok_or_else(|| "accounts.yaml must contain an accounts list".to_string())?;
    for account in accounts {
        let Some(mapping) = account.as_mapping() else {
            continue;
        };
        let id = mapping
            .get(&Value::String("id".to_string()))
            .and_then(Value::as_str)
            .map(str::trim);
        if id == Some(account_id) {
            return Ok(mapping
                .get(&Value::String("login".to_string()))
                .and_then(Value::as_mapping)
                .and_then(|login| {
                    login
                        .get(&Value::String("credential_ref".to_string()))
                        .and_then(Value::as_str)
                })
                .and_then(|value| blank_to_none(Some(value))));
        }
    }
    Err(format!(
        "account '{}' was not found in accounts.yaml",
        account_id
    ))
}

fn set_account_credential_ref(
    config_value: &mut Value,
    account_id: &str,
    credential_ref: &str,
) -> Result<(), String> {
    let accounts = config_value
        .get_mut("accounts")
        .and_then(Value::as_sequence_mut)
        .ok_or_else(|| "accounts.yaml must contain an accounts list".to_string())?;
    for account in accounts {
        let Some(mapping) = account.as_mapping_mut() else {
            continue;
        };
        let id = mapping
            .get(&Value::String("id".to_string()))
            .and_then(Value::as_str)
            .map(str::trim);
        if id != Some(account_id) {
            continue;
        }

        let login_key = Value::String("login".to_string());
        if !mapping.contains_key(&login_key) {
            mapping.insert(login_key.clone(), Value::Mapping(Mapping::new()));
        }
        if !mapping
            .get(&login_key)
            .map(Value::is_mapping)
            .unwrap_or(false)
        {
            mapping.insert(login_key.clone(), Value::Mapping(Mapping::new()));
        }
        let login = mapping
            .get_mut(&login_key)
            .and_then(Value::as_mapping_mut)
            .ok_or_else(|| format!("account '{}' login config is not a mapping", account_id))?;
        if !login.contains_key(&Value::String("enabled".to_string())) {
            login.insert(Value::String("enabled".to_string()), Value::Bool(false));
        }
        if !login.contains_key(&Value::String("method".to_string())) {
            login.insert(
                Value::String("method".to_string()),
                Value::String(DEFAULT_LOGIN_METHOD.to_string()),
            );
        }
        login.insert(
            Value::String("credential_ref".to_string()),
            Value::String(credential_ref.to_string()),
        );
        return Ok(());
    }
    Err(format!(
        "account '{}' was not found in accounts.yaml",
        account_id
    ))
}

fn login_credential_status(
    account_id: &str,
    credential_ref: Option<&str>,
) -> LoginCredentialStatus {
    let Some(credential_ref) = credential_ref.and_then(|value| blank_to_none(Some(value))) else {
        return LoginCredentialStatus {
            account_id: account_id.to_string(),
            credential_ref: None,
            saved: false,
            readable: false,
            error: None,
        };
    };
    let path = match credential_ref_path(&credential_ref) {
        Ok(path) => path,
        Err(error) => {
            return LoginCredentialStatus {
                account_id: account_id.to_string(),
                credential_ref: Some(credential_ref),
                saved: false,
                readable: false,
                error: Some(error),
            };
        }
    };
    if !path.exists() {
        return LoginCredentialStatus {
            account_id: account_id.to_string(),
            credential_ref: Some(credential_ref),
            saved: false,
            readable: false,
            error: None,
        };
    }
    let encrypted = match fs::read_to_string(&path) {
        Ok(value) => value,
        Err(error) => {
            return LoginCredentialStatus {
                account_id: account_id.to_string(),
                credential_ref: Some(credential_ref),
                saved: true,
                readable: false,
                error: Some(format!(
                    "failed to read encrypted login credential {}: {}",
                    normalize(&path),
                    error
                )),
            };
        }
    };
    match unprotect_login_secret(&credential_ref, &encrypted) {
        Ok(_) => LoginCredentialStatus {
            account_id: account_id.to_string(),
            credential_ref: Some(credential_ref),
            saved: true,
            readable: true,
            error: None,
        },
        Err(error) => LoginCredentialStatus {
            account_id: account_id.to_string(),
            credential_ref: Some(credential_ref),
            saved: true,
            readable: false,
            error: Some(format!(
                "stored login credential exists but secure credential read failed: {}",
                error
            )),
        },
    }
}

fn ai_comment_api_key_status_for_provider(provider: &str) -> AiCommentApiKeyStatus {
    let provider = match normalize_ai_comment_provider(Some(provider)) {
        Ok(provider) => provider,
        Err(error) => {
            return AiCommentApiKeyStatus {
                provider: provider.to_string(),
                credential_ref: String::new(),
                saved: false,
                readable: false,
                error: Some(error),
            };
        }
    };
    let credential_ref = match ai_comment_credential_ref(&provider) {
        Ok(credential_ref) => credential_ref,
        Err(error) => {
            return AiCommentApiKeyStatus {
                provider,
                credential_ref: String::new(),
                saved: false,
                readable: false,
                error: Some(error),
            };
        }
    };
    let path = match ai_comment_credential_ref_path(&credential_ref) {
        Ok(path) => path,
        Err(error) => {
            return AiCommentApiKeyStatus {
                provider,
                credential_ref,
                saved: false,
                readable: false,
                error: Some(error),
            };
        }
    };
    if !path.exists() {
        return AiCommentApiKeyStatus {
            provider,
            credential_ref,
            saved: false,
            readable: false,
            error: None,
        };
    }
    let encrypted = match fs::read_to_string(&path) {
        Ok(encrypted) => encrypted,
        Err(error) => {
            return AiCommentApiKeyStatus {
                provider,
                credential_ref,
                saved: true,
                readable: false,
                error: Some(format!(
                    "failed to read encrypted AI comment credential {}: {}",
                    normalize(&path),
                    error
                )),
            };
        }
    };
    match unprotect_ai_comment_secret(&credential_ref, &encrypted) {
        Ok(_) => AiCommentApiKeyStatus {
            provider,
            credential_ref,
            saved: true,
            readable: true,
            error: None,
        },
        Err(error) => AiCommentApiKeyStatus {
            provider,
            credential_ref,
            saved: true,
            readable: false,
            error: Some(format!(
                "stored AI comment credential exists but secure credential read failed: {}",
                error
            )),
        },
    }
}

fn run_ai_comment_generation(
    settings: &AiCommentSettingsPayload,
    title: &str,
    description: &str,
) -> Result<AiCommentGenerationResult, String> {
    let provider = normalize_ai_comment_provider(Some(&settings.provider))?;
    let missing_api_key_result = || AiCommentGenerationResult {
        ok: false,
        comment: String::new(),
        source: "ai".to_string(),
        reason: "missing_api_key".to_string(),
        latency_ms: 0,
        error: None,
        provider: provider.clone(),
        model: settings.model.trim().to_string(),
    };
    let Some(api_key) = read_ai_comment_api_key_for_runtime(Some(&provider))? else {
        return Ok(missing_api_key_result());
    };
    if api_key.trim().is_empty() {
        return Ok(missing_api_key_result());
    }

    let result = run_ai_comment_python(settings, title, description, &provider, &api_key)?;
    Ok(AiCommentGenerationResult {
        error: result
            .error
            .map(|error| redact_text(&error, &vec![api_key.to_string()])),
        ..result
    })
}

fn run_ai_comment_python(
    settings: &AiCommentSettingsPayload,
    title: &str,
    description: &str,
    provider: &str,
    api_key: &str,
) -> Result<AiCommentGenerationResult, String> {
    let paths = project_paths()?;
    let payload = json!({
        "config": ai_comment_payload_to_python_config(settings)?,
        "context": {
            "platform": "tiktok",
            "title": title,
            "description": description,
        },
    });
    let (program, args, current_dir) = if paths.runtime_mode == "bundled" {
        let runtime_dir = Path::new(&paths.runtime_path)
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(|| PathBuf::from("."));
        (
            paths.runtime_path.clone(),
            vec!["ai-comment".to_string()],
            runtime_dir,
        )
    } else {
        let command = crate::paths::python_command_parts()?;
        let (program, args) = command
            .split_first()
            .ok_or_else(|| "python command is empty".to_string())?;
        let script = r#"
import json
import os
import sys

sys.path.insert(0, os.environ["AM_PROJECT_SRC_DIR"])
from ai_comment import generate_ai_comment, read_api_key_from_env

payload = json.loads(sys.stdin.read() or "{}")
config = payload.get("config") or {}
result = generate_ai_comment(payload.get("context") or {}, config, read_api_key_from_env)
result["provider"] = str(config.get("provider") or "")
result["model"] = str(config.get("model") or "")
print(json.dumps(result, ensure_ascii=True))
"#;
        let mut source_args = args.to_vec();
        source_args.push("-B".to_string());
        source_args.push("-c".to_string());
        source_args.push(script.to_string());
        (program.clone(), source_args, PathBuf::from("."))
    };

    let mut command_builder = Command::new(program);
    command_builder
        .args(args)
        .current_dir(current_dir)
        .env("AM_PROJECT_SRC_DIR", &paths.src_dir)
        .env("AM_AI_COMMENT_API_KEY", api_key)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    hide_console_window(&mut command_builder);
    let mut child = command_builder
        .spawn()
        .map_err(|err| format!("failed to start Python AI comment preview: {}", err))?;

    if let Some(stdin) = child.stdin.as_mut() {
        stdin
            .write_all(payload.to_string().as_bytes())
            .map_err(|err| format!("failed to write AI comment preview payload: {}", err))?;
    }

    let output = child
        .wait_with_output()
        .map_err(|err| format!("failed to run AI comment preview: {}", err))?;
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = redact_text(&String::from_utf8_lossy(&output.stderr), &vec![api_key.to_string()]);
    if !output.status.success() {
        return Ok(AiCommentGenerationResult {
            ok: false,
            comment: String::new(),
            source: "ai".to_string(),
            reason: "runtime_error".to_string(),
            latency_ms: 0,
            error: blank_to_none(Some(&stderr)),
            provider: provider.to_string(),
            model: settings.model.trim().to_string(),
        });
    }
    let mut result: AiCommentGenerationResult = serde_json::from_str(&stdout)
        .map_err(|err| format!("failed to parse AI comment preview result: {}", err))?;
    result.provider = provider.to_string();
    result.model = settings.model.trim().to_string();
    Ok(result)
}

fn hide_console_window(command: &mut Command) {
    #[cfg(windows)]
    {
        command.creation_flags(CREATE_NO_WINDOW);
    }
}

fn ai_comment_payload_to_python_config(
    settings: &AiCommentSettingsPayload,
) -> Result<JsonValue, String> {
    let provider = normalize_ai_comment_provider(Some(&settings.provider))?;
    Ok(json!({
        "enabled": true,
        "provider": provider,
        "base_url": settings.base_url.trim().trim_end_matches('/'),
        "model": settings.model.trim(),
        "timeout_seconds": settings.timeout_seconds,
        "max_comment_length": settings.max_comment_length,
        "fallback_to_pool": settings.fallback_to_pool.unwrap_or(true),
        "language": settings.language.trim(),
        "blocked_words": normalize_plain_string_list(&settings.blocked_words),
    }))
}

#[allow(dead_code)]
pub(crate) fn read_login_password_for_runtime(account_id: &str) -> Result<Option<String>, String> {
    let account_id = normalize_account_id(account_id)?;
    let Some(credential_ref) = load_account_credential_ref(&account_id)? else {
        return Ok(None);
    };
    let credential_path = credential_ref_path(&credential_ref)?;
    if !credential_path.exists() {
        return Ok(None);
    }
    let encrypted = fs::read_to_string(&credential_path).map_err(|err| {
        format!(
            "failed to read encrypted login credential {}: {}",
            normalize(&credential_path),
            err
        )
    })?;
    unprotect_login_secret(&credential_ref, &encrypted).map(Some)
}

#[allow(dead_code)]
pub(crate) fn read_ai_comment_api_key_for_runtime(
    provider: Option<&str>,
) -> Result<Option<String>, String> {
    let provider = normalize_ai_comment_provider(provider)?;
    let credential_ref = ai_comment_credential_ref(&provider)?;
    let credential_path = ai_comment_credential_ref_path(&credential_ref)?;
    if !credential_path.exists() {
        return Ok(None);
    }
    let encrypted = fs::read_to_string(&credential_path).map_err(|err| {
        format!(
            "failed to read encrypted AI comment credential {}: {}",
            normalize(&credential_path),
            err
        )
    })?;
    unprotect_ai_comment_secret(&credential_ref, &encrypted).map(Some)
}

fn credential_ref_path(credential_ref: &str) -> Result<PathBuf, String> {
    local_secret_ref_path(credential_ref, LOGIN_CREDENTIAL_PREFIX, "login")
}

fn ai_comment_credential_ref_path(credential_ref: &str) -> Result<PathBuf, String> {
    local_secret_ref_path(credential_ref, AI_COMMENT_CREDENTIAL_PREFIX, "ai_comment")
}

fn local_secret_ref_path(
    credential_ref: &str,
    expected_prefix: &str,
    category: &str,
) -> Result<PathBuf, String> {
    let normalized = credential_ref.trim();
    let Some(name) = normalized.strip_prefix(expected_prefix) else {
        return Err(format!(
            "unsupported credential_ref '{}'; expected prefix {}",
            normalized, expected_prefix
        ));
    };
    let name = sanitize_credential_component(name);
    let paths = project_paths()?;
    Ok(PathBuf::from(paths.data_dir)
        .join("credentials")
        .join(category)
        .join(format!("{}.dpapi", name)))
}

fn ai_comment_credential_ref(provider: &str) -> Result<String, String> {
    let provider = normalize_ai_comment_provider(Some(provider))?;
    Ok(format!(
        "{}{}/api-key",
        AI_COMMENT_CREDENTIAL_PREFIX, provider
    ))
}

fn sanitize_credential_component(value: &str) -> String {
    let sanitized = value
        .trim()
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.') {
                ch
            } else {
                '_'
            }
        })
        .collect::<String>();
    if sanitized.is_empty() {
        "account".to_string()
    } else {
        sanitized
    }
}

fn is_valid_login_credential_ref(value: &str) -> bool {
    let Some(name) = value.trim().strip_prefix(LOGIN_CREDENTIAL_PREFIX) else {
        return false;
    };
    !name.trim().is_empty()
        && name
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.'))
}

const LOGIN_SECRET_SERVICE: &str = "星域 Login Credential";
const LEGACY_LOGIN_SECRET_SERVICE: &str = "Account Matrix Login Credential";
const AI_COMMENT_SECRET_SERVICE: &str = "星域 AI Comment API Key";
const LEGACY_AI_COMMENT_SECRET_SERVICE: &str = "Account Matrix AI Comment API Key";

fn protect_login_secret(credential_ref: &str, secret: &str) -> Result<String, String> {
    protect_os_secret(LOGIN_SECRET_SERVICE, credential_ref, secret)
}

fn unprotect_login_secret(credential_ref: &str, encrypted: &str) -> Result<String, String> {
    unprotect_os_secret(LOGIN_SECRET_SERVICE, credential_ref, encrypted).or_else(|_| {
        unprotect_os_secret(LEGACY_LOGIN_SECRET_SERVICE, credential_ref, encrypted)
    })
}

fn delete_login_secret(credential_ref: &str) -> Result<(), String> {
    delete_os_secret(LOGIN_SECRET_SERVICE, credential_ref)?;
    let _ = delete_os_secret(LEGACY_LOGIN_SECRET_SERVICE, credential_ref);
    Ok(())
}

fn protect_ai_comment_secret(credential_ref: &str, secret: &str) -> Result<String, String> {
    protect_os_secret(AI_COMMENT_SECRET_SERVICE, credential_ref, secret)
}

fn unprotect_ai_comment_secret(credential_ref: &str, encrypted: &str) -> Result<String, String> {
    unprotect_os_secret(AI_COMMENT_SECRET_SERVICE, credential_ref, encrypted).or_else(|_| {
        unprotect_os_secret(LEGACY_AI_COMMENT_SECRET_SERVICE, credential_ref, encrypted)
    })
}

fn delete_ai_comment_secret(credential_ref: &str) -> Result<(), String> {
    delete_os_secret(AI_COMMENT_SECRET_SERVICE, credential_ref)?;
    let _ = delete_os_secret(LEGACY_AI_COMMENT_SECRET_SERVICE, credential_ref);
    Ok(())
}

#[cfg(target_os = "windows")]
fn protect_os_secret(_service: &str, _credential_ref: &str, secret: &str) -> Result<String, String> {
    let script = r#"$ErrorActionPreference = 'Stop'; $secret = [Console]::In.ReadToEnd(); $secure = ConvertTo-SecureString -String $secret -AsPlainText -Force; $secure | ConvertFrom-SecureString"#;
    let encrypted = run_powershell_with_stdin(script, secret, "encrypt login credential")?;
    let encrypted = encrypted.trim();
    if encrypted.is_empty() {
        Err("DPAPI returned an empty encrypted credential".to_string())
    } else {
        Ok(encrypted.to_string())
    }
}

#[cfg(target_os = "windows")]
fn unprotect_os_secret(_service: &str, _credential_ref: &str, encrypted: &str) -> Result<String, String> {
    let script = r#"$ErrorActionPreference = 'Stop'; $blob = [Console]::In.ReadToEnd(); $secure = ConvertTo-SecureString -String $blob; $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }"#;
    run_powershell_with_stdin(script, encrypted, "read login credential")
        .map(|value| value.trim_end_matches(['\r', '\n']).to_string())
}

#[cfg(target_os = "windows")]
fn delete_os_secret(_service: &str, _credential_ref: &str) -> Result<(), String> {
    Ok(())
}

#[cfg(target_os = "windows")]
fn run_powershell_with_stdin(script: &str, input: &str, action: &str) -> Result<String, String> {
    let mut child = Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", script])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|err| format!("failed to start PowerShell to {}: {}", action, err))?;

    let mut stdin = child
        .stdin
        .take()
        .ok_or_else(|| format!("failed to open PowerShell stdin to {}", action))?;
    stdin
        .write_all(input.as_bytes())
        .map_err(|err| format!("failed to send secret to PowerShell stdin: {}", err))?;
    drop(stdin);

    let output = child
        .wait_with_output()
        .map_err(|err| format!("failed to wait for PowerShell to {}: {}", action, err))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let detail = redact_text(stderr.trim(), &[]);
        return Err(if detail.is_empty() {
            format!("PowerShell failed to {}", action)
        } else {
            format!("PowerShell failed to {}: {}", action, detail)
        });
    }
    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

#[cfg(target_os = "macos")]
const MACOS_KEYCHAIN_MARKER: &str = "account-matrix-macos-keychain-v1";

#[cfg(target_os = "macos")]
fn protect_os_secret(service: &str, credential_ref: &str, secret: &str) -> Result<String, String> {
    macos_keychain_save_password(service, credential_ref, secret)?;
    Ok(format!(
        "{}\nservice={}\naccount={}\n",
        MACOS_KEYCHAIN_MARKER, service, credential_ref
    ))
}

#[cfg(target_os = "macos")]
fn unprotect_os_secret(service: &str, credential_ref: &str, encrypted: &str) -> Result<String, String> {
    if encrypted.lines().next() != Some(MACOS_KEYCHAIN_MARKER) {
        return Err("stored credential marker is not a macOS Keychain credential".to_string());
    }
    macos_keychain_read_password(service, credential_ref)
}

#[cfg(target_os = "macos")]
fn delete_os_secret(service: &str, credential_ref: &str) -> Result<(), String> {
    macos_keychain_delete_password(service, credential_ref)
}

#[cfg(target_os = "macos")]
type OsStatus = i32;
#[cfg(target_os = "macos")]
type SecKeychainRef = *const std::os::raw::c_void;
#[cfg(target_os = "macos")]
type SecKeychainItemRef = *mut std::os::raw::c_void;

#[cfg(target_os = "macos")]
const ERR_SEC_SUCCESS: OsStatus = 0;
#[cfg(target_os = "macos")]
const ERR_SEC_ITEM_NOT_FOUND: OsStatus = -25300;

#[cfg(target_os = "macos")]
#[link(name = "Security", kind = "framework")]
unsafe extern "C" {
    fn SecKeychainAddGenericPassword(
        keychain: SecKeychainRef,
        serviceNameLength: u32,
        serviceName: *const std::os::raw::c_char,
        accountNameLength: u32,
        accountName: *const std::os::raw::c_char,
        passwordLength: u32,
        passwordData: *const std::os::raw::c_void,
        itemRef: *mut SecKeychainItemRef,
    ) -> OsStatus;

    fn SecKeychainFindGenericPassword(
        keychain: SecKeychainRef,
        serviceNameLength: u32,
        serviceName: *const std::os::raw::c_char,
        accountNameLength: u32,
        accountName: *const std::os::raw::c_char,
        passwordLength: *mut u32,
        passwordData: *mut *mut std::os::raw::c_void,
        itemRef: *mut SecKeychainItemRef,
    ) -> OsStatus;

    fn SecKeychainItemModifyAttributesAndData(
        itemRef: SecKeychainItemRef,
        attrList: *const std::os::raw::c_void,
        length: u32,
        data: *const std::os::raw::c_void,
    ) -> OsStatus;

    fn SecKeychainItemDelete(itemRef: SecKeychainItemRef) -> OsStatus;

    fn SecKeychainItemFreeContent(
        attrList: *mut std::os::raw::c_void,
        data: *mut std::os::raw::c_void,
    ) -> OsStatus;
}

#[cfg(target_os = "macos")]
#[link(name = "CoreFoundation", kind = "framework")]
unsafe extern "C" {
    fn CFRelease(cf: *const std::os::raw::c_void);
}

#[cfg(target_os = "macos")]
fn macos_keychain_save_password(service: &str, credential_ref: &str, secret: &str) -> Result<(), String> {
    let service = service.as_bytes();
    let account = credential_ref.as_bytes();
    let password = secret.as_bytes();
    let service_len = macos_len(service.len(), "Keychain service")?;
    let account_len = macos_len(account.len(), "Keychain account")?;
    let password_len = macos_len(password.len(), "Keychain password")?;
    let mut item_ref: SecKeychainItemRef = std::ptr::null_mut();

    let find_status = unsafe {
        SecKeychainFindGenericPassword(
            std::ptr::null(),
            service_len,
            service.as_ptr() as *const std::os::raw::c_char,
            account_len,
            account.as_ptr() as *const std::os::raw::c_char,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            &mut item_ref,
        )
    };

    if find_status == ERR_SEC_SUCCESS {
        let update_status = unsafe {
            SecKeychainItemModifyAttributesAndData(
                item_ref,
                std::ptr::null(),
                password_len,
                password.as_ptr() as *const std::os::raw::c_void,
            )
        };
        macos_release_item(item_ref);
        return macos_status_to_result(update_status, "update credential in macOS Keychain");
    }
    if find_status != ERR_SEC_ITEM_NOT_FOUND {
        return macos_status_to_result(find_status, "find credential in macOS Keychain");
    }

    let add_status = unsafe {
        SecKeychainAddGenericPassword(
            std::ptr::null(),
            service_len,
            service.as_ptr() as *const std::os::raw::c_char,
            account_len,
            account.as_ptr() as *const std::os::raw::c_char,
            password_len,
            password.as_ptr() as *const std::os::raw::c_void,
            std::ptr::null_mut(),
        )
    };
    macos_status_to_result(add_status, "save credential to macOS Keychain")
}

#[cfg(target_os = "macos")]
fn macos_keychain_read_password(service: &str, credential_ref: &str) -> Result<String, String> {
    let service = service.as_bytes();
    let account = credential_ref.as_bytes();
    let service_len = macos_len(service.len(), "Keychain service")?;
    let account_len = macos_len(account.len(), "Keychain account")?;
    let mut password_len: u32 = 0;
    let mut password_data: *mut std::os::raw::c_void = std::ptr::null_mut();

    let status = unsafe {
        SecKeychainFindGenericPassword(
            std::ptr::null(),
            service_len,
            service.as_ptr() as *const std::os::raw::c_char,
            account_len,
            account.as_ptr() as *const std::os::raw::c_char,
            &mut password_len,
            &mut password_data,
            std::ptr::null_mut(),
        )
    };
    if status != ERR_SEC_SUCCESS {
        return macos_status_to_result(status, "read credential from macOS Keychain")
            .map(|_| String::new());
    }

    let password = unsafe {
        let bytes = std::slice::from_raw_parts(password_data as *const u8, password_len as usize);
        String::from_utf8(bytes.to_vec())
    }
    .map_err(|err| {
        format!(
            "macOS Keychain returned non-UTF-8 credential: {}",
            err
        )
    });
    unsafe {
        SecKeychainItemFreeContent(std::ptr::null_mut(), password_data);
    }
    password
}

#[cfg(target_os = "macos")]
fn macos_keychain_delete_password(service: &str, credential_ref: &str) -> Result<(), String> {
    let service = service.as_bytes();
    let account = credential_ref.as_bytes();
    let service_len = macos_len(service.len(), "Keychain service")?;
    let account_len = macos_len(account.len(), "Keychain account")?;
    let mut item_ref: SecKeychainItemRef = std::ptr::null_mut();

    let find_status = unsafe {
        SecKeychainFindGenericPassword(
            std::ptr::null(),
            service_len,
            service.as_ptr() as *const std::os::raw::c_char,
            account_len,
            account.as_ptr() as *const std::os::raw::c_char,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            &mut item_ref,
        )
    };
    if find_status == ERR_SEC_ITEM_NOT_FOUND {
        return Ok(());
    }
    if find_status != ERR_SEC_SUCCESS {
        return macos_status_to_result(find_status, "find credential in macOS Keychain");
    }

    let delete_status = unsafe { SecKeychainItemDelete(item_ref) };
    macos_release_item(item_ref);
    macos_status_to_result(delete_status, "delete credential from macOS Keychain")
}

#[cfg(target_os = "macos")]
fn macos_release_item(item_ref: SecKeychainItemRef) {
    if !item_ref.is_null() {
        unsafe {
            CFRelease(item_ref as *const std::os::raw::c_void);
        }
    }
}

#[cfg(target_os = "macos")]
fn macos_status_to_result(status: OsStatus, action: &str) -> Result<(), String> {
    if status == ERR_SEC_SUCCESS {
        Ok(())
    } else if status == ERR_SEC_ITEM_NOT_FOUND {
        Err(format!(
            "macOS Keychain failed to {}: item not found",
            action
        ))
    } else {
        Err(format!(
            "macOS Keychain failed to {}: OSStatus {}",
            action, status
        ))
    }
}

#[cfg(target_os = "macos")]
fn macos_len(len: usize, label: &str) -> Result<u32, String> {
    u32::try_from(len).map_err(|_| format!("{} is too large for macOS Keychain", label))
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn protect_os_secret(_service: &str, _credential_ref: &str, _secret: &str) -> Result<String, String> {
    Err("secure credential storage is not supported on this operating system".to_string())
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn unprotect_os_secret(
    _service: &str,
    _credential_ref: &str,
    _encrypted: &str,
) -> Result<String, String> {
    Err("secure credential storage is not supported on this operating system".to_string())
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn delete_os_secret(_service: &str, _credential_ref: &str) -> Result<(), String> {
    Ok(())
}

fn build_migration_preview(
    config: &Value,
    paths: &ProjectPaths,
) -> Result<MigrationPreview, String> {
    let mut operations = Vec::new();
    operations.push(MigrationOperation {
        key: "schema_version".to_string(),
        label: "记录配置 schema 版本".to_string(),
        detail: format!(
            "缺少 schema_version 的配置会被视为 legacy，并写入 schema_version: {}",
            CONFIG_SCHEMA_VERSION
        ),
        pending: config_schema_version(config) != Some(CONFIG_SCHEMA_VERSION),
    });
    operations.push(MigrationOperation {
        key: "accounts_platform".to_string(),
        label: "补齐账号 platform".to_string(),
        detail: "缺少 platform 的老账号会显式写入 platform: tiktok".to_string(),
        pending: accounts_missing_platform(config),
    });
    operations.push(MigrationOperation {
        key: "tiktok_warmup".to_string(),
        label: "迁移 TikTok FYP 配置".to_string(),
        detail: "defaults.daily_actions 会复制到 platforms.tiktok.warmup".to_string(),
        pending: legacy_daily_actions(config).is_some()
            && platform_section(config, "tiktok", "warmup").is_none(),
    });
    operations.push(MigrationOperation {
        key: "tiktok_target_engagement".to_string(),
        label: "迁移 TikTok 目标号配置".to_string(),
        detail: "target_accounts 会复制到 platforms.tiktok.target_engagement".to_string(),
        pending: config.get("target_accounts").is_some()
            && platform_section(config, "tiktok", "target_engagement").is_none(),
    });
    operations.push(MigrationOperation {
        key: "tiktok_comments".to_string(),
        label: "归属 TikTok 评论池".to_string(),
        detail: "comments.txt / comments_brand.txt 会记录到 platforms.tiktok.comments".to_string(),
        pending: platform_section(config, "tiktok", "comments").is_none(),
    });
    operations.push(MigrationOperation {
        key: "sqlite_platform".to_string(),
        label: "迁移旧统计记录".to_string(),
        detail: "actions.db 中旧 action_log / target_* 记录会补 platform=tiktok".to_string(),
        pending: sqlite_migration_pending(&paths.actions_db_path)?,
    });

    let mut warnings = Vec::new();
    if !PathBuf::from(&paths.actions_db_path).exists() {
        warnings.push(format!(
            "actions.db 不存在，apply 时只迁移 accounts.yaml：{}",
            paths.actions_db_path
        ));
    }

    Ok(MigrationPreview {
        required: operations.iter().any(|operation| operation.pending),
        operations,
        warnings,
    })
}

fn apply_config_value_migration(config: &mut Value, paths: &ProjectPaths) -> Result<(), String> {
    let Value::Mapping(root) = config else {
        return Err("accounts.yaml root must be a mapping".to_string());
    };

    root.insert(
        Value::String("schema_version".to_string()),
        Value::Number(serde_yaml::Number::from(CONFIG_SCHEMA_VERSION)),
    );

    if let Some(Value::Sequence(accounts)) = root.get_mut(&Value::String("accounts".to_string())) {
        for account in accounts {
            if let Value::Mapping(mapping) = account {
                let platform_key = Value::String("platform".to_string());
                let needs_platform = mapping
                    .get(&platform_key)
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
                    .is_none();
                if needs_platform {
                    mapping.insert(platform_key, Value::String("tiktok".to_string()));
                }
            }
        }
    }

    if platform_section(config, "tiktok", "warmup").is_none() {
        if let Some(Value::Mapping(warmup)) = legacy_daily_actions(config) {
            set_platform_section(config, "tiktok", "warmup", warmup.clone())?;
        }
    }

    if platform_section(config, "tiktok", "target_engagement").is_none() {
        if let Some(Value::Mapping(target)) = config.get("target_accounts") {
            set_platform_section(config, "tiktok", "target_engagement", target.clone())?;
        }
    }

    if platform_section(config, "tiktok", "comments").is_none() {
        let target_file = platform_section(config, "tiktok", "target_engagement")
            .and_then(|target| target.get("comments_file"))
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .or_else(|| {
                config
                    .get("target_accounts")
                    .and_then(|target| target.get("comments_file"))
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
            })
            .unwrap_or("comments_brand.txt");
        let mut comments = Mapping::new();
        comments.insert(
            Value::String("general_file".to_string()),
            Value::String(
                file_name(&paths.comments_path)
                    .unwrap_or("comments.txt")
                    .to_string(),
            ),
        );
        comments.insert(
            Value::String("target_file".to_string()),
            Value::String(file_name(target_file).unwrap_or(target_file).to_string()),
        );
        set_platform_section(config, "tiktok", "comments", comments)?;
    }

    Ok(())
}

fn legacy_daily_actions(config: &Value) -> Option<&Value> {
    config
        .get("defaults")
        .and_then(|defaults| defaults.get("daily_actions"))
}

fn accounts_missing_platform(config: &Value) -> bool {
    config
        .get("accounts")
        .and_then(Value::as_sequence)
        .map(|accounts| {
            accounts.iter().any(|account| {
                account
                    .get("platform")
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
                    .is_none()
            })
        })
        .unwrap_or(false)
}

fn config_schema_version(config: &Value) -> Option<i64> {
    config.get("schema_version").and_then(Value::as_i64)
}

fn backup_actions_db(actions_db_path: &str) -> Result<Option<String>, String> {
    let source = PathBuf::from(actions_db_path);
    if !source.exists() {
        return Ok(None);
    }
    let backup_dir = source
        .parent()
        .ok_or_else(|| format!("failed to resolve data directory for {}", actions_db_path))?
        .join("backups");
    fs::create_dir_all(&backup_dir).map_err(|err| {
        format!(
            "failed to create database backup directory {}: {}",
            normalize(&backup_dir),
            err
        )
    })?;
    let filename = format!("actions.{}.db", Local::now().format("%Y%m%d-%H%M%S"));
    let target = backup_dir.join(filename);
    fs::copy(&source, &target).map_err(|err| {
        format!(
            "failed to backup {} to {}: {}",
            actions_db_path,
            normalize(&target),
            err
        )
    })?;
    Ok(Some(normalize(&target)))
}

fn sqlite_migration_pending(actions_db_path: &str) -> Result<bool, String> {
    let db_path = PathBuf::from(actions_db_path);
    if !db_path.exists() {
        return Ok(false);
    }
    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", actions_db_path, err))?;
    for table in ["action_log", "target_engagements", "target_follows"] {
        if !sqlite_table_exists(&conn, table)? {
            continue;
        }
        if !sqlite_column_exists(&conn, table, "platform")? {
            return Ok(true);
        }
        let pending = conn
            .query_row(
                &format!(
                    "SELECT COUNT(*) FROM {} WHERE platform IS NULL OR TRIM(platform)=''",
                    table
                ),
                [],
                |row| row.get::<_, i64>(0),
            )
            .map_err(|err| format!("failed to inspect {} platform values: {}", table, err))?;
        if pending > 0 {
            return Ok(true);
        }
    }
    Ok(false)
}

fn migrate_actions_db(actions_db_path: &str) -> Result<(), String> {
    let db_path = PathBuf::from(actions_db_path);
    if !db_path.exists() {
        return Ok(());
    }
    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", actions_db_path, err))?;
    for table in ["action_log", "target_engagements", "target_follows"] {
        if !sqlite_table_exists(&conn, table)? {
            continue;
        }
        if !sqlite_column_exists(&conn, table, "platform")? {
            conn.execute(
                &format!("ALTER TABLE {} ADD COLUMN platform TEXT", table),
                [],
            )
            .map_err(|err| format!("failed to add {}.platform: {}", table, err))?;
        }
        conn.execute(
            &format!(
                "UPDATE {} SET platform='tiktok' WHERE platform IS NULL OR TRIM(platform)=''",
                table
            ),
            [],
        )
        .map_err(|err| format!("failed to backfill {}.platform: {}", table, err))?;
    }
    Ok(())
}

fn sqlite_table_exists(conn: &Connection, table_name: &str) -> Result<bool, String> {
    conn.query_row(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?1",
        params![table_name],
        |row| row.get::<_, i64>(0),
    )
    .map(|count| count > 0)
    .map_err(|err| format!("failed to inspect SQLite schema: {}", err))
}

fn sqlite_column_exists(
    conn: &Connection,
    table_name: &str,
    column_name: &str,
) -> Result<bool, String> {
    let mut stmt = conn
        .prepare(&format!("PRAGMA table_info({})", table_name))
        .map_err(|err| format!("failed to inspect SQLite table {}: {}", table_name, err))?;
    let rows = stmt
        .query_map([], |row| row.get::<_, String>(1))
        .map_err(|err| {
            format!(
                "failed to inspect SQLite columns for {}: {}",
                table_name, err
            )
        })?;
    for row in rows {
        if row.map_err(|err| format!("failed to read SQLite column metadata: {}", err))?
            == column_name
        {
            return Ok(true);
        }
    }
    Ok(false)
}

fn file_name(path: &str) -> Option<&str> {
    std::path::Path::new(path)
        .file_name()
        .and_then(|value| value.to_str())
}

fn validate_raw_yaml(raw_yaml: &str) -> ValidationResult {
    match serde_yaml::from_str::<ConfigYaml>(raw_yaml) {
        Ok(config) => {
            let mut validation = validate_config_model(&config);
            if let Ok(config_value) = serde_yaml::from_str::<Value>(raw_yaml) {
                validate_no_plaintext_login_passwords(&config_value, &mut validation.errors);
                validate_no_plaintext_ai_comment_api_key(&config_value, &mut validation.errors);
                validation.valid = validation.errors.is_empty();
            }
            validation
        }
        Err(err) => ValidationResult {
            valid: false,
            errors: vec![ValidationIssue {
                path: "accounts.yaml".to_string(),
                message: format!("YAML parse error: {}", err),
            }],
            warnings: vec![],
        },
    }
}

fn validate_no_plaintext_login_passwords(config: &Value, errors: &mut Vec<ValidationIssue>) {
    let Some(accounts) = config.get("accounts").and_then(Value::as_sequence) else {
        return;
    };
    for (index, account) in accounts.iter().enumerate() {
        let Some(mapping) = account.as_mapping() else {
            continue;
        };
        for key in ["password", "login_password"] {
            if mapping.contains_key(&Value::String(key.to_string())) {
                errors.push(issue(
                    format!("accounts[{}].{}", index, key),
                    "login password must not be stored in accounts.yaml; save it to local credentials instead",
                ));
            }
        }
        let Some(login) = mapping
            .get(&Value::String("login".to_string()))
            .and_then(Value::as_mapping)
        else {
            continue;
        };
        for key in login.keys().filter_map(Value::as_str) {
            let lowered = key.to_ascii_lowercase();
            if lowered.contains("password") || lowered.contains("secret") {
                errors.push(issue(
                    format!("accounts[{}].login.{}", index, key),
                    "login password must not be stored in accounts.yaml; save it to local credentials instead",
                ));
            }
        }
    }
}

fn validate_no_plaintext_ai_comment_api_key(config: &Value, errors: &mut Vec<ValidationIssue>) {
    let Some(ai_comment) = config
        .get("ai_comment")
        .and_then(Value::as_mapping)
    else {
        return;
    };
    for key in ai_comment.keys().filter_map(Value::as_str) {
        let lowered = key.to_ascii_lowercase();
        if lowered.contains("api_key")
            || lowered.contains("apikey")
            || lowered.contains("secret")
            || lowered.contains("token")
            || lowered.contains("authorization")
        {
            errors.push(issue(
                format!("ai_comment.{}", key),
                "AI comment API Key must not be stored in accounts.yaml; save it to local credentials instead",
            ));
        }
    }
}

fn validate_config_model(config: &ConfigYaml) -> ValidationResult {
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    let accounts = config.accounts.as_deref().unwrap_or(&[]);

    if accounts.is_empty() {
        errors.push(issue(
            "accounts",
            "accounts must contain at least one account",
        ));
    }
    validate_schema_version(config.schema_version, &mut errors, &mut warnings);

    let default_browser_provider = config_default_browser_provider(config);
    validate_accounts(
        accounts,
        &default_browser_provider,
        &mut errors,
        &mut warnings,
    );
    validate_browser_defaults(config.browser.as_ref(), &mut errors);
    validate_platforms(config.platforms.as_ref(), accounts, &mut errors);
    validate_target_accounts(
        config.target_accounts.as_ref(),
        accounts,
        "target_accounts",
        &mut errors,
    );
    validate_defaults(config.defaults.as_ref(), &mut errors);
    validate_bitbrowser(config.bitbrowser.as_ref(), &mut errors);
    validate_scheduler(config.scheduler.as_ref(), "scheduler", &mut errors);
    validate_ai_comment_yaml(config.ai_comment.as_ref(), "ai_comment", &mut errors);

    ValidationResult {
        valid: errors.is_empty(),
        errors,
        warnings,
    }
}

fn validate_schema_version(
    schema_version: Option<i64>,
    errors: &mut Vec<ValidationIssue>,
    warnings: &mut Vec<ValidationIssue>,
) {
    match schema_version {
        Some(CONFIG_SCHEMA_VERSION) => {}
        Some(version) if version > CONFIG_SCHEMA_VERSION => errors.push(issue(
            "schema_version",
            format!(
                "config schema_version {} is newer than supported {}",
                version, CONFIG_SCHEMA_VERSION
            ),
        )),
        Some(version) if version < CONFIG_SCHEMA_VERSION => warnings.push(issue(
            "schema_version",
            format!(
                "legacy config schema_version {} can be migrated to {}",
                version, CONFIG_SCHEMA_VERSION
            ),
        )),
        None => warnings.push(issue(
            "schema_version",
            format!(
                "missing schema_version is treated as legacy schema {}",
                CONFIG_SCHEMA_VERSION
            ),
        )),
        Some(_) => {}
    }
}

fn validate_accounts(
    accounts: &[AccountYaml],
    default_browser_provider: &str,
    errors: &mut Vec<ValidationIssue>,
    warnings: &mut Vec<ValidationIssue>,
) {
    let mut account_ids = HashSet::new();
    let mut profile_ids: HashMap<String, String> = HashMap::new();
    let mut enabled_by_ip_group: HashMap<i64, Vec<(String, [f64; 2])>> = HashMap::new();

    for (index, account) in accounts.iter().enumerate() {
        let base = format!("accounts[{}]", index);
        if account.id.trim().is_empty() {
            errors.push(issue(
                format!("{}.id", base),
                "account id must not be empty",
            ));
        } else if !account_ids.insert(account.id.clone()) {
            errors.push(issue(
                format!("{}.id", base),
                format!("duplicate account id '{}'", account.id),
            ));
        }

        if let Some(platform) = account.platform.as_deref() {
            if !is_valid_platform(platform) {
                errors.push(issue(
                    format!("{}.platform", base),
                    format!("unsupported platform '{}'", platform),
                ));
            }
        }

        let provider = match account_browser_provider_result(account, default_browser_provider) {
            Ok(provider) => provider,
            Err(message) => {
                errors.push(issue(format!("{}.browser_provider", base), message));
                DEFAULT_BROWSER_PROVIDER.to_string()
            }
        };

        if account.enabled.unwrap_or(true) {
            if provider == DEFAULT_BROWSER_PROVIDER && account_browser_profile_id(account).is_none()
            {
                errors.push(issue(
                    format!("{}.bitbrowser_profile_id", base),
                    "BitBrowser 浏览器环境需要配置 bitbrowser_profile_id 或 browser.profile_id",
                ));
            }
            if provider == "builtin_chromium" {
                warnings.push(issue(
                    format!("{}.browser_provider", base),
                    "内置 Chromium 仅作为可选测试环境，不能替代 BitBrowser 的指纹浏览器能力",
                ));
            }
        }

        if provider == "builtin_chromium" {
            if let Some(proxy_type) = account_browser_proxy_type(account) {
                if !matches!(proxy_type.as_str(), "http" | "https" | "socks5") {
                    errors.push(issue(
                        format!("{}.browser.proxy_type", base),
                        "browser.proxy_type must be http, https, or socks5",
                    ));
                }
            }
            if let Some(proxy) = account_browser_proxy(account) {
                if let Err(message) = validate_builtin_proxy(&proxy) {
                    errors.push(issue(format!("{}.browser.proxy", base), message));
                }
            }
        }

        if let Some(login) = account.login.as_ref() {
            let login_enabled = login.enabled.unwrap_or(false);
            let method = login
                .method
                .as_deref()
                .and_then(|value| blank_to_none(Some(value)))
                .unwrap_or_else(|| DEFAULT_LOGIN_METHOD.to_string());
            if method != DEFAULT_LOGIN_METHOD {
                errors.push(issue(
                    format!("{}.login.method", base),
                    "login.method must be password for V1",
                ));
            }
            let username = blank_to_none(login.username.as_deref());
            let credential_ref = blank_to_none(login.credential_ref.as_deref());
            if let Some(credential_ref) = credential_ref.as_deref() {
                if !is_valid_login_credential_ref(credential_ref) {
                    errors.push(issue(
                        format!("{}.login.credential_ref", base),
                        format!(
                            "login.credential_ref must start with {} and contain only safe account characters",
                            LOGIN_CREDENTIAL_PREFIX
                        ),
                    ));
                }
            }
            if login_enabled {
                if username.is_none() {
                    errors.push(issue(
                        format!("{}.login.username", base),
                        "login.username is required when auto login is enabled",
                    ));
                }
                if credential_ref.is_none() {
                    errors.push(issue(
                        format!("{}.login.credential_ref", base),
                        "login.credential_ref is required when auto login is enabled; save the password first",
                    ));
                }
            }
        }

        if let Some(profile_id) = account_browser_profile_id(account) {
            let normalized = profile_id.trim();
            if !normalized.is_empty() {
                if let Some(first_account_id) =
                    profile_ids.insert(normalized.to_string(), account.id.clone())
                {
                    errors.push(issue(
                        format!("{}.bitbrowser_profile_id", base),
                        format!(
                            "duplicate profile_id '{}' used by '{}' and '{}'",
                            normalized, first_account_id, account.id
                        ),
                    ));
                }
            }
        }

        let active_hours = account.active_hours.as_deref().unwrap_or(&[]);
        if active_hours.is_empty() {
            errors.push(issue(
                format!("{}.active_hours", base),
                "active_hours must contain at least one [start, end] range",
            ));
        }

        for (range_index, range) in active_hours.iter().enumerate() {
            let path = format!("{}.active_hours[{}]", base, range_index);
            validate_hour_range(&path, *range, errors);
        }

        if account.enabled.unwrap_or(true) && account.scheduled.unwrap_or(true) {
            if let Some(ip_group) = account.ip_group {
                for range in active_hours {
                    enabled_by_ip_group
                        .entry(ip_group)
                        .or_default()
                        .push((account.id.clone(), *range));
                }
            } else {
                warnings.push(issue(
                    format!("{}.ip_group", base),
                    "参与调度的启用账号未配置 ip_group，排班冲突检测会跳过它",
                ));
            }
        }
    }

    for (ip_group, ranges) in enabled_by_ip_group {
        for left_index in 0..ranges.len() {
            for right_index in (left_index + 1)..ranges.len() {
                let (left_id, left_range) = &ranges[left_index];
                let (right_id, right_range) = &ranges[right_index];
                if ranges_overlap(*left_range, *right_range) {
                    errors.push(issue(
                        format!("accounts.ip_group[{}].active_hours", ip_group),
                        format!(
                            "参与调度的启用账号 '{}' 和 '{}' active_hours 有重叠",
                            left_id, right_id
                        ),
                    ));
                }
            }
        }
    }
}

fn validate_platforms(
    platforms: Option<&HashMap<String, PlatformYaml>>,
    accounts: &[AccountYaml],
    errors: &mut Vec<ValidationIssue>,
) {
    let Some(platforms) = platforms else {
        return;
    };

    for (platform, config) in platforms {
        let base = format!("platforms.{}", platform);
        if !is_valid_platform(platform) {
            errors.push(issue(base, format!("unsupported platform '{}'", platform)));
            continue;
        }

        if let Some(warmup) = config.warmup.as_ref() {
            validate_daily_actions(&format!("{}.warmup", base), warmup, errors);
        }

        validate_target_accounts(
            config.target_engagement.as_ref(),
            accounts,
            &format!("{}.target_engagement", base),
            errors,
        );

        validate_scheduler(
            config.scheduler.as_ref(),
            &format!("{}.scheduler", base),
            errors,
        );

        if let Some(scheduler) = config.scheduler.as_ref() {
            if let Some(active_hours) = scheduler.active_hours.as_ref() {
                for (index, range) in active_hours.iter().enumerate() {
                    validate_hour_range(
                        &format!("{}.scheduler.active_hours[{}]", base, index),
                        *range,
                        errors,
                    );
                }
            }
        }

        if let Some(comments) = config.comments.as_ref() {
            validate_optional_filename(
                &format!("{}.comments.general_file", base),
                comments.general_file.as_deref(),
                errors,
            );
            validate_optional_filename(
                &format!("{}.comments.target_file", base),
                comments.target_file.as_deref(),
                errors,
            );
        }
    }
}

fn validate_target_accounts(
    target: Option<&TargetAccountsYaml>,
    accounts: &[AccountYaml],
    base_path: &str,
    errors: &mut Vec<ValidationIssue>,
) {
    let Some(target) = target else {
        return;
    };
    let account_ids: HashSet<&str> = accounts.iter().map(|account| account.id.as_str()).collect();

    if let Some(handles) = target.handles.as_ref() {
        for (index, handle) in handles.iter().enumerate() {
            if !is_valid_tiktok_handle(handle) {
                errors.push(issue(
                    format!("{}.handles[{}]", base_path, index),
                    format!("invalid TikTok handle '{}'", handle),
                ));
            }
        }
    }

    if let Some(participants) = target.participants.as_ref() {
        for (index, participant) in participants.iter().enumerate() {
            if !account_ids.contains(participant.as_str()) {
                errors.push(issue(
                    format!("{}.participants[{}]", base_path, index),
                    format!(
                        "participant '{}' does not reference an existing account",
                        participant
                    ),
                ));
            }
        }
    }

    validate_optional_positive(
        &format!("{}.first_run_latest_n", base_path),
        target.first_run_latest_n,
        errors,
    );
    validate_optional_positive(
        &format!("{}.max_videos_per_run", base_path),
        target.max_videos_per_run,
        errors,
    );
    validate_optional_probability(
        &format!("{}.like_probability", base_path),
        target.like_probability,
        errors,
    );
    validate_optional_probability(
        &format!("{}.comment_probability", base_path),
        target.comment_probability,
        errors,
    );
    validate_optional_probability(
        &format!("{}.follow_probability", base_path),
        target.follow_probability,
        errors,
    );
}

fn validate_defaults(defaults: Option<&DefaultsYaml>, errors: &mut Vec<ValidationIssue>) {
    if let Some(active_hours) = defaults.and_then(|defaults| defaults.active_hours.as_ref()) {
        for (index, range) in active_hours.iter().enumerate() {
            validate_hour_range(&format!("defaults.active_hours[{}]", index), *range, errors);
        }
    }

    let Some(daily_actions) = defaults.and_then(|defaults| defaults.daily_actions.as_ref()) else {
        return;
    };

    validate_daily_actions("defaults.daily_actions", daily_actions, errors);
}

fn validate_daily_actions(
    base_path: &str,
    daily_actions: &DailyActionsYaml,
    errors: &mut Vec<ValidationIssue>,
) {
    if let Some(range) = daily_actions.fyp_browse_minutes {
        validate_number_range(&format!("{}.fyp_browse_minutes", base_path), range, errors);
    }
    if let Some(range) = daily_actions.follows_per_session {
        validate_integer_range(&format!("{}.follows_per_session", base_path), range, errors);
    }
    validate_optional_probability(
        &format!("{}.like_probability", base_path),
        daily_actions.like_probability,
        errors,
    );

    if let Some(comment) = daily_actions.comment.as_ref() {
        if let Some(range) = comment.comments_per_session {
            validate_integer_range(
                &format!("{}.comment.comments_per_session", base_path),
                range,
                errors,
            );
        }
        validate_optional_positive(
            &format!("{}.comment.min_video_comments", base_path),
            comment.min_video_comments,
            errors,
        );
        validate_optional_probability(
            &format!("{}.comment.probability", base_path),
            comment.probability,
            errors,
        );
    }
}

fn validate_ai_comment_yaml(
    ai_comment: Option<&AiCommentYaml>,
    base_path: &str,
    errors: &mut Vec<ValidationIssue>,
) {
    let Some(ai_comment) = ai_comment else {
        return;
    };
    if let Some(provider) = ai_comment.provider.as_deref() {
        if let Err(message) = validate_ai_comment_provider(provider) {
            errors.push(issue(format!("{}.provider", base_path), message));
        }
    }
    if let Some(base_url) = ai_comment.base_url.as_deref() {
        if let Err(message) = validate_ai_comment_base_url(base_url) {
            errors.push(issue(format!("{}.base_url", base_path), message));
        }
    }
    if let Some(model) = ai_comment.model.as_deref() {
        if blank_to_none(Some(model)).is_none() {
            errors.push(issue(
                format!("{}.model", base_path),
                "ai_comment.model must not be empty",
            ));
        }
    }
    validate_optional_positive(
        &format!("{}.timeout_seconds", base_path),
        ai_comment.timeout_seconds,
        errors,
    );
    validate_optional_positive(
        &format!("{}.max_comment_length", base_path),
        ai_comment.max_comment_length,
        errors,
    );
    if let Some(language) = ai_comment.language.as_deref() {
        if blank_to_none(Some(language)).is_none() {
            errors.push(issue(
                format!("{}.language", base_path),
                "ai_comment.language must not be empty",
            ));
        }
    }
}

fn validate_bitbrowser(bitbrowser: Option<&BitbrowserYaml>, errors: &mut Vec<ValidationIssue>) {
    let Some(api_url) = bitbrowser.and_then(|bitbrowser| bitbrowser.api_url.as_ref()) else {
        errors.push(issue(
            "bitbrowser.api_url",
            "BitBrowser API URL is required",
        ));
        return;
    };

    let value = api_url.trim();
    if value.is_empty()
        || value.contains(char::is_whitespace)
        || !(value.starts_with("http://") || value.starts_with("https://"))
    {
        errors.push(issue(
            "bitbrowser.api_url",
            "BitBrowser API URL must start with http:// or https:// and contain no whitespace",
        ));
    }
}

fn validate_browser_defaults(
    browser: Option<&BrowserDefaultsYaml>,
    errors: &mut Vec<ValidationIssue>,
) {
    if let Some(provider) = browser.and_then(|browser| browser.default_provider.as_deref()) {
        if let Err(message) = normalize_browser_provider(provider, "browser.default_provider") {
            errors.push(issue("browser.default_provider", message));
        }
    }
}

fn validate_scheduler(
    scheduler: Option<&SchedulerYaml>,
    base_path: &str,
    errors: &mut Vec<ValidationIssue>,
) {
    if let Some(fires_per_day) = scheduler.and_then(|scheduler| scheduler.fires_per_day) {
        if fires_per_day < 0 {
            errors.push(issue(
                format!("{}.fires_per_day", base_path),
                "fires_per_day must be greater than or equal to 0",
            ));
        }
    }
}

fn validate_hour_range(path: &str, range: [f64; 2], errors: &mut Vec<ValidationIssue>) {
    if range[0] < 0.0 || range[1] > 24.0 || range[0] >= range[1] {
        errors.push(issue(
            path,
            "active_hours range must satisfy 0 <= start < end <= 24",
        ));
    }
}

fn validate_number_range(path: &str, range: [f64; 2], errors: &mut Vec<ValidationIssue>) {
    if range[0] < 0.0 || range[0] > range[1] {
        errors.push(issue(path, "range must satisfy 0 <= min <= max"));
    }
}

fn validate_integer_range(path: &str, range: [i64; 2], errors: &mut Vec<ValidationIssue>) {
    if range[0] < 0 || range[0] > range[1] {
        errors.push(issue(path, "range must satisfy 0 <= min <= max"));
    }
}

fn validate_optional_probability(
    path: &str,
    value: Option<f64>,
    errors: &mut Vec<ValidationIssue>,
) {
    if let Some(value) = value {
        if !(0.0..=1.0).contains(&value) {
            errors.push(issue(path, "probability must be between 0 and 1"));
        }
    }
}

fn validate_optional_positive(path: &str, value: Option<i64>, errors: &mut Vec<ValidationIssue>) {
    if let Some(value) = value {
        if value < 0 {
            errors.push(issue(path, "value must be greater than or equal to 0"));
        }
    }
}

fn validate_optional_filename(path: &str, value: Option<&str>, errors: &mut Vec<ValidationIssue>) {
    let Some(value) = value.map(str::trim) else {
        return;
    };
    if value.is_empty() {
        errors.push(issue(path, "file name must not be empty"));
    } else if value.contains('\\') || value.contains('/') || value.contains("..") {
        errors.push(issue(
            path,
            "file name must stay inside the config directory",
        ));
    }
}

fn ranges_overlap(left: [f64; 2], right: [f64; 2]) -> bool {
    left[0] < right[1] && right[0] < left[1]
}

fn is_valid_tiktok_handle(handle: &str) -> bool {
    let normalized = handle.trim().trim_start_matches('@');
    !normalized.is_empty()
        && normalized.len() <= 24
        && normalized
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '.')
}

fn map_accounts(accounts: &[AccountYaml], default_browser_provider: &str) -> Vec<Account> {
    accounts
        .iter()
        .map(|account| {
            let provider = account_browser_provider(account, default_browser_provider);
            let profile_id = account_browser_profile_id(account);
            let proxy_type = account_browser_proxy_type(account);
            let proxy = account_browser_proxy(account);
            let user_data_dir = account_browser_user_data_dir(account);
            let login = account_login(account);
            Account {
                platform: account
                    .platform
                    .as_deref()
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
                    .map(ToString::to_string)
                    .unwrap_or_else(|| "tiktok".to_string()),
                id: account.id.clone(),
                enabled: account.enabled.unwrap_or(true),
                scheduled: account.scheduled.unwrap_or(true),
                ip_group: account.ip_group,
                active_hours: account.active_hours.clone().unwrap_or_default(),
                browser_provider: provider.clone(),
                browser: Some(AccountBrowser {
                    provider,
                    profile_id: profile_id.clone(),
                    proxy_type,
                    proxy,
                    user_data_dir,
                }),
                login,
                bitbrowser_profile_id: profile_id,
                notes: blank_to_none(account.notes.as_deref()),
                profile_open: None,
                login_check: None,
                last_run_at: None,
                last_status: Some("unknown".to_string()),
            }
        })
        .collect()
}

fn enrich_accounts_with_recent_runs(accounts: &mut [Account], actions_db_path: &str) {
    let db_path = PathBuf::from(actions_db_path);
    if !db_path.exists() {
        return;
    }

    let Ok(conn) = Connection::open(&db_path) else {
        return;
    };

    for account in accounts {
        let latest = conn.query_row(
            "SELECT status, ts
             FROM action_log
             WHERE account_id = ?1
             ORDER BY ts DESC, id DESC
             LIMIT 1",
            params![account.id.as_str()],
            |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)),
        );

        if let Ok((status, ts)) = latest {
            account.last_status = Some(map_action_status(&status));
            account.last_run_at = Some(ts);
        }

        let latest_login_check = conn.query_row(
            "SELECT action, status, detail, ts
             FROM action_log
             WHERE account_id = ?1
               AND action IN ('login_check', 'register_auto_complete')
             ORDER BY ts DESC, id DESC
             LIMIT 1",
            params![account.id.as_str()],
            |row| {
                let action = row.get::<_, String>(0)?;
                let status = row.get::<_, String>(1)?;
                Ok(AccountLoginCheck {
                    status: if action == "register_auto_complete" && status == "ok" {
                        "logged_in".to_string()
                    } else {
                        status
                    },
                    detail: redact_line(&row.get::<_, String>(2)?, &[]),
                    ts: row.get(3)?,
                })
            },
        );

        if let Ok(login_check) = latest_login_check {
            account.login_check = Some(login_check);
        }
    }
}

fn account_input_to_yaml_value(account: &AccountInput) -> Result<Value, String> {
    let provider = normalize_browser_provider(
        account
            .browser_provider
            .as_deref()
            .or_else(|| {
                account
                    .browser
                    .as_ref()
                    .and_then(|browser| browser.provider.as_deref())
            })
            .unwrap_or(DEFAULT_BROWSER_PROVIDER),
        "accounts.browser_provider",
    )?;
    let mut mapping = Mapping::new();
    mapping.insert(
        Value::String("id".to_string()),
        Value::String(account.id.trim().to_string()),
    );
    mapping.insert(
        Value::String("platform".to_string()),
        Value::String(account.platform.trim().to_string()),
    );
    mapping.insert(
        Value::String("enabled".to_string()),
        Value::Bool(account.enabled),
    );
    if let Some(scheduled) = account.scheduled {
        mapping.insert(
            Value::String("scheduled".to_string()),
            Value::Bool(scheduled),
        );
    }

    if let Some(ip_group) = account.ip_group {
        mapping.insert(
            Value::String("ip_group".to_string()),
            serde_yaml::to_value(ip_group)
                .map_err(|err| format!("failed to serialize ip_group: {}", err))?,
        );
    }

    mapping.insert(
        Value::String("active_hours".to_string()),
        serde_yaml::to_value(&account.active_hours)
            .map_err(|err| format!("failed to serialize active_hours: {}", err))?,
    );

    if let Some(profile_id) = blank_to_none(account.bitbrowser_profile_id.as_deref()) {
        mapping.insert(
            Value::String("bitbrowser_profile_id".to_string()),
            Value::String(profile_id),
        );
    }

    if provider != DEFAULT_BROWSER_PROVIDER || account.browser.is_some() {
        mapping.insert(
            Value::String("browser_provider".to_string()),
            Value::String(provider.clone()),
        );
        let profile_id = account
            .browser
            .as_ref()
            .and_then(|browser| blank_to_none(browser.profile_id.as_deref()))
            .or_else(|| blank_to_none(account.bitbrowser_profile_id.as_deref()));
        let proxy_type = account
            .browser
            .as_ref()
            .and_then(|browser| blank_to_none(browser.proxy_type.as_deref()));
        let proxy = account
            .browser
            .as_ref()
            .and_then(|browser| blank_to_none(browser.proxy.as_deref()));
        let user_data_dir = account
            .browser
            .as_ref()
            .and_then(|browser| blank_to_none(browser.user_data_dir.as_deref()));
        let mut browser_mapping = Mapping::new();
        browser_mapping.insert(
            Value::String("provider".to_string()),
            Value::String(provider),
        );
        if let Some(profile_id) = profile_id {
            browser_mapping.insert(
                Value::String("profile_id".to_string()),
                Value::String(profile_id),
            );
        }
        if let Some(proxy_type) = proxy_type {
            browser_mapping.insert(
                Value::String("proxy_type".to_string()),
                Value::String(proxy_type),
            );
        }
        if let Some(proxy) = proxy {
            browser_mapping.insert(Value::String("proxy".to_string()), Value::String(proxy));
        }
        if let Some(user_data_dir) = user_data_dir {
            browser_mapping.insert(
                Value::String("user_data_dir".to_string()),
                Value::String(user_data_dir),
            );
        }
        mapping.insert(
            Value::String("browser".to_string()),
            Value::Mapping(browser_mapping),
        );
    }

    if let Some(login) = account.login.as_ref() {
        let method = blank_to_none(login.method.as_deref())
            .unwrap_or_else(|| DEFAULT_LOGIN_METHOD.to_string());
        if method != DEFAULT_LOGIN_METHOD {
            return Err("accounts.login.method must be password for V1".to_string());
        }
        let username = blank_to_none(login.username.as_deref());
        let credential_ref = blank_to_none(login.credential_ref.as_deref());
        if let Some(credential_ref) = credential_ref.as_deref() {
            if !is_valid_login_credential_ref(credential_ref) {
                return Err(format!(
                    "accounts.login.credential_ref must start with {} and contain only safe account characters",
                    LOGIN_CREDENTIAL_PREFIX
                ));
            }
        }
        if login.enabled || username.is_some() || credential_ref.is_some() {
            let mut login_mapping = Mapping::new();
            login_mapping.insert(
                Value::String("enabled".to_string()),
                Value::Bool(login.enabled),
            );
            login_mapping.insert(Value::String("method".to_string()), Value::String(method));
            if let Some(username) = username {
                login_mapping.insert(
                    Value::String("username".to_string()),
                    Value::String(username),
                );
            }
            if let Some(credential_ref) = credential_ref {
                login_mapping.insert(
                    Value::String("credential_ref".to_string()),
                    Value::String(credential_ref),
                );
            }
            mapping.insert(
                Value::String("login".to_string()),
                Value::Mapping(login_mapping),
            );
        }
    }

    if let Some(notes) = blank_to_none(account.notes.as_deref()) {
        mapping.insert(Value::String("notes".to_string()), Value::String(notes));
    }

    Ok(Value::Mapping(mapping))
}

fn fyp_payload_to_yaml_mapping(payload: &FypSettingsPayload) -> Result<Mapping, String> {
    let mut daily_actions_mapping = Mapping::new();
    daily_actions_mapping.insert(
        Value::String("fyp_browse_minutes".to_string()),
        serde_yaml::to_value(payload.fyp_browse_minutes)
            .map_err(|err| format!("failed to serialize fyp_browse_minutes: {}", err))?,
    );
    daily_actions_mapping.insert(
        Value::String("like_probability".to_string()),
        serde_yaml::to_value(payload.like_probability)
            .map_err(|err| format!("failed to serialize like_probability: {}", err))?,
    );
    daily_actions_mapping.insert(
        Value::String("follows_per_session".to_string()),
        serde_yaml::to_value(payload.follows_per_session)
            .map_err(|err| format!("failed to serialize follows_per_session: {}", err))?,
    );

    let mut comment_mapping = Mapping::new();
    comment_mapping.insert(
        Value::String("enabled".to_string()),
        Value::Bool(payload.comment.enabled),
    );
    comment_mapping.insert(
        Value::String("comments_per_session".to_string()),
        serde_yaml::to_value(payload.comment.comments_per_session)
            .map_err(|err| format!("failed to serialize comments_per_session: {}", err))?,
    );
    comment_mapping.insert(
        Value::String("min_video_comments".to_string()),
        serde_yaml::to_value(payload.comment.min_video_comments)
            .map_err(|err| format!("failed to serialize min_video_comments: {}", err))?,
    );
    comment_mapping.insert(
        Value::String("probability".to_string()),
        serde_yaml::to_value(payload.comment.probability)
            .map_err(|err| format!("failed to serialize comment probability: {}", err))?,
    );

    daily_actions_mapping.insert(
        Value::String("comment".to_string()),
        Value::Mapping(comment_mapping),
    );
    Ok(daily_actions_mapping)
}

fn ai_comment_payload_to_yaml_value(payload: &AiCommentSettingsPayload) -> Result<Value, String> {
    let provider = normalize_ai_comment_provider(Some(&payload.provider))?;
    let mut mapping = Mapping::new();
    mapping.insert(
        Value::String("enabled".to_string()),
        Value::Bool(payload.enabled),
    );
    mapping.insert(
        Value::String("provider".to_string()),
        Value::String(provider),
    );
    mapping.insert(
        Value::String("base_url".to_string()),
        Value::String(payload.base_url.trim().trim_end_matches('/').to_string()),
    );
    mapping.insert(
        Value::String("model".to_string()),
        Value::String(payload.model.trim().to_string()),
    );
    mapping.insert(
        Value::String("timeout_seconds".to_string()),
        serde_yaml::to_value(payload.timeout_seconds)
            .map_err(|err| format!("failed to serialize timeout_seconds: {}", err))?,
    );
    mapping.insert(
        Value::String("max_comment_length".to_string()),
        serde_yaml::to_value(payload.max_comment_length)
            .map_err(|err| format!("failed to serialize max_comment_length: {}", err))?,
    );
    mapping.insert(
        Value::String("fallback_to_pool".to_string()),
        Value::Bool(payload.fallback_to_pool.unwrap_or(true)),
    );
    mapping.insert(
        Value::String("language".to_string()),
        Value::String(payload.language.trim().to_string()),
    );
    mapping.insert(
        Value::String("blocked_words".to_string()),
        serde_yaml::to_value(normalize_plain_string_list(&payload.blocked_words))
            .map_err(|err| format!("failed to serialize blocked_words: {}", err))?,
    );
    Ok(Value::Mapping(mapping))
}

fn target_payload_to_yaml_mapping(payload: &TargetEngagementPayload) -> Result<Mapping, String> {
    let mut target_mapping = Mapping::new();
    target_mapping.insert(
        Value::String("enabled".to_string()),
        Value::Bool(payload.enabled),
    );
    target_mapping.insert(
        Value::String("handles".to_string()),
        serde_yaml::to_value(normalize_string_list(&payload.handles))
            .map_err(|err| format!("failed to serialize target handles: {}", err))?,
    );
    target_mapping.insert(
        Value::String("participants".to_string()),
        serde_yaml::to_value(normalize_string_list(&payload.participants))
            .map_err(|err| format!("failed to serialize target participants: {}", err))?,
    );
    target_mapping.insert(
        Value::String("first_run_latest_n".to_string()),
        serde_yaml::to_value(payload.first_run_latest_n)
            .map_err(|err| format!("failed to serialize first_run_latest_n: {}", err))?,
    );
    target_mapping.insert(
        Value::String("max_videos_per_run".to_string()),
        serde_yaml::to_value(payload.max_videos_per_run)
            .map_err(|err| format!("failed to serialize max_videos_per_run: {}", err))?,
    );
    target_mapping.insert(
        Value::String("like_probability".to_string()),
        serde_yaml::to_value(payload.like_probability)
            .map_err(|err| format!("failed to serialize like_probability: {}", err))?,
    );
    target_mapping.insert(
        Value::String("comment_probability".to_string()),
        serde_yaml::to_value(payload.comment_probability)
            .map_err(|err| format!("failed to serialize comment_probability: {}", err))?,
    );
    target_mapping.insert(
        Value::String("comments_file".to_string()),
        Value::String(payload.comments_file.trim().to_string()),
    );
    target_mapping.insert(
        Value::String("follow".to_string()),
        Value::Bool(payload.follow),
    );
    target_mapping.insert(
        Value::String("follow_probability".to_string()),
        serde_yaml::to_value(payload.follow_probability)
            .map_err(|err| format!("failed to serialize follow_probability: {}", err))?,
    );
    Ok(target_mapping)
}

fn notify_payload_to_yaml_value(payload: &NotifySettingsPayload) -> Result<Value, String> {
    let mut mapping = Mapping::new();
    mapping.insert(
        Value::String("enabled".to_string()),
        Value::Bool(payload.enabled),
    );
    mapping.insert(
        Value::String("type".to_string()),
        Value::String(payload.notify_type.trim().to_string()),
    );

    let mut serverchan = Mapping::new();
    if let Some(sendkey) = payload
        .serverchan
        .as_ref()
        .and_then(|serverchan| blank_to_none(serverchan.sendkey.as_deref()))
    {
        serverchan.insert(Value::String("sendkey".to_string()), Value::String(sendkey));
    }
    mapping.insert(
        Value::String("serverchan".to_string()),
        Value::Mapping(serverchan),
    );

    let mut bark = Mapping::new();
    if let Some(url) = payload
        .bark
        .as_ref()
        .and_then(|bark| blank_to_none(bark.url.as_deref()))
    {
        bark.insert(Value::String("url".to_string()), Value::String(url));
    }
    mapping.insert(Value::String("bark".to_string()), Value::Mapping(bark));

    let mut webhook = Mapping::new();
    if let Some(url) = payload
        .webhook
        .as_ref()
        .and_then(|webhook| blank_to_none(webhook.url.as_deref()))
    {
        webhook.insert(Value::String("url".to_string()), Value::String(url));
    }
    mapping.insert(
        Value::String("webhook".to_string()),
        Value::Mapping(webhook),
    );

    Ok(Value::Mapping(mapping))
}

fn format_validation_errors(validation: &ValidationResult) -> String {
    let details = validation
        .errors
        .iter()
        .map(|issue| format!("{}: {}", issue.path, issue.message))
        .collect::<Vec<_>>()
        .join("; ");
    format!("config validation failed: {}", details)
}

fn validate_ai_comment_settings_payload(payload: &AiCommentSettingsPayload) -> Result<(), String> {
    validate_ai_comment_provider(&payload.provider)?;
    validate_ai_comment_base_url(&payload.base_url)?;
    if payload.model.trim().is_empty() {
        return Err("ai_comment.model must not be empty".to_string());
    }
    if payload.timeout_seconds <= 0 {
        return Err("ai_comment.timeout_seconds must be greater than 0".to_string());
    }
    if payload.max_comment_length <= 0 {
        return Err("ai_comment.max_comment_length must be greater than 0".to_string());
    }
    if payload.language.trim().is_empty() {
        return Err("ai_comment.language must not be empty".to_string());
    }
    Ok(())
}

fn validate_ai_comment_provider(provider: &str) -> Result<(), String> {
    let value = provider.trim();
    if value.is_empty() {
        return Err("ai_comment.provider must not be empty".to_string());
    }
    if value
        .chars()
        .all(|ch| ch.is_ascii_lowercase() || ch.is_ascii_digit() || ch == '_')
    {
        Ok(())
    } else {
        Err("ai_comment.provider must use lowercase letters, digits, and underscores".to_string())
    }
}

fn validate_ai_comment_base_url(base_url: &str) -> Result<(), String> {
    let value = base_url.trim();
    if value.is_empty() {
        return Err("ai_comment.base_url must not be empty".to_string());
    }
    if value.contains(char::is_whitespace) {
        return Err("ai_comment.base_url must not contain whitespace".to_string());
    }
    if !(value.starts_with("https://") || value.starts_with("http://")) {
        return Err("ai_comment.base_url must start with http:// or https://".to_string());
    }
    Ok(())
}

fn normalize_ai_comment_provider(provider: Option<&str>) -> Result<String, String> {
    let value = blank_to_none(provider).unwrap_or_else(|| DEFAULT_AI_COMMENT_PROVIDER.to_string());
    validate_ai_comment_provider(&value)?;
    Ok(value)
}

pub fn normalized_platform_filter(value: Option<&str>) -> Result<Option<String>, String> {
    let Some(value) = blank_to_none(value) else {
        return Ok(None);
    };
    if value == "all" {
        return Ok(None);
    }
    normalize_platform(&value, "platform").map(Some)
}

pub fn normalize_platform(value: &str, field: &str) -> Result<String, String> {
    let platform = value.trim();
    if is_valid_platform(platform) {
        Ok(platform.to_string())
    } else {
        Err(format!("{} has unsupported platform '{}'", field, platform))
    }
}

pub fn ensure_platform_capability(platform: &str, capability: &str) -> Result<(), String> {
    let platform = normalize_platform(platform, "platform")?;
    let status = platform_capability_status(&platform, capability).ok_or_else(|| {
        format!(
            "unsupported capability '{}' for platform '{}'",
            capability, platform
        )
    })?;
    if status == "supported" {
        Ok(())
    } else {
        Err(format!(
            "platform '{}' capability '{}' is '{}'",
            platform, capability, status
        ))
    }
}

pub fn ensure_account_ids_belong_to_platform(
    platform: &str,
    account_ids: &[String],
) -> Result<(), String> {
    let platform = normalize_platform(platform, "platform")?;
    let config = load_config()?;
    for account_id in account_ids {
        let account_id = account_id.trim();
        let account = config
            .accounts()
            .iter()
            .find(|account| account.id() == account_id)
            .ok_or_else(|| format!("account '{}' does not exist in config", account_id))?;
        if account.platform() != platform {
            return Err(format!(
                "account '{}' belongs to platform '{}' but request.platform is '{}'",
                account_id,
                account.platform(),
                platform
            ));
        }
    }
    Ok(())
}

fn platform_section<'a>(config: &'a Value, platform: &str, section: &str) -> Option<&'a Value> {
    config
        .get("platforms")
        .and_then(|platforms| platforms.get(platform))
        .and_then(|platform_config| platform_config.get(section))
}

fn existing_platform_section_mapping(config: &Value, platform: &str, section: &str) -> Mapping {
    platform_section(config, platform, section)
        .and_then(Value::as_mapping)
        .cloned()
        .unwrap_or_default()
}

fn ensure_child_mapping<'a>(
    mapping: &'a mut Mapping,
    key_name: &str,
    path: &str,
) -> Result<&'a mut Mapping, String> {
    let key = Value::String(key_name.to_string());
    if !mapping.contains_key(&key) {
        mapping.insert(key.clone(), Value::Mapping(Mapping::new()));
    }
    match mapping.get_mut(&key) {
        Some(Value::Mapping(child)) => Ok(child),
        Some(_) => Err(format!("{} must be a mapping", path)),
        None => Err(format!("failed to access {}", path)),
    }
}

fn platform_mapping<'a>(
    config_value: &'a mut Value,
    platform: &str,
) -> Result<&'a mut Mapping, String> {
    let Value::Mapping(root) = config_value else {
        return Err("accounts.yaml root must be a mapping".to_string());
    };
    let platforms = ensure_child_mapping(root, "platforms", "platforms")?;
    ensure_child_mapping(platforms, platform, &format!("platforms.{}", platform))
}

fn set_platform_section(
    config_value: &mut Value,
    platform: &str,
    section: &str,
    mapping: Mapping,
) -> Result<(), String> {
    let platform = platform_mapping(config_value, platform)?;
    platform.insert(Value::String(section.to_string()), Value::Mapping(mapping));
    Ok(())
}

fn map_action_status(status: &str) -> String {
    match status {
        "ok" => "ok".to_string(),
        "error" | "fail" | "failed" => "error".to_string(),
        "skip" => "skip".to_string(),
        _ => "unknown".to_string(),
    }
}

fn resolve_tiktok_platform(config: &ConfigYaml) -> Option<&PlatformYaml> {
    config
        .platforms
        .as_ref()
        .and_then(|platforms| platforms.get("tiktok"))
}

fn resolve_tiktok_warmup(config: &ConfigYaml) -> Option<&DailyActionsYaml> {
    resolve_tiktok_platform(config)
        .and_then(|platform| platform.warmup.as_ref())
        .or_else(|| {
            config
                .defaults
                .as_ref()
                .and_then(|defaults| defaults.daily_actions.as_ref())
        })
}

fn resolve_tiktok_target_engagement(config: &ConfigYaml) -> Option<&TargetAccountsYaml> {
    resolve_tiktok_platform(config)
        .and_then(|platform| platform.target_engagement.as_ref())
        .or(config.target_accounts.as_ref())
}

fn resolve_tiktok_scheduler(config: &ConfigYaml) -> Option<&SchedulerYaml> {
    resolve_tiktok_platform(config)
        .and_then(|platform| platform.scheduler.as_ref())
        .or(config.scheduler.as_ref())
}

fn map_fyp_settings(daily: Option<&DailyActionsYaml>) -> Option<FypSettings> {
    let daily = daily?;
    let comment = daily.comment.as_ref();

    Some(FypSettings {
        fyp_browse_minutes: daily.fyp_browse_minutes.unwrap_or([0.0, 0.0]),
        like_probability: daily.like_probability.unwrap_or(0.0),
        follows_per_session: daily.follows_per_session.unwrap_or([0, 0]),
        comment: FypCommentSettings {
            enabled: comment.and_then(|comment| comment.enabled).unwrap_or(false),
            comments_per_session: comment
                .and_then(|comment| comment.comments_per_session)
                .unwrap_or([0, 0]),
            min_video_comments: comment
                .and_then(|comment| comment.min_video_comments)
                .unwrap_or(0),
            probability: comment
                .and_then(|comment| comment.probability)
                .unwrap_or(0.0),
        },
    })
}

fn map_ai_comment_settings(ai_comment: Option<&AiCommentYaml>) -> AiCommentSettings {
    AiCommentSettings {
        enabled: ai_comment
            .and_then(|ai_comment| ai_comment.enabled)
            .unwrap_or(false),
        provider: ai_comment
            .and_then(|ai_comment| blank_to_none(ai_comment.provider.as_deref()))
            .unwrap_or_else(|| DEFAULT_AI_COMMENT_PROVIDER.to_string()),
        base_url: ai_comment
            .and_then(|ai_comment| blank_to_none(ai_comment.base_url.as_deref()))
            .unwrap_or_else(|| DEFAULT_AI_COMMENT_BASE_URL.to_string()),
        model: ai_comment
            .and_then(|ai_comment| blank_to_none(ai_comment.model.as_deref()))
            .unwrap_or_else(|| DEFAULT_AI_COMMENT_MODEL.to_string()),
        timeout_seconds: ai_comment
            .and_then(|ai_comment| ai_comment.timeout_seconds)
            .unwrap_or(DEFAULT_AI_COMMENT_TIMEOUT_SECONDS),
        max_comment_length: ai_comment
            .and_then(|ai_comment| ai_comment.max_comment_length)
            .unwrap_or(DEFAULT_AI_COMMENT_MAX_LENGTH),
        fallback_to_pool: ai_comment
            .and_then(|ai_comment| ai_comment.fallback_to_pool)
            .unwrap_or(true),
        language: ai_comment
            .and_then(|ai_comment| blank_to_none(ai_comment.language.as_deref()))
            .unwrap_or_else(|| DEFAULT_AI_COMMENT_LANGUAGE.to_string()),
        blocked_words: ai_comment
            .and_then(|ai_comment| ai_comment.blocked_words.as_ref())
            .map(|words| normalize_plain_string_list(words))
            .unwrap_or_default(),
    }
}

fn map_target_engagement(target: Option<&TargetAccountsYaml>) -> Option<TargetEngagementSettings> {
    let target = target?;
    Some(TargetEngagementSettings {
        enabled: target.enabled.unwrap_or(false),
        handles: target.handles.clone().unwrap_or_default(),
        participants: target.participants.clone().unwrap_or_default(),
        first_run_latest_n: target.first_run_latest_n.unwrap_or(0),
        max_videos_per_run: target.max_videos_per_run.unwrap_or(0),
        like_probability: target.like_probability.unwrap_or(0.0),
        comment_probability: target.comment_probability.unwrap_or(0.0),
        comments_file: target.comments_file.clone().unwrap_or_default(),
        follow: target.follow.unwrap_or(false),
        follow_probability: target.follow_probability.unwrap_or(0.0),
    })
}

fn map_scheduler_settings(scheduler: Option<&SchedulerYaml>) -> SchedulerSettings {
    SchedulerSettings {
        fires_per_day: scheduler
            .and_then(|scheduler| scheduler.fires_per_day)
            .unwrap_or(3),
    }
}

fn map_notify(notify: Option<&NotifyYaml>) -> Option<NotifySettings> {
    let notify = notify?;
    Some(NotifySettings {
        enabled: notify.enabled.unwrap_or(false),
        notify_type: notify
            .notify_type
            .clone()
            .unwrap_or_else(|| "serverchan".to_string()),
        serverchan: notify
            .serverchan
            .as_ref()
            .map(|serverchan| ServerChanSettings {
                sendkey: blank_to_none(serverchan.sendkey.as_deref()),
            }),
        bark: notify.bark.as_ref().map(|bark| UrlHolderSettings {
            url: blank_to_none(bark.url.as_deref()),
        }),
        webhook: notify.webhook.as_ref().map(|webhook| UrlHolderSettings {
            url: blank_to_none(webhook.url.as_deref()),
        }),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn minimal_yaml(accounts: &str) -> String {
        format!(
            r#"bitbrowser:
  api_url: http://127.0.0.1:54345
scheduler:
  fires_per_day: 3
defaults:
  daily_actions:
    fyp_browse_minutes: [1, 2]
    like_probability: 0.5
    follows_per_session: [0, 1]
    comment:
      enabled: true
      comments_per_session: [0, 1]
      min_video_comments: 10
      probability: 0.2
target_accounts:
  enabled: true
  handles: [brand_one]
  participants: [acct_1]
  first_run_latest_n: 3
  max_videos_per_run: 2
  like_probability: 0.3
  comment_probability: 0.4
  comments_file: config/comments_brand.txt
  follow: true
  follow_probability: 0.1
accounts:
{}
"#,
            accounts
        )
    }

    fn valid_account_yaml() -> &'static str {
        "  - id: acct_1\n    platform: tiktok\n    enabled: true\n    ip_group: 1\n    active_hours: [[9, 12]]\n    bitbrowser_profile_id: profile_1\n"
    }

    fn legacy_account_yaml() -> &'static str {
        "  - id: acct_1\n    enabled: true\n    ip_group: 1\n    active_hours: [[9, 12]]\n    bitbrowser_profile_id: profile_1\n"
    }

    fn test_paths() -> ProjectPaths {
        ProjectPaths {
            runtime_mode: "source".to_string(),
            project_root: "root".to_string(),
            config_path: "config/accounts.yaml".to_string(),
            comments_path: "config/comments.txt".to_string(),
            brand_comments_path: "config/comments_brand.txt".to_string(),
            data_dir: "data".to_string(),
            logs_dir: "data".to_string(),
            actions_db_path: "data/missing-actions.db".to_string(),
            sessions_log_path: "data/sessions.log".to_string(),
            lock_file_path: "data/run.lock".to_string(),
            src_dir: "src".to_string(),
            settings_path: "desktop/local-settings.json".to_string(),
            runtime_path: "desktop/src-tauri/resources/runtime/account-matrix-runtime.exe"
                .to_string(),
            runtime_manifest_path: "desktop/src-tauri/resources/runtime/runtime-manifest.json"
                .to_string(),
            runtime_version: None,
            python_executable: "py".to_string(),
            default_browser_provider: "bitbrowser".to_string(),
            chromium_executable: String::new(),
            bitbrowser_api_url: "http://127.0.0.1:54345".to_string(),
            auto_close_profile: true,
            log_poll_interval_seconds: 3,
        }
    }

    fn issue_paths(validation: &ValidationResult) -> Vec<String> {
        validation
            .errors
            .iter()
            .map(|issue| issue.path.clone())
            .collect()
    }

    #[test]
    fn yaml_snapshot_reads_valid_accounts() {
        let raw_yaml = minimal_yaml(valid_account_yaml());
        let paths = test_paths();

        let snapshot = config_snapshot(paths, raw_yaml).expect("valid yaml should load");

        assert!(snapshot.validation.valid);
        assert_eq!(snapshot.accounts.len(), 1);
        assert_eq!(snapshot.accounts[0].id(), "acct_1");
        assert_eq!(
            snapshot.bitbrowser_api_url().as_deref(),
            Some("http://127.0.0.1:54345")
        );
    }

    #[test]
    fn legacy_config_snapshot_defaults_missing_account_platform_to_tiktok() {
        let raw_yaml = minimal_yaml(legacy_account_yaml());

        let snapshot = config_snapshot(test_paths(), raw_yaml).expect("legacy yaml should load");

        assert!(snapshot.validation.valid);
        assert_eq!(snapshot.accounts[0].platform(), "tiktok");
        assert!(!snapshot.accounts[0].login.enabled);
        assert_eq!(
            snapshot
                .fyp_settings
                .as_ref()
                .expect("legacy daily_actions should map to fyp settings")
                .like_probability,
            0.5
        );
        assert_eq!(
            snapshot
                .target_engagement
                .as_ref()
                .expect("legacy target_accounts should map to target settings")
                .handles,
            vec!["brand_one".to_string()]
        );
    }

    #[test]
    fn config_migration_preview_and_apply_backfills_tiktok_sections() {
        let raw_yaml = minimal_yaml(legacy_account_yaml());
        let paths = test_paths();
        let mut config_value: Value =
            serde_yaml::from_str(&raw_yaml).expect("test yaml should parse");

        let preview = build_migration_preview(&config_value, &paths).expect("preview should build");
        let pending = preview
            .operations
            .iter()
            .filter(|operation| operation.pending)
            .map(|operation| operation.key.as_str())
            .collect::<Vec<_>>();

        assert!(preview.required);
        assert!(pending.contains(&"accounts_platform"));
        assert!(pending.contains(&"schema_version"));
        assert!(pending.contains(&"tiktok_warmup"));
        assert!(pending.contains(&"tiktok_target_engagement"));
        assert!(pending.contains(&"tiktok_comments"));

        apply_config_value_migration(&mut config_value, &paths)
            .expect("config value migration should apply");

        assert!(!accounts_missing_platform(&config_value));
        assert_eq!(
            config_value["schema_version"].as_i64(),
            Some(CONFIG_SCHEMA_VERSION)
        );
        assert_eq!(
            config_value["accounts"][0]["platform"].as_str(),
            Some("tiktok")
        );
        assert!(platform_section(&config_value, "tiktok", "warmup").is_some());
        assert!(platform_section(&config_value, "tiktok", "target_engagement").is_some());
        assert_eq!(
            platform_section(&config_value, "tiktok", "comments")
                .and_then(|comments| comments.get("general_file"))
                .and_then(Value::as_str),
            Some("comments.txt")
        );

        let next_yaml =
            serde_yaml::to_string(&config_value).expect("migrated yaml should serialize");
        assert!(validate_raw_yaml(&next_yaml).valid);
    }

    #[test]
    fn validation_reports_config_field_paths() {
        let raw_yaml = minimal_yaml(
            "  - id: acct_1\n    platform: tiktok\n    enabled: true\n    ip_group: 1\n    active_hours: [[9, 12]]\n    bitbrowser_profile_id: profile_1\n  - id: acct_1\n    platform: tiktok\n    enabled: true\n    ip_group: 1\n    active_hours: [[11, 13]]\n    bitbrowser_profile_id: profile_1\n",
        );

        let validation = validate_raw_yaml(&raw_yaml);
        let paths = issue_paths(&validation);

        assert!(!validation.valid);
        assert!(paths.contains(&"accounts[1].id".to_string()));
        assert!(paths.contains(&"accounts[1].bitbrowser_profile_id".to_string()));
        assert!(paths.contains(&"accounts.ip_group[1].active_hours".to_string()));
    }

    #[test]
    fn validation_rejects_invalid_target_and_probability_values() {
        let raw_yaml = minimal_yaml(valid_account_yaml())
            .replace("participants: [acct_1]", "participants: [missing_acct]")
            .replace("like_probability: 0.5", "like_probability: 1.4");

        let validation = validate_raw_yaml(&raw_yaml);
        let paths = issue_paths(&validation);

        assert!(!validation.valid);
        assert!(paths.contains(&"target_accounts.participants[0]".to_string()));
        assert!(paths.contains(&"defaults.daily_actions.like_probability".to_string()));
    }

    #[test]
    fn validation_rejects_invalid_account_platform() {
        let raw_yaml =
            minimal_yaml(valid_account_yaml()).replace("platform: tiktok", "platform: unknown");

        let validation = validate_raw_yaml(&raw_yaml);
        let paths = issue_paths(&validation);

        assert!(!validation.valid);
        assert!(paths.contains(&"accounts[0].platform".to_string()));
    }

    #[test]
    fn validation_rejects_enabled_login_without_required_fields() {
        let raw_yaml = minimal_yaml(
            "  - id: acct_1\n    platform: tiktok\n    enabled: true\n    ip_group: 1\n    active_hours: [[9, 12]]\n    bitbrowser_profile_id: profile_1\n    login:\n      enabled: true\n      method: password\n",
        );

        let validation = validate_raw_yaml(&raw_yaml);
        let paths = issue_paths(&validation);

        assert!(!validation.valid);
        assert!(paths.contains(&"accounts[0].login.username".to_string()));
        assert!(paths.contains(&"accounts[0].login.credential_ref".to_string()));
    }

    #[test]
    fn validation_rejects_plaintext_login_password_fields() {
        let raw_yaml = minimal_yaml(
            "  - id: acct_1\n    platform: tiktok\n    enabled: true\n    ip_group: 1\n    active_hours: [[9, 12]]\n    bitbrowser_profile_id: profile_1\n    login:\n      enabled: false\n      method: password\n      username: user@example.com\n      password: open-sesame\n",
        );

        let validation = validate_raw_yaml(&raw_yaml);
        let paths = issue_paths(&validation);

        assert!(!validation.valid);
        assert!(paths.contains(&"accounts[0].login.password".to_string()));
    }

    #[test]
    fn backend_platform_capability_validation_rejects_reserved_execution() {
        assert!(ensure_platform_capability("tiktok", "warmupTask").is_ok());
        assert!(ensure_platform_capability("instagram", "accountManagement").is_ok());

        let reserved = ensure_platform_capability("instagram", "warmupTask")
            .expect_err("instagram warmup should be reserved");
        assert!(reserved.contains("platform 'instagram' capability 'warmupTask' is 'reserved'"));

        let invalid = ensure_platform_capability("unknown", "warmupTask")
            .expect_err("unknown platform should fail");
        assert!(invalid.contains("unsupported platform"));
    }

    #[test]
    fn account_platform_validation_defaults_legacy_accounts_and_rejects_invalid_values() {
        let legacy_account: Value =
            serde_yaml::from_str("id: acct_1\nenabled: true\nactive_hours: [[9, 12]]\n")
                .expect("legacy account value should parse");
        assert_eq!(yaml_account_platform(&legacy_account), "tiktok");

        let invalid = normalize_platform("unknown", "accounts.platform")
            .expect_err("invalid account platform should fail");
        assert!(invalid.contains("unsupported platform"));
    }

    #[test]
    fn active_hours_touching_edges_do_not_overlap() {
        assert!(ranges_overlap([9.0, 12.0], [11.5, 13.0]));
        assert!(!ranges_overlap([9.0, 12.0], [12.0, 14.0]));
    }

    #[test]
    fn account_payload_serializes_to_yaml_mapping() {
        let value = account_input_to_yaml_value(&AccountInput {
            id: " acct_2 ".to_string(),
            platform: "tiktok".to_string(),
            enabled: true,
            scheduled: Some(false),
            ip_group: Some(2),
            active_hours: vec![[19.0, 23.0]],
            browser_provider: None,
            browser: None,
            login: None,
            bitbrowser_profile_id: Some(" profile_2 ".to_string()),
            notes: Some(" evening ".to_string()),
        })
        .expect("account payload should serialize");
        let account: AccountYaml =
            serde_yaml::from_value(value).expect("serialized account should deserialize");

        assert_eq!(account.id, "acct_2");
        assert_eq!(account.scheduled, Some(false));
        assert_eq!(account.bitbrowser_profile_id.as_deref(), Some("profile_2"));
        assert_eq!(account.active_hours.unwrap(), vec![[19.0, 23.0]]);
    }

    #[test]
    fn account_payload_serializes_login_metadata_without_plaintext_password() {
        let value = account_input_to_yaml_value(&AccountInput {
            id: "acct_2".to_string(),
            platform: "tiktok".to_string(),
            enabled: true,
            scheduled: Some(true),
            ip_group: Some(2),
            active_hours: vec![[19.0, 23.0]],
            browser_provider: None,
            browser: None,
            login: Some(AccountLoginInput {
                enabled: true,
                method: Some("password".to_string()),
                username: Some(" user@example.com ".to_string()),
                credential_ref: Some(" account-login/acct_2 ".to_string()),
            }),
            bitbrowser_profile_id: Some("profile_2".to_string()),
            notes: None,
        })
        .expect("account payload should serialize");
        let yaml = serde_yaml::to_string(&value).expect("yaml should serialize");

        assert!(yaml.contains("credential_ref: account-login/acct_2"));
        assert!(yaml.contains("username: user@example.com"));
        assert!(!yaml.contains("open-sesame"));
    }
}

fn yaml_account_platform(account: &Value) -> String {
    let account_mapping = account.as_mapping();
    let platform = account_mapping
        .and_then(|mapping| mapping.get(&Value::String("platform".to_string())))
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty());
    if let Some(platform) = platform {
        return platform.to_string();
    }

    account_mapping
        .and_then(|mapping| mapping.get(&Value::String("id".to_string())))
        .and_then(Value::as_str)
        .map(|_| "tiktok".to_string())
        .unwrap_or_else(|| "tiktok".to_string())
}

fn account_browser_provider(account: &AccountYaml, default_provider: &str) -> String {
    account_browser_provider_result(account, default_provider)
        .unwrap_or_else(|_| default_provider.to_string())
}

fn config_default_browser_provider(config: &ConfigYaml) -> String {
    config
        .browser
        .as_ref()
        .and_then(|browser| browser.default_provider.as_deref())
        .and_then(|provider| normalize_browser_provider(provider, "browser.default_provider").ok())
        .unwrap_or_else(|| DEFAULT_BROWSER_PROVIDER.to_string())
}

fn account_browser_provider_result(
    account: &AccountYaml,
    default_provider: &str,
) -> Result<String, String> {
    let provider = account
        .browser_provider
        .as_deref()
        .or_else(|| {
            account
                .browser
                .as_ref()
                .and_then(|browser| browser.provider.as_deref())
        })
        .unwrap_or(default_provider);
    normalize_browser_provider(provider, "browser_provider")
}

fn account_browser_profile_id(account: &AccountYaml) -> Option<String> {
    account
        .browser
        .as_ref()
        .and_then(|browser| blank_to_none(browser.profile_id.as_deref()))
        .or_else(|| {
            account
                .browser
                .as_ref()
                .and_then(|browser| browser.bitbrowser.as_ref())
                .and_then(|bitbrowser| blank_to_none(bitbrowser.profile_id.as_deref()))
        })
        .or_else(|| blank_to_none(account.bitbrowser_profile_id.as_deref()))
}

fn account_browser_proxy_type(account: &AccountYaml) -> Option<String> {
    account
        .browser
        .as_ref()
        .and_then(|browser| blank_to_none(browser.proxy_type.as_deref()))
        .map(|value| value.to_ascii_lowercase())
}

fn account_browser_proxy(account: &AccountYaml) -> Option<String> {
    account
        .browser
        .as_ref()
        .and_then(|browser| blank_to_none(browser.proxy.as_deref()))
}

fn account_browser_user_data_dir(account: &AccountYaml) -> Option<String> {
    account
        .browser
        .as_ref()
        .and_then(|browser| blank_to_none(browser.user_data_dir.as_deref()))
}

fn account_login(account: &AccountYaml) -> AccountLogin {
    let login = account.login.as_ref();
    AccountLogin {
        enabled: login.and_then(|login| login.enabled).unwrap_or(false),
        method: login
            .and_then(|login| blank_to_none(login.method.as_deref()))
            .unwrap_or_else(|| DEFAULT_LOGIN_METHOD.to_string()),
        username: login.and_then(|login| blank_to_none(login.username.as_deref())),
        credential_ref: login.and_then(|login| blank_to_none(login.credential_ref.as_deref())),
    }
}

fn validate_builtin_proxy(proxy: &str) -> Result<(), String> {
    let value = proxy.trim();
    if value.contains("://") {
        let (scheme, rest) = value
            .split_once("://")
            .ok_or_else(|| "browser.proxy URL must include a scheme".to_string())?;
        if !matches!(
            scheme.to_ascii_lowercase().as_str(),
            "http" | "https" | "socks5"
        ) {
            return Err("browser.proxy scheme must be http, https, or socks5".to_string());
        }
        let (userinfo, host_port) = if let Some((userinfo, host_port)) = rest.rsplit_once('@') {
            (Some(userinfo), host_port)
        } else {
            (None, rest)
        };
        if let Some(userinfo) = userinfo {
            let (username, password) = userinfo.split_once(':').ok_or_else(|| {
                "browser.proxy URL credentials must be username:password".to_string()
            })?;
            if username.trim().is_empty() || password.trim().is_empty() {
                return Err("browser.proxy username and password must be non-empty".to_string());
            }
        }
        let (host, port) = host_port
            .rsplit_once(':')
            .ok_or_else(|| "browser.proxy URL must include host and port".to_string())?;
        if host.trim().is_empty() {
            return Err("browser.proxy host must be non-empty".to_string());
        }
        validate_builtin_proxy_port(port)?;
        return Ok(());
    }
    let parts = value.split(':').collect::<Vec<_>>();
    if !(parts.len() == 2 || parts.len() == 4) || parts.iter().any(|part| part.trim().is_empty()) {
        return Err("browser.proxy must be host:port or host:port:username:password".to_string());
    }
    validate_builtin_proxy_port(parts[1])?;
    Ok(())
}

fn validate_builtin_proxy_port(port: &str) -> Result<(), String> {
    let port = port
        .parse::<u16>()
        .map_err(|_| "browser.proxy port must be between 1 and 65535".to_string())?;
    if port == 0 {
        return Err("browser.proxy port must be between 1 and 65535".to_string());
    }
    Ok(())
}

fn normalize_browser_provider(provider: &str, path: &str) -> Result<String, String> {
    let normalized = provider.trim().to_ascii_lowercase();
    if matches!(normalized.as_str(), "bitbrowser" | "builtin_chromium") {
        Ok(normalized)
    } else {
        Err(format!("{} 必须是 bitbrowser 或 builtin_chromium", path))
    }
}

fn is_valid_platform(platform: &str) -> bool {
    matches!(platform, "tiktok" | "instagram" | "whatsapp" | "douyin")
}

fn platform_capability_status(platform: &str, capability: &str) -> Option<&'static str> {
    match (platform, capability) {
        ("tiktok", "accountManagement")
        | ("tiktok", "browserProfile")
        | ("tiktok", "warmupTask")
        | ("tiktok", "targetEngagement")
        | ("tiktok", "scheduler")
        | ("tiktok", "comments")
        | ("tiktok", "records")
        | ("tiktok", "stats")
        | ("tiktok", "gmailSetup")
        | ("tiktok", "diagnostics") => Some("supported"),

        ("instagram", "accountManagement")
        | ("instagram", "browserProfile")
        | ("instagram", "scheduler")
        | ("instagram", "comments")
        | ("instagram", "records")
        | ("instagram", "stats")
        | ("instagram", "diagnostics")
        | ("whatsapp", "accountManagement")
        | ("whatsapp", "browserProfile")
        | ("whatsapp", "scheduler")
        | ("whatsapp", "comments")
        | ("whatsapp", "records")
        | ("whatsapp", "stats")
        | ("whatsapp", "diagnostics")
        | ("douyin", "accountManagement")
        | ("douyin", "browserProfile")
        | ("douyin", "scheduler")
        | ("douyin", "comments")
        | ("douyin", "records")
        | ("douyin", "stats")
        | ("douyin", "diagnostics") => Some("supported"),

        ("instagram", "warmupTask")
        | ("instagram", "targetEngagement")
        | ("instagram", "gmailSetup")
        | ("whatsapp", "warmupTask")
        | ("douyin", "warmupTask")
        | ("douyin", "targetEngagement")
        | ("douyin", "gmailSetup") => Some("reserved"),

        ("whatsapp", "targetEngagement") | ("whatsapp", "gmailSetup") => Some("not_supported"),

        _ => None,
    }
}

fn blank_to_none(value: Option<&str>) -> Option<String> {
    value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToString::to_string)
}

fn normalize_string_list(values: &[String]) -> Vec<String> {
    values
        .iter()
        .map(|value| value.trim().trim_start_matches('@').to_string())
        .filter(|value| !value.is_empty())
        .collect()
}

fn normalize_plain_string_list(values: &[String]) -> Vec<String> {
    values
        .iter()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .collect()
}

fn issue(path: impl Into<String>, message: impl Into<String>) -> ValidationIssue {
    ValidationIssue {
        path: path.into(),
        message: message.into(),
    }
}
