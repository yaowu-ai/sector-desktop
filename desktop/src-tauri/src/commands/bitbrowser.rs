use chrono::Local;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value as JsonValue};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Duration;

use crate::commands::config::{append_accounts_to_config, load_config, AccountInput, SaveResult};
use crate::paths::{
    effective_chromium_executable, load_local_app_settings, normalize, project_paths,
    save_local_app_settings,
};

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ApiStatus {
    available: bool,
    api_url: String,
    checked_at: String,
    error: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct BrowserProviderCapability {
    provider: String,
    label: String,
    implemented: bool,
    production_ready: bool,
    can_launch: bool,
    can_close: bool,
    provides_cdp_endpoint: bool,
    requires_profile_id: bool,
    supports_tiktok: bool,
    risk_level: String,
    notes: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountBrowserDiagnosis {
    account_id: String,
    provider: String,
    status: String,
    checks: Vec<ProviderDiagnosticCheck>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProviderDiagnosticCheck {
    name: String,
    status: String,
    detail: String,
}

impl ApiStatus {
    pub fn available(&self) -> bool {
        self.available
    }

    pub fn api_url(&self) -> &str {
        &self.api_url
    }

    pub fn error(&self) -> Option<&str> {
        self.error.as_deref()
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BrowserProfile {
    id: String,
    name: String,
    platform: Option<String>,
    proxy: Option<String>,
    group_id: Option<String>,
    opened: bool,
    bound_account_id: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfileStatus {
    profile_id: String,
    opened: bool,
    pid: Option<String>,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfileOperationResult {
    profile_id: String,
    opened: bool,
    cdp_endpoint: Option<String>,
    message: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CdpResolveRequest {
    cdp_endpoint: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BuiltinChromiumStatus {
    available: bool,
    executable_path: Option<String>,
    data_root: String,
    checked_at: String,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BuiltinChromiumCleanupResult {
    account_id: String,
    user_data_dir: String,
    removed: bool,
    message: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BrowserPreviewFrame {
    data_url: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProxyCheckRequest {
    proxy_type: String,
    proxy: String,
    check_exists: Option<bool>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ParsedProxy {
    host: String,
    port: u16,
    username: String,
    masked: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProxyCheckResult {
    valid: bool,
    used: bool,
    message: String,
    proxy: Option<ParsedProxy>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateProfileRequest {
    name: String,
    proxy_type: String,
    proxy: String,
    group_id: Option<String>,
    skip_proxy_check: Option<bool>,
    allow_used_proxy: Option<bool>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateProfileResult {
    name: String,
    profile_id: String,
    proxy: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BatchCreateProfileRequest {
    prefix: String,
    proxy_type: String,
    proxies_text: String,
    group_id: Option<String>,
    skip_proxy_check: Option<bool>,
    skip_used: Option<bool>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BatchCreateProfileResult {
    created: Vec<BatchCreatedProfile>,
    skipped: Vec<BatchProfileIssue>,
    failed: Vec<BatchProfileIssue>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BatchCreatedProfile {
    line_number: usize,
    name: String,
    profile_id: String,
    proxy: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BatchProfileIssue {
    line_number: usize,
    name: Option<String>,
    proxy: String,
    reason: String,
}

#[derive(Debug, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct SyncAccountsRequest {
    prefix: String,
    start: i64,
    end: i64,
    morning_start: i64,
    morning_end: i64,
    evening_start: i64,
    evening_end: i64,
    first_ip_group: i64,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct SyncPreview {
    accounts_to_add: Vec<AccountInput>,
    existing_accounts: Vec<String>,
    missing_profiles: Vec<String>,
    duplicate_profiles: Vec<String>,
    can_apply: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SyncApplyResult {
    preview: SyncPreview,
    save_result: SaveResult,
}

#[tauri::command]
pub fn check_bitbrowser_api() -> ApiStatus {
    let checked_at = Local::now().to_rfc3339();
    let api_url = bitbrowser_api_url();

    match socket_addr_from_url(&api_url).and_then(check_tcp) {
        Ok(()) => ApiStatus {
            available: true,
            api_url,
            checked_at,
            error: None,
        },
        Err(error) => ApiStatus {
            available: false,
            api_url,
            checked_at,
            error: Some(error),
        },
    }
}

#[tauri::command]
pub fn get_browser_provider_matrix() -> Vec<BrowserProviderCapability> {
    provider_capability_matrix()
}

#[tauri::command]
pub fn diagnose_account_browser(account_id: String) -> Result<AccountBrowserDiagnosis, String> {
    let snapshot = load_config()?;
    let account = snapshot
        .accounts()
        .iter()
        .find(|account| account.id() == account_id)
        .ok_or_else(|| format!("account '{}' does not exist", account_id))?;
    let provider = account.browser_provider().to_string();
    let mut checks = Vec::new();
    let capability = provider_capability(&provider).ok_or_else(|| {
        format!(
            "account '{}' uses unsupported browser provider '{}'",
            account.id(),
            provider
        )
    })?;

    checks.push(ProviderDiagnosticCheck {
        name: "providerCapability".to_string(),
        status: if capability.implemented {
            "ok"
        } else {
            "error"
        }
        .to_string(),
        detail: capability.notes.clone(),
    });

    if provider == "bitbrowser" {
        if let Some(profile_id) = account.bitbrowser_profile_id() {
            checks.push(ProviderDiagnosticCheck {
                name: "accountProfile".to_string(),
                status: "ok".to_string(),
                detail: profile_id.to_string(),
            });
            let api_status = check_bitbrowser_api();
            checks.push(ProviderDiagnosticCheck {
                name: "providerStatus".to_string(),
                status: if api_status.available() {
                    "ok"
                } else {
                    "error"
                }
                .to_string(),
                detail: api_status
                    .error()
                    .map(|error| format!("{}: {}", api_status.api_url(), error))
                    .unwrap_or_else(|| api_status.api_url().to_string()),
            });
            let profile_status = get_profile_status(profile_id.to_string());
            checks.push(ProviderDiagnosticCheck {
                name: "profileStatus".to_string(),
                status: if profile_status.error.is_none() {
                    "ok"
                } else {
                    "warning"
                }
                .to_string(),
                detail: profile_status
                    .error
                    .unwrap_or_else(|| format!("opened={}", profile_status.opened)),
            });
        } else {
            checks.push(ProviderDiagnosticCheck {
                name: "accountProfile".to_string(),
                status: "error".to_string(),
                detail: "BitBrowser provider requires bitbrowser_profile_id or browser.profile_id"
                    .to_string(),
            });
        }
    } else if provider == "builtin_chromium" {
        let status = builtin_chromium_status();
        checks.push(ProviderDiagnosticCheck {
            name: "chromiumExecutable".to_string(),
            status: if status.available { "ok" } else { "error" }.to_string(),
            detail: status
                .error
                .unwrap_or_else(|| status.executable_path.unwrap_or_default()),
        });
        if let Some(proxy) = account.browser_proxy() {
            match parse_builtin_proxy(account.browser_proxy_type(), proxy) {
                Ok(proxy_parts) => {
                    checks.push(ProviderDiagnosticCheck {
                        name: "proxyConfig".to_string(),
                        status: "ok".to_string(),
                        detail: format!(
                            "{}; passwordSet={}",
                            proxy_parts.masked(),
                            proxy_parts.has_password()
                        ),
                    });
                    checks.push(builtin_proxy_connectivity_detail(&proxy_parts));
                }
                Err(error) => checks.push(ProviderDiagnosticCheck {
                    name: "proxyConfig".to_string(),
                    status: "error".to_string(),
                    detail: format!("{}.browser.proxy: {}", account.id(), error),
                }),
            }
        } else {
            checks.push(ProviderDiagnosticCheck {
                name: "proxyConfig".to_string(),
                status: "ok".to_string(),
                detail: "not configured".to_string(),
            });
        }
        match builtin_user_data_dir(account.id(), account.browser_user_data_dir()) {
            Ok(path) => {
                let access = user_data_dir_access_detail(&path);
                checks.push(ProviderDiagnosticCheck {
                    name: "userDataDir".to_string(),
                    status: if access.readable && access.writable {
                        "ok"
                    } else {
                        "error"
                    }
                    .to_string(),
                    detail: access.detail,
                });
            }
            Err(error) => checks.push(ProviderDiagnosticCheck {
                name: "userDataDir".to_string(),
                status: "error".to_string(),
                detail: error,
            }),
        }
        match builtin_session_for_account(account.id()) {
            Ok(Some(session)) => {
                let pid = session_pid(&session)
                    .map(|pid| pid.to_string())
                    .unwrap_or_else(|| "unknown".to_string());
                let port = session_port(&session)
                    .map(|port| port.to_string())
                    .unwrap_or_else(|| "unknown".to_string());
                let cdp = session_cdp_endpoint(&session).unwrap_or("unknown");
                let runtime_path = builtin_runtime_path(account.id())
                    .map(|path| normalize(&path))
                    .unwrap_or_else(|_| "unknown".to_string());
                checks.push(ProviderDiagnosticCheck {
                    name: "runtimeRecord".to_string(),
                    status: "warning".to_string(),
                    detail: format!(
                        "path={}; existing builtin_chromium session pid={}; port={}; cdp={}",
                        runtime_path, pid, port, cdp
                    ),
                });
                checks.push(builtin_cdp_endpoint_detail(cdp));
            }
            Ok(None) => checks.push(ProviderDiagnosticCheck {
                name: "runtimeRecord".to_string(),
                status: "ok".to_string(),
                detail: builtin_runtime_path(account.id())
                    .map(|path| {
                        format!(
                            "path={}; absent; CDP will be created on launch",
                            normalize(&path)
                        )
                    })
                    .unwrap_or_else(|error| error),
            }),
            Err(error) => checks.push(ProviderDiagnosticCheck {
                name: "runtimeRecord".to_string(),
                status: "warning".to_string(),
                detail: error,
            }),
        }
    } else {
        checks.push(ProviderDiagnosticCheck {
            name: "providerStatus".to_string(),
            status: "error".to_string(),
            detail: "provider is reserved and not implemented".to_string(),
        });
    }

    let status = if checks.iter().any(|check| check.status == "error") {
        "error"
    } else if checks.iter().any(|check| check.status == "warning") {
        "warning"
    } else {
        "ok"
    };

    Ok(AccountBrowserDiagnosis {
        account_id: account.id().to_string(),
        provider,
        status: status.to_string(),
        checks,
    })
}

#[tauri::command]
pub fn get_builtin_chromium_status() -> BuiltinChromiumStatus {
    builtin_chromium_status()
}

pub fn auto_configure_chromium_executable() -> Result<String, String> {
    let executable = locate_chromium_executable()?;
    let normalized = normalize(&executable);
    let mut settings = load_local_app_settings().unwrap_or_default();
    if effective_chromium_executable(&settings).trim().is_empty() {
        settings.chromium_executable = Some(normalized.clone());
        save_local_app_settings(&settings)?;
    }
    Ok(normalized)
}

#[tauri::command]
pub fn cleanup_builtin_chromium_data(
    account_id: String,
) -> Result<BuiltinChromiumCleanupResult, String> {
    let snapshot = load_config()?;
    let account = snapshot
        .accounts()
        .iter()
        .find(|account| account.id() == account_id)
        .ok_or_else(|| format!("account '{}' does not exist", account_id))?;
    let user_data_dir = builtin_user_data_dir(account.id(), account.browser_user_data_dir())?;
    let session = builtin_session_for_account(account.id())?;
    let mut close_message = "no runtime record".to_string();
    if let Some(session) = session.as_ref() {
        if !session_matches_account(account.id(), session) {
            close_message =
                "runtime record did not match account; process left untouched".to_string();
        } else if let Some(pid) = session_pid(session) {
            if pid_alive(pid as u32) {
                terminate_pid(pid as u32);
                close_message = format!("terminated matching builtin_chromium process pid={}", pid);
            } else {
                close_message = format!("browser process already exited; pid={}", pid);
            }
        } else {
            close_message = "runtime record had no valid PID".to_string();
        }
    }
    if user_data_dir.exists() {
        fs::remove_dir_all(&user_data_dir)
            .map_err(|err| format!("failed to remove {}: {}", normalize(&user_data_dir), err))?;
    }
    for session_path in builtin_session_paths(account.id())? {
        if session_path.exists() {
            let _ = fs::remove_file(&session_path);
        }
    }
    Ok(BuiltinChromiumCleanupResult {
        account_id: account.id().to_string(),
        user_data_dir: normalize(&user_data_dir),
        removed: true,
        message: format!("builtin_chromium user data removed; {}", close_message),
    })
}

#[tauri::command]
pub fn list_browser_profiles() -> Result<Vec<BrowserProfile>, String> {
    let api_url = bitbrowser_api_url();
    let raw_profiles = list_raw_profiles(&api_url, None)?;
    let ids = raw_profiles
        .iter()
        .filter_map(profile_id_from_raw)
        .collect::<Vec<_>>();
    let opened_by_id = profile_pids(&api_url, &ids).unwrap_or_default();
    let bindings = profile_account_bindings();

    Ok(raw_profiles
        .iter()
        .filter_map(|profile| map_browser_profile(profile, &opened_by_id, &bindings))
        .collect())
}

#[tauri::command]
pub fn get_profile_status(profile_id: String) -> ProfileStatus {
    let api_url = bitbrowser_api_url();
    match profile_pids(&api_url, &[profile_id.clone()]) {
        Ok(pids) => {
            let pid = pids.get(&profile_id).cloned();
            ProfileStatus {
                profile_id,
                opened: pid.is_some(),
                pid,
                error: None,
            }
        }
        Err(error) => ProfileStatus {
            profile_id,
            opened: false,
            pid: None,
            error: Some(error),
        },
    }
}

#[tauri::command]
pub fn open_profile(profile_id: String) -> Result<ProfileOperationResult, String> {
    let api_url = bitbrowser_api_url();
    let response = http_post_json(&api_url, "/browser/open", &json!({ "id": profile_id }))?;
    ensure_api_success(&response, "BitBrowser open")?;
    let cdp_endpoint = response
        .get("data")
        .and_then(extract_cdp_endpoint)
        .or_else(|| extract_cdp_endpoint(&response));

    Ok(ProfileOperationResult {
        profile_id,
        opened: true,
        cdp_endpoint,
        message: "profile opened".to_string(),
    })
}

#[tauri::command]
pub fn close_profile(profile_id: String) -> Result<ProfileOperationResult, String> {
    let api_url = bitbrowser_api_url();
    let response = http_post_json(&api_url, "/browser/close", &json!({ "id": profile_id }))?;
    ensure_api_success(&response, "BitBrowser close")?;

    Ok(ProfileOperationResult {
        profile_id,
        opened: false,
        cdp_endpoint: None,
        message: "profile closed".to_string(),
    })
}

#[tauri::command]
pub fn resolve_cdp_page_ws(request: CdpResolveRequest) -> Result<String, String> {
    let http_base = cdp_http_base(&request.cdp_endpoint)?;
    let response = match http_get_json(&http_base, "/json/list") {
        Ok(response) => response,
        Err(_error) if request.cdp_endpoint.starts_with("ws://") => {
            return Ok(request.cdp_endpoint);
        }
        Err(error) => return Err(error),
    };
    let pages = response
        .as_array()
        .ok_or_else(|| "CDP /json/list did not return a target list".to_string())?;

    select_preview_target(pages)
        .and_then(|target| {
            target
                .get("webSocketDebuggerUrl")
                .and_then(JsonValue::as_str)
                .map(ToString::to_string)
        })
        .or_else(|| {
            if request.cdp_endpoint.starts_with("ws://") {
                Some(request.cdp_endpoint)
            } else {
                None
            }
        })
        .ok_or_else(|| "No page WebSocket URL found from CDP endpoint".to_string())
}

fn select_preview_target(pages: &[JsonValue]) -> Option<&JsonValue> {
    pages
        .iter()
        .filter(|target| is_page_target(target))
        .find(|target| {
            target
                .get("url")
                .and_then(JsonValue::as_str)
                .map(|url| url.contains("tiktok.com"))
                .unwrap_or(false)
        })
        .or_else(|| {
            pages
                .iter()
                .filter(|target| is_page_target(target))
                .find(|target| {
                    target
                        .get("url")
                        .and_then(JsonValue::as_str)
                        .map(|url| !url.contains("console.bitbrowser.net"))
                        .unwrap_or(true)
                })
        })
        .or_else(|| pages.iter().find(|target| is_page_target(target)))
}

fn is_page_target(target: &JsonValue) -> bool {
    target
        .get("type")
        .and_then(JsonValue::as_str)
        .map(|value| value == "page")
        .unwrap_or(false)
}

#[tauri::command]
pub fn capture_browser_preview(request: CdpResolveRequest) -> Result<BrowserPreviewFrame, String> {
    let ws_url = resolve_cdp_page_ws(CdpResolveRequest {
        cdp_endpoint: request.cdp_endpoint,
    })?;
    let data = capture_cdp_screenshot(&ws_url)?;
    Ok(BrowserPreviewFrame {
        data_url: format!("data:image/jpeg;base64,{}", data),
    })
}

#[tauri::command]
pub fn check_proxy(request: ProxyCheckRequest) -> ProxyCheckResult {
    match parse_proxy(&request.proxy) {
        Ok(proxy) => {
            let api_url = bitbrowser_api_url();
            match check_proxy_inner(
                &api_url,
                &request.proxy_type,
                &proxy,
                request.check_exists.unwrap_or(true),
            ) {
                Ok(used) => ProxyCheckResult {
                    valid: true,
                    used,
                    message: if used {
                        "代理可用，但已被窗口使用".to_string()
                    } else {
                        "代理可用".to_string()
                    },
                    proxy: Some(proxy.to_public()),
                },
                Err(error) => ProxyCheckResult {
                    valid: false,
                    used: false,
                    message: error,
                    proxy: Some(proxy.to_public()),
                },
            }
        }
        Err(error) => ProxyCheckResult {
            valid: false,
            used: false,
            message: error,
            proxy: None,
        },
    }
}

#[tauri::command]
pub fn create_single_browser_profile(
    request: CreateProfileRequest,
) -> Result<CreateProfileResult, String> {
    validate_profile_name(&request.name)?;
    validate_proxy_type(&request.proxy_type)?;
    let proxy = parse_proxy(&request.proxy)?;
    let api_url = bitbrowser_api_url();

    if !request.skip_proxy_check.unwrap_or(false) {
        let used = check_proxy_inner(&api_url, &request.proxy_type, &proxy, true)?;
        if used && !request.allow_used_proxy.unwrap_or(false) {
            return Err("proxy is already used by another BitBrowser profile".to_string());
        }
    }

    let profile_id = create_browser_profile(
        &api_url,
        &request.name,
        &request.proxy_type,
        &proxy,
        request.group_id.as_deref(),
    )?;

    Ok(CreateProfileResult {
        name: request.name,
        profile_id,
        proxy: proxy.masked(),
    })
}

#[tauri::command]
pub fn create_batch_browser_profiles(
    request: BatchCreateProfileRequest,
) -> Result<BatchCreateProfileResult, String> {
    validate_profile_name(&format!("{}_1", request.prefix))?;
    validate_proxy_type(&request.proxy_type)?;
    let parsed_proxies = parse_proxy_lines(&request.proxies_text);
    let api_url = bitbrowser_api_url();
    let profiles = list_raw_profiles(&api_url, Some(format!("{}_", request.prefix)))?;
    let mut next_number = next_browser_number(&profiles, &request.prefix);
    let mut created = Vec::new();
    let mut skipped = Vec::new();
    let mut failed = Vec::new();

    for item in parsed_proxies {
        match item {
            Ok((line_number, proxy)) => {
                let name = format!("{}_{}", request.prefix, next_number);
                if !request.skip_proxy_check.unwrap_or(false) {
                    match check_proxy_inner(&api_url, &request.proxy_type, &proxy, true) {
                        Ok(true) if request.skip_used.unwrap_or(false) => {
                            skipped.push(BatchProfileIssue {
                                line_number,
                                name: Some(name),
                                proxy: proxy.masked(),
                                reason: "代理已被现有窗口使用".to_string(),
                            });
                            continue;
                        }
                        Ok(_) => {}
                        Err(error) => {
                            failed.push(BatchProfileIssue {
                                line_number,
                                name: Some(name),
                                proxy: proxy.masked(),
                                reason: error,
                            });
                            continue;
                        }
                    }
                }

                match create_browser_profile(
                    &api_url,
                    &name,
                    &request.proxy_type,
                    &proxy,
                    request.group_id.as_deref(),
                ) {
                    Ok(profile_id) => {
                        created.push(BatchCreatedProfile {
                            line_number,
                            name,
                            profile_id,
                            proxy: proxy.masked(),
                        });
                        next_number += 1;
                    }
                    Err(error) => failed.push(BatchProfileIssue {
                        line_number,
                        name: Some(name),
                        proxy: proxy.masked(),
                        reason: error,
                    }),
                }
            }
            Err(issue) => failed.push(issue),
        }
    }

    Ok(BatchCreateProfileResult {
        created,
        skipped,
        failed,
    })
}

#[tauri::command]
pub fn sync_accounts_dry_run(request: SyncAccountsRequest) -> Result<SyncPreview, String> {
    build_sync_preview(&request)
}

#[tauri::command]
pub fn sync_accounts_apply(request: SyncAccountsRequest) -> Result<SyncApplyResult, String> {
    let preview = build_sync_preview(&request)?;
    if !preview.can_apply {
        return Err(
            "sync preview cannot be applied; resolve missing or duplicate profiles first"
                .to_string(),
        );
    }
    if preview.accounts_to_add.is_empty() {
        return Err("no missing accounts to append".to_string());
    }
    let save_result = append_accounts_to_config(preview.accounts_to_add.clone())?;
    Ok(SyncApplyResult {
        preview,
        save_result,
    })
}

fn bitbrowser_api_url() -> String {
    if let Ok(settings) = load_local_app_settings() {
        if let Some(api_url) = settings
            .bitbrowser_api_url
            .as_deref()
            .map(str::trim)
            .filter(|value| !value.is_empty())
        {
            return api_url.to_string();
        }
    }

    load_config()
        .ok()
        .and_then(|snapshot| snapshot.bitbrowser_api_url())
        .unwrap_or_else(|| "http://127.0.0.1:54345".to_string())
}

fn builtin_chromium_status() -> BuiltinChromiumStatus {
    let checked_at = Local::now().to_rfc3339();
    let data_root = builtin_data_root()
        .map(|path| normalize(&path))
        .unwrap_or_else(|_| String::new());
    match locate_chromium_executable() {
        Ok(executable) => BuiltinChromiumStatus {
            available: true,
            executable_path: Some(normalize(&executable)),
            data_root,
            checked_at,
            error: None,
        },
        Err(error) => BuiltinChromiumStatus {
            available: false,
            executable_path: None,
            data_root,
            checked_at,
            error: Some(error),
        },
    }
}

pub fn locate_chromium_executable() -> Result<PathBuf, String> {
    let mut candidates = Vec::new();
    if let Ok(value) = std::env::var("AM_CHROMIUM_EXECUTABLE") {
        push_nonempty_path(&mut candidates, &value);
    }
    if let Ok(settings) = load_local_app_settings() {
        push_nonempty_path(&mut candidates, &effective_chromium_executable(&settings));
    }
    if let Ok(snapshot) = load_config() {
        if let Some(value) = snapshot.chromium_executable() {
            push_nonempty_path(&mut candidates, &value);
        }
    }
    if cfg!(windows) {
        for root in [
            std::env::var("PROGRAMFILES").ok(),
            std::env::var("PROGRAMFILES(X86)").ok(),
            std::env::var("LOCALAPPDATA").ok(),
        ]
        .into_iter()
        .flatten()
        {
            candidates.push(
                PathBuf::from(&root)
                    .join("Google")
                    .join("Chrome")
                    .join("Application")
                    .join("chrome.exe"),
            );
            candidates.push(
                PathBuf::from(&root)
                    .join("Microsoft")
                    .join("Edge")
                    .join("Application")
                    .join("msedge.exe"),
            );
        }
    }
    if cfg!(target_os = "macos") {
        for root in ["/Applications", "~/Applications"] {
            for app in [
                "Google Chrome.app/Contents/MacOS/Google Chrome",
                "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
                "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "Chromium.app/Contents/MacOS/Chromium",
            ] {
                push_nonempty_path(&mut candidates, &format!("{}/{}", root, app));
            }
        }
    }
    if !cfg!(windows) {
        for name in [
            "chromium",
            "chromium-browser",
            "google-chrome",
            "google-chrome-stable",
            "microsoft-edge",
            "msedge",
        ] {
            if let Some(path) = find_on_path(name) {
                candidates.push(path);
            }
        }
    }
    candidates
        .into_iter()
        .find_map(|path| resolve_chromium_candidate(&path))
        .ok_or_else(|| {
            "未检测到可用 Chromium，请安装 Chrome/Edge/Chromium 或手动指定可执行文件。".to_string()
        })
}

fn push_nonempty_path(candidates: &mut Vec<PathBuf>, value: &str) {
    let trimmed = value.trim();
    if !trimmed.is_empty() {
        candidates.push(expand_user_path(trimmed));
    }
}

fn expand_user_path(value: &str) -> PathBuf {
    if let Some(rest) = value.strip_prefix("~/") {
        if let Ok(home) = std::env::var("HOME") {
            return PathBuf::from(home).join(rest);
        }
    }
    PathBuf::from(value)
}

fn resolve_chromium_candidate(path: &Path) -> Option<PathBuf> {
    if path.is_file() {
        return Some(path.to_path_buf());
    }
    if cfg!(target_os = "macos")
        && path.extension().and_then(|value| value.to_str()) == Some("app")
        && path.is_dir()
    {
        let macos_dir = path.join("Contents").join("MacOS");
        let mut names = Vec::new();
        if let Some(stem) = path.file_stem().and_then(|value| value.to_str()) {
            names.push(stem.to_string());
        }
        names.extend([
            "Google Chrome".to_string(),
            "Google Chrome for Testing".to_string(),
            "Microsoft Edge".to_string(),
            "Chromium".to_string(),
        ]);
        return names
            .into_iter()
            .map(|name| macos_dir.join(name))
            .find(|candidate| candidate.is_file());
    }
    None
}

fn find_on_path(name: &str) -> Option<PathBuf> {
    let paths = std::env::var_os("PATH")?;
    std::env::split_paths(&paths)
        .map(|dir| dir.join(name))
        .find(|path| path.is_file())
}

fn builtin_data_root() -> Result<PathBuf, String> {
    Ok(PathBuf::from(project_paths()?.data_dir)
        .join("browser")
        .join("builtin_chromium"))
}

fn safe_account_dir_name(account_id: &str) -> String {
    let value = account_id
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.') {
                ch
            } else {
                '_'
            }
        })
        .collect::<String>();
    if value.trim().is_empty() {
        "account".to_string()
    } else {
        value
    }
}

fn builtin_account_dir(account_id: &str) -> Result<PathBuf, String> {
    Ok(builtin_data_root()?.join(safe_account_dir_name(account_id)))
}

fn builtin_user_data_dir(account_id: &str, configured: Option<&str>) -> Result<PathBuf, String> {
    if let Some(configured) = configured.map(str::trim).filter(|value| !value.is_empty()) {
        let path = PathBuf::from(configured);
        if path.is_absolute() {
            return Ok(path);
        }
        return Ok(PathBuf::from(project_paths()?.data_dir).join(path));
    }
    Ok(builtin_account_dir(account_id)?.join("user-data"))
}

fn builtin_runtime_path(account_id: &str) -> Result<PathBuf, String> {
    Ok(builtin_account_dir(account_id)?.join("runtime.json"))
}

fn legacy_builtin_session_path(account_id: &str) -> Result<PathBuf, String> {
    Ok(builtin_account_dir(account_id)?.join("session.json"))
}

fn builtin_session_paths(account_id: &str) -> Result<Vec<PathBuf>, String> {
    Ok(vec![
        builtin_runtime_path(account_id)?,
        legacy_builtin_session_path(account_id)?,
    ])
}

fn builtin_session_for_account(account_id: &str) -> Result<Option<JsonValue>, String> {
    for path in builtin_session_paths(account_id)? {
        if !path.exists() {
            continue;
        }
        let raw = fs::read_to_string(&path)
            .map_err(|err| format!("failed to read {}: {}", normalize(&path), err))?;
        return serde_json::from_str(&raw)
            .map(Some)
            .map_err(|err| format!("failed to parse {}: {}", normalize(&path), err));
    }
    Ok(None)
}

struct UserDataDirAccess {
    readable: bool,
    writable: bool,
    detail: String,
}

#[derive(Debug, Clone)]
struct BuiltinProxyParts {
    scheme: String,
    host: String,
    port: u16,
    username: Option<String>,
    password: Option<String>,
}

impl BuiltinProxyParts {
    fn masked(&self) -> String {
        if let Some(username) = self.username.as_ref() {
            format!(
                "{}://{}:***@{}:{}",
                self.scheme, username, self.host, self.port
            )
        } else {
            format!("{}://{}:{}", self.scheme, self.host, self.port)
        }
    }

    fn has_password(&self) -> bool {
        self.password
            .as_ref()
            .is_some_and(|password| !password.is_empty())
    }
}

fn user_data_dir_access_detail(path: &PathBuf) -> UserDataDirAccess {
    if let Err(error) = fs::create_dir_all(path) {
        return UserDataDirAccess {
            readable: false,
            writable: false,
            detail: format!(
                "path={}; exists={}; readable=false; writable=false; error={}",
                normalize(path),
                path.exists(),
                error
            ),
        };
    }

    let readable = path.is_dir() && fs::read_dir(path).is_ok();
    let test_file = path.join(".account-matrix-write-test");
    let writable = fs::write(&test_file, b"ok").is_ok();
    if writable {
        let _ = fs::remove_file(&test_file);
    }

    UserDataDirAccess {
        readable,
        writable,
        detail: format!(
            "path={}; exists={}; readable={}; writable={}",
            normalize(path),
            path.exists(),
            readable,
            writable
        ),
    }
}

fn parse_builtin_proxy(proxy_type: Option<&str>, raw: &str) -> Result<BuiltinProxyParts, String> {
    let value = raw.trim();
    if value.is_empty() {
        return Err("browser.proxy must be non-empty".to_string());
    }
    let default_scheme = proxy_type
        .map(str::trim)
        .filter(|scheme| !scheme.is_empty())
        .unwrap_or("socks5")
        .to_ascii_lowercase();
    validate_builtin_proxy_scheme(&default_scheme, "browser.proxy_type")?;

    if let Some((scheme, rest)) = value.split_once("://") {
        let scheme = scheme.trim().to_ascii_lowercase();
        validate_builtin_proxy_scheme(&scheme, "browser.proxy scheme")?;
        let (userinfo, host_port) = if let Some((userinfo, host_port)) = rest.rsplit_once('@') {
            (Some(userinfo), host_port)
        } else {
            (None, rest)
        };
        let (host, port) = parse_host_port(host_port)?;
        let (username, password) = parse_proxy_userinfo(userinfo)?;
        return Ok(BuiltinProxyParts {
            scheme,
            host,
            port,
            username,
            password,
        });
    }

    let parts = value.split(':').collect::<Vec<_>>();
    if parts.len() == 2 {
        let host = require_proxy_segment(parts[0], "browser.proxy host")?;
        let port = parse_proxy_port(parts[1])?;
        return Ok(BuiltinProxyParts {
            scheme: default_scheme,
            host,
            port,
            username: None,
            password: None,
        });
    }
    if parts.len() == 4 {
        let host = require_proxy_segment(parts[0], "browser.proxy host")?;
        let port = parse_proxy_port(parts[1])?;
        let username = require_proxy_segment(parts[2], "browser.proxy username")?;
        let password = require_proxy_segment(parts[3], "browser.proxy password")?;
        return Ok(BuiltinProxyParts {
            scheme: default_scheme,
            host,
            port,
            username: Some(username),
            password: Some(password),
        });
    }

    Err("browser.proxy must be host:port or host:port:username:password".to_string())
}

fn validate_builtin_proxy_scheme(value: &str, field: &str) -> Result<(), String> {
    if matches!(value, "http" | "https" | "socks5") {
        Ok(())
    } else {
        Err(format!("{} must be http, https, or socks5", field))
    }
}

fn parse_proxy_userinfo(
    userinfo: Option<&str>,
) -> Result<(Option<String>, Option<String>), String> {
    let Some(userinfo) = userinfo else {
        return Ok((None, None));
    };
    let (username, password) = userinfo
        .split_once(':')
        .ok_or_else(|| "browser.proxy URL credentials must be username:password".to_string())?;
    Ok((
        Some(require_proxy_segment(username, "browser.proxy username")?),
        Some(require_proxy_segment(password, "browser.proxy password")?),
    ))
}

fn parse_host_port(value: &str) -> Result<(String, u16), String> {
    let (host, port) = value
        .rsplit_once(':')
        .ok_or_else(|| "browser.proxy URL must include host and port".to_string())?;
    Ok((
        require_proxy_segment(host, "browser.proxy host")?,
        parse_proxy_port(port)?,
    ))
}

fn require_proxy_segment(value: &str, field: &str) -> Result<String, String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        Err(format!("{} must be non-empty", field))
    } else {
        Ok(trimmed.to_string())
    }
}

fn parse_proxy_port(value: &str) -> Result<u16, String> {
    let port = value
        .trim()
        .parse::<u16>()
        .map_err(|_| "browser.proxy port must be between 1 and 65535".to_string())?;
    if port == 0 {
        return Err("browser.proxy port must be between 1 and 65535".to_string());
    }
    Ok(port)
}

fn builtin_proxy_connectivity_detail(proxy: &BuiltinProxyParts) -> ProviderDiagnosticCheck {
    let target = format!("{}:{}", proxy.host, proxy.port);
    let address = match target
        .to_socket_addrs()
        .ok()
        .and_then(|mut addrs| addrs.next())
    {
        Some(address) => address,
        None => {
            return ProviderDiagnosticCheck {
                name: "proxyConnectivity".to_string(),
                status: "error".to_string(),
                detail: format!(
                    "{}; passwordSet={}; host={}; port={}; reachable=false; error=failed to resolve host",
                    proxy.masked(),
                    proxy.has_password(),
                    proxy.host,
                    proxy.port
                ),
            };
        }
    };
    match TcpStream::connect_timeout(&address, Duration::from_secs(3)) {
        Ok(_) => ProviderDiagnosticCheck {
            name: "proxyConnectivity".to_string(),
            status: "ok".to_string(),
            detail: format!(
                "{}; passwordSet={}; host={}; port={}; reachable=true",
                proxy.masked(),
                proxy.has_password(),
                proxy.host,
                proxy.port
            ),
        },
        Err(error) => ProviderDiagnosticCheck {
            name: "proxyConnectivity".to_string(),
            status: "error".to_string(),
            detail: format!(
                "{}; passwordSet={}; host={}; port={}; reachable=false; error={}",
                proxy.masked(),
                proxy.has_password(),
                proxy.host,
                proxy.port,
                error
            ),
        },
    }
}

fn builtin_cdp_endpoint_detail(cdp_endpoint: &str) -> ProviderDiagnosticCheck {
    match cdp_http_base(cdp_endpoint).and_then(|base| http_get_json(&base, "/json/version")) {
        Ok(response) => {
            let browser = response
                .get("Browser")
                .and_then(JsonValue::as_str)
                .unwrap_or("unknown");
            ProviderDiagnosticCheck {
                name: "cdpEndpoint".to_string(),
                status: "ok".to_string(),
                detail: format!("{}; /json/version ok; browser={}", cdp_endpoint, browser),
            }
        }
        Err(error) => ProviderDiagnosticCheck {
            name: "cdpEndpoint".to_string(),
            status: "error".to_string(),
            detail: format!("{}; /json/version failed: {}", cdp_endpoint, error),
        },
    }
}

fn session_pid(session: &JsonValue) -> Option<i64> {
    session
        .get("lastPid")
        .or_else(|| session.get("pid"))
        .and_then(JsonValue::as_i64)
}

fn session_port(session: &JsonValue) -> Option<i64> {
    session
        .get("lastPort")
        .or_else(|| session.get("port"))
        .and_then(JsonValue::as_i64)
}

fn session_cdp_endpoint(session: &JsonValue) -> Option<&str> {
    session
        .get("lastCdpEndpoint")
        .or_else(|| session.get("cdp_endpoint"))
        .and_then(JsonValue::as_str)
}

fn session_account_id(session: &JsonValue) -> Option<&str> {
    session
        .get("accountId")
        .or_else(|| session.get("account_id"))
        .and_then(JsonValue::as_str)
}

fn session_matches_account(account_id: &str, session: &JsonValue) -> bool {
    let provider = session
        .get("provider")
        .and_then(JsonValue::as_str)
        .unwrap_or("builtin_chromium");
    provider == "builtin_chromium" && session_account_id(session) == Some(account_id)
}

fn pid_alive(pid: u32) -> bool {
    if pid == 0 {
        return false;
    }
    if cfg!(windows) {
        let output = Command::new("tasklist")
            .args(["/FI", &format!("PID eq {}", pid), "/NH"])
            .output();
        return output
            .ok()
            .and_then(|output| String::from_utf8(output.stdout).ok())
            .is_some_and(|stdout| stdout.contains(&pid.to_string()));
    }
    Command::new("kill")
        .args(["-0", &pid.to_string()])
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

fn terminate_pid(pid: u32) {
    if pid == 0 {
        return;
    }
    if cfg!(windows) {
        let _ = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .output();
    } else {
        let _ = Command::new("kill")
            .arg("-TERM")
            .arg(pid.to_string())
            .output();
    }
}

fn list_raw_profiles(api_url: &str, name: Option<String>) -> Result<Vec<JsonValue>, String> {
    let mut profiles = Vec::new();
    let mut page = 0;
    let page_size = 100;

    loop {
        let mut payload = json!({
            "page": page,
            "pageSize": page_size,
            "sort": "asc"
        });
        if let Some(name) = name.as_deref() {
            payload["name"] = JsonValue::String(name.to_string());
        }

        let response = http_post_json(api_url, "/browser/list", &payload)?;
        ensure_api_success(&response, "BitBrowser list")?;
        let data = response
            .get("data")
            .ok_or_else(|| "BitBrowser list returned no data".to_string())?;
        let (items, total) = extract_list_items(data)?;
        let item_count = items.len();
        profiles.extend(items);

        if item_count == 0 || item_count < page_size {
            break;
        }
        if let Some(total) = total {
            if profiles.len() >= total {
                break;
            }
        }
        page += 1;
    }

    Ok(profiles)
}

fn profile_pids(api_url: &str, ids: &[String]) -> Result<HashMap<String, String>, String> {
    if ids.is_empty() {
        return Ok(HashMap::new());
    }

    let response = http_post_json(api_url, "/browser/pids", &json!({ "ids": ids }))?;
    ensure_api_success(&response, "BitBrowser pids")?;
    let mut pids = HashMap::new();
    let data = response.get("data").unwrap_or(&JsonValue::Null);

    if let Some(map) = data.as_object() {
        for (id, value) in map {
            if json_value_truthy(value) {
                pids.insert(id.clone(), json_value_to_label(value));
            }
        }
    }

    Ok(pids)
}

fn map_browser_profile(
    raw: &JsonValue,
    opened_by_id: &HashMap<String, String>,
    bindings: &HashMap<String, String>,
) -> Option<BrowserProfile> {
    let id = profile_id_from_raw(raw)?;
    let name =
        string_field(raw, &["name", "browserName", "windowName"]).unwrap_or_else(|| id.clone());
    let proxy = proxy_label_from_raw(raw);

    Some(BrowserProfile {
        platform: Some(infer_platform_from_name(&name)),
        group_id: string_field(raw, &["groupId", "group_id"]),
        opened: opened_by_id.contains_key(&id),
        bound_account_id: bindings.get(&id).cloned(),
        id,
        name,
        proxy,
    })
}

fn profile_account_bindings() -> HashMap<String, String> {
    let mut bindings = HashMap::new();
    if let Ok(config) = load_config() {
        for account in config.accounts() {
            if let Some(profile_id) = account.bitbrowser_profile_id() {
                bindings.insert(profile_id.to_string(), account.id().to_string());
            }
        }
    }
    bindings
}

fn build_sync_preview(request: &SyncAccountsRequest) -> Result<SyncPreview, String> {
    validate_sync_request(request)?;
    let api_url = bitbrowser_api_url();
    let profiles = list_raw_profiles(&api_url, Some(format!("{}_", request.prefix)))?;
    let (profile_map, duplicate_profiles) = exact_profile_map(&profiles, &request.prefix);
    let config = load_config()?;
    let existing_ids = config
        .accounts()
        .iter()
        .map(|account| account.id().to_string())
        .collect::<HashSet<_>>();

    let mut accounts_to_add = Vec::new();
    let mut existing_accounts = Vec::new();
    let mut missing_profiles = Vec::new();

    for number in request.start..=request.end {
        let account_id = format!("{}_{}", request.prefix, number);
        if existing_ids.contains(&account_id) {
            existing_accounts.push(account_id);
            continue;
        }

        let Some(profile_id) = profile_map.get(&account_id) else {
            missing_profiles.push(account_id);
            continue;
        };

        accounts_to_add.push(build_account_input(
            number,
            &request.prefix,
            profile_id,
            request,
        )?);
    }

    let can_apply = missing_profiles.is_empty() && duplicate_profiles.is_empty();
    Ok(SyncPreview {
        accounts_to_add,
        existing_accounts,
        missing_profiles,
        duplicate_profiles,
        can_apply,
    })
}

fn check_proxy_inner(
    api_url: &str,
    proxy_type: &str,
    proxy: &ProxyParts,
    check_exists: bool,
) -> Result<bool, String> {
    validate_proxy_type(proxy_type)?;
    let response = http_post_json(
        api_url,
        "/checkagent",
        &json!({
            "proxyType": proxy_type,
            "host": proxy.host,
            "port": proxy.port.to_string(),
            "proxyUserName": proxy.username,
            "proxyPassword": proxy.password,
            "checkExists": if check_exists { 1 } else { 0 },
        }),
    )?;
    ensure_api_success(&response, "BitBrowser proxy check")?;
    let result = response.get("data").unwrap_or(&JsonValue::Null);

    if let Some(success) = result.get("success").and_then(JsonValue::as_bool) {
        if !success {
            return Err(api_message(result, "BitBrowser proxy check failed"));
        }
    }

    let payload = result.get("data").unwrap_or(result);
    Ok(payload
        .get("used")
        .and_then(JsonValue::as_bool)
        .unwrap_or(false))
}

fn create_browser_profile(
    api_url: &str,
    name: &str,
    proxy_type: &str,
    proxy: &ProxyParts,
    group_id: Option<&str>,
) -> Result<String, String> {
    let mut payload = json!({
        "name": name,
        "proxyMethod": 2,
        "proxyType": proxy_type,
        "host": proxy.host,
        "port": proxy.port,
        "proxyUserName": proxy.username,
        "proxyPassword": proxy.password,
        "ipCheckService": "ip-api",
        "browserFingerPrint": {},
        "stopWhileNetError": true,
        "randomFingerprint": false,
        "workbench": "disable"
    });
    if let Some(group_id) = group_id.map(str::trim).filter(|value| !value.is_empty()) {
        payload["groupId"] = JsonValue::String(group_id.to_string());
    }

    let response = http_post_json(api_url, "/browser/update", &payload)?;
    ensure_api_success(&response, "BitBrowser create")?;
    let data = response.get("data").unwrap_or(&JsonValue::Null);
    if let Some(id) = data.as_str() {
        return Ok(id.to_string());
    }
    if let Some(id) = data
        .get("id")
        .or_else(|| data.get("browserId"))
        .and_then(JsonValue::as_str)
    {
        return Ok(id.to_string());
    }

    Err("BitBrowser created the profile but returned no profile id".to_string())
}

#[derive(Debug, Clone)]
struct ProxyParts {
    host: String,
    port: u16,
    username: String,
    password: String,
}

impl ProxyParts {
    fn masked(&self) -> String {
        format!("{}:{}:{}:***", self.host, self.port, self.username)
    }

    fn to_public(&self) -> ParsedProxy {
        ParsedProxy {
            host: self.host.clone(),
            port: self.port,
            username: self.username.clone(),
            masked: self.masked(),
        }
    }
}

fn parse_proxy(value: &str) -> Result<ProxyParts, String> {
    let parts = value.trim().splitn(4, ':').collect::<Vec<_>>();
    if parts.len() != 4 || parts.iter().any(|part| part.trim().is_empty()) {
        return Err("代理格式必须是 host:port:用户名:密码".to_string());
    }

    let port = parts[1]
        .parse::<u16>()
        .map_err(|_| "代理端口必须是 1~65535 的整数".to_string())?;
    if port == 0 {
        return Err("代理端口必须是 1~65535 的整数".to_string());
    }

    Ok(ProxyParts {
        host: parts[0].trim().to_string(),
        port,
        username: parts[2].trim().to_string(),
        password: parts[3].trim().to_string(),
    })
}

fn parse_proxy_lines(text: &str) -> Vec<Result<(usize, ProxyParts), BatchProfileIssue>> {
    let mut items = Vec::new();
    for (index, raw) in text.lines().enumerate() {
        let line_number = index + 1;
        let value = raw.trim();
        if value.is_empty() || value.starts_with('#') {
            continue;
        }
        match parse_proxy(value) {
            Ok(proxy) => items.push(Ok((line_number, proxy))),
            Err(reason) => items.push(Err(BatchProfileIssue {
                line_number,
                name: None,
                proxy: value.to_string(),
                reason,
            })),
        }
    }
    items
}

fn validate_proxy_type(proxy_type: &str) -> Result<(), String> {
    if matches!(proxy_type, "http" | "https" | "socks5") {
        Ok(())
    } else {
        Err("代理协议必须是 http、https 或 socks5".to_string())
    }
}

fn validate_profile_name(name: &str) -> Result<(), String> {
    let value = name.trim();
    if value.is_empty()
        || !value
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-')
    {
        return Err("窗口名称只能包含字母、数字、下划线和短横线".to_string());
    }
    Ok(())
}

fn validate_sync_request(request: &SyncAccountsRequest) -> Result<(), String> {
    validate_profile_name(&format!("{}_1", request.prefix))?;
    if request.start > request.end {
        return Err("同步起始编号不能大于结束编号".to_string());
    }
    if request.morning_start > request.morning_end || request.evening_start > request.evening_end {
        return Err("上午段或晚上段编号范围不合法".to_string());
    }
    let morning_count = request.morning_end - request.morning_start + 1;
    let evening_count = request.evening_end - request.evening_start + 1;
    if morning_count != evening_count {
        return Err("上午段和晚上段数量必须一致，才能一一复用 ip_group".to_string());
    }
    Ok(())
}

fn build_account_input(
    number: i64,
    prefix: &str,
    profile_id: &str,
    request: &SyncAccountsRequest,
) -> Result<AccountInput, String> {
    let (shift_name, active_hours) = shift_for_number(number, request)?;
    let ip_group = ip_group_for_number(number, request)?;
    let notes = if shift_name == "晚上" {
        let pair_number = request.morning_start + (number - request.evening_start);
        format!(
            "IP-{} 晚上（与 {}_{} 共享 IP）",
            ip_group, prefix, pair_number
        )
    } else {
        format!("IP-{} 上午", ip_group)
    };

    Ok(AccountInput {
        id: format!("{}_{}", prefix, number),
        platform: infer_platform_from_name(prefix),
        enabled: true,
        scheduled: Some(true),
        ip_group: Some(ip_group),
        active_hours,
        browser_provider: None,
        browser: None,
        login: None,
        bitbrowser_profile_id: Some(profile_id.to_string()),
        notes: Some(notes),
    })
}

fn shift_for_number(
    number: i64,
    request: &SyncAccountsRequest,
) -> Result<(&'static str, Vec<[f64; 2]>), String> {
    if request.morning_start <= number && number <= request.morning_end {
        return Ok(("上午", vec![[9.0, 12.0]]));
    }
    if request.evening_start <= number && number <= request.evening_end {
        return Ok(("晚上", vec![[19.0, 23.0]]));
    }
    Err(format!(
        "编号 {} 不在上午段 {}-{} 或晚上段 {}-{} 内",
        number,
        request.morning_start,
        request.morning_end,
        request.evening_start,
        request.evening_end
    ))
}

fn ip_group_for_number(number: i64, request: &SyncAccountsRequest) -> Result<i64, String> {
    if request.morning_start <= number && number <= request.morning_end {
        return Ok(request.first_ip_group + (number - request.morning_start));
    }
    if request.evening_start <= number && number <= request.evening_end {
        return Ok(request.first_ip_group + (number - request.evening_start));
    }
    Err(format!("编号 {} 无法计算 ip_group", number))
}

fn exact_profile_map(
    profiles: &[JsonValue],
    prefix: &str,
) -> (HashMap<String, String>, Vec<String>) {
    let mut by_name = HashMap::new();
    let mut duplicates = Vec::new();
    let needle = format!("{}_", prefix);

    for profile in profiles {
        let Some(name) = string_field(profile, &["name", "browserName", "windowName"]) else {
            continue;
        };
        if !name.starts_with(&needle) {
            continue;
        }
        let Some(profile_id) = profile_id_from_raw(profile) else {
            continue;
        };
        if by_name.insert(name.clone(), profile_id).is_some() {
            duplicates.push(name);
        }
    }

    duplicates.sort();
    duplicates.dedup();
    (by_name, duplicates)
}

fn next_browser_number(profiles: &[JsonValue], prefix: &str) -> i64 {
    let needle = format!("{}_", prefix);
    profiles
        .iter()
        .filter_map(|profile| string_field(profile, &["name", "browserName", "windowName"]))
        .filter_map(|name| {
            name.strip_prefix(&needle)
                .and_then(|value| value.parse::<i64>().ok())
        })
        .max()
        .unwrap_or(0)
        + 1
}

fn extract_list_items(data: &JsonValue) -> Result<(Vec<JsonValue>, Option<usize>), String> {
    if let Some(items) = data.as_array() {
        return Ok((items.clone(), None));
    }
    let Some(map) = data.as_object() else {
        return Err("BitBrowser list returned an unsupported data structure".to_string());
    };

    let items = ["list", "rows", "records", "items"]
        .iter()
        .find_map(|key| map.get(*key).and_then(JsonValue::as_array))
        .ok_or_else(|| "BitBrowser list returned no profile list".to_string())?
        .clone();
    let total = ["total", "totalNum", "totalCount"]
        .iter()
        .find_map(|key| map.get(*key).and_then(JsonValue::as_u64))
        .map(|value| value as usize);
    Ok((items, total))
}

fn profile_id_from_raw(profile: &JsonValue) -> Option<String> {
    string_field(profile, &["id", "browserId"])
}

fn proxy_label_from_raw(profile: &JsonValue) -> Option<String> {
    let host = string_field(profile, &["host", "proxyHost", "proxyServer"])?;
    let port = string_field(profile, &["port", "proxyPort"]).unwrap_or_default();
    if port.is_empty() {
        Some(host)
    } else {
        Some(format!("{}:{}", host, port))
    }
}

fn string_field(value: &JsonValue, keys: &[&str]) -> Option<String> {
    keys.iter().find_map(|key| {
        value.get(*key).and_then(|field| {
            field
                .as_str()
                .map(ToString::to_string)
                .or_else(|| field.as_i64().map(|number| number.to_string()))
                .or_else(|| field.as_u64().map(|number| number.to_string()))
        })
    })
}

fn infer_platform_from_name(name: &str) -> String {
    if name.starts_with("instagram") {
        "instagram".to_string()
    } else if name.starts_with("whatsapp") {
        "whatsapp".to_string()
    } else if name.starts_with("douyin") {
        "douyin".to_string()
    } else {
        "tiktok".to_string()
    }
}

fn extract_cdp_endpoint(value: &JsonValue) -> Option<String> {
    ["ws", "webSocketDebuggerUrl", "http", "debuggerAddress"]
        .iter()
        .find_map(|key| value.get(*key).and_then(JsonValue::as_str))
        .map(|endpoint| {
            if endpoint.starts_with("http://")
                || endpoint.starts_with("https://")
                || endpoint.starts_with("ws://")
                || endpoint.starts_with("wss://")
            {
                endpoint.to_string()
            } else {
                format!("http://{}", endpoint)
            }
        })
}

fn ensure_api_success(value: &JsonValue, label: &str) -> Result<(), String> {
    if value
        .get("success")
        .and_then(JsonValue::as_bool)
        .unwrap_or(false)
    {
        Ok(())
    } else {
        Err(api_message(value, label))
    }
}

fn api_message(value: &JsonValue, fallback: &str) -> String {
    value
        .get("msg")
        .or_else(|| value.get("message"))
        .and_then(JsonValue::as_str)
        .map(ToString::to_string)
        .unwrap_or_else(|| fallback.to_string())
}

fn json_value_truthy(value: &JsonValue) -> bool {
    match value {
        JsonValue::Bool(value) => *value,
        JsonValue::Number(number) => number.as_i64().unwrap_or(0) != 0,
        JsonValue::String(value) => !value.is_empty() && value != "0",
        JsonValue::Object(map) => !map.is_empty(),
        JsonValue::Array(items) => !items.is_empty(),
        JsonValue::Null => false,
    }
}

fn json_value_to_label(value: &JsonValue) -> String {
    if let Some(value) = value.as_str() {
        value.to_string()
    } else if let Some(value) = value.as_i64() {
        value.to_string()
    } else if let Some(pid) = value.get("pid").or_else(|| value.get("processId")) {
        json_value_to_label(pid)
    } else {
        value.to_string()
    }
}

fn check_tcp(addr: SocketAddr) -> Result<(), String> {
    TcpStream::connect_timeout(&addr, Duration::from_millis(800))
        .map(|_| ())
        .map_err(|err| format!("failed to connect {}: {}", addr, err))
}

fn http_post_json(api_url: &str, path: &str, body: &JsonValue) -> Result<JsonValue, String> {
    let endpoint = parse_http_endpoint(api_url, path)?;
    let addr = format!("{}:{}", endpoint.host, endpoint.port)
        .to_socket_addrs()
        .map_err(|err| format!("failed to resolve BitBrowser API host: {}", err))?
        .next()
        .ok_or_else(|| "failed to resolve BitBrowser API host".to_string())?;
    let body_text = serde_json::to_string(body)
        .map_err(|err| format!("failed to serialize BitBrowser request: {}", err))?;
    let request = format!(
        "POST {} HTTP/1.1\r\nHost: {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        endpoint.path,
        endpoint.host_header,
        body_text.as_bytes().len(),
        body_text
    );

    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_secs(6))
        .map_err(|err| format!("failed to connect {}: {}", api_url, err))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(30)))
        .map_err(|err| format!("failed to set read timeout: {}", err))?;
    stream
        .set_write_timeout(Some(Duration::from_secs(10)))
        .map_err(|err| format!("failed to set write timeout: {}", err))?;
    stream
        .write_all(request.as_bytes())
        .map_err(|err| format!("failed to write BitBrowser request: {}", err))?;

    let mut response = Vec::new();
    stream
        .read_to_end(&mut response)
        .map_err(|err| format!("failed to read BitBrowser response: {}", err))?;
    parse_http_json_response(&response)
}

fn http_get_json(api_url: &str, path: &str) -> Result<JsonValue, String> {
    let endpoint = parse_http_endpoint(api_url, path)?;
    let addr = format!("{}:{}", endpoint.host, endpoint.port)
        .to_socket_addrs()
        .map_err(|err| format!("failed to resolve CDP host: {}", err))?
        .next()
        .ok_or_else(|| "failed to resolve CDP host".to_string())?;
    let request = format!(
        "GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n",
        endpoint.path, endpoint.host_header
    );

    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_secs(5))
        .map_err(|err| format!("failed to connect {}: {}", api_url, err))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(10)))
        .map_err(|err| format!("failed to set read timeout: {}", err))?;
    stream
        .set_write_timeout(Some(Duration::from_secs(5)))
        .map_err(|err| format!("failed to set write timeout: {}", err))?;
    stream
        .write_all(request.as_bytes())
        .map_err(|err| format!("failed to write CDP request: {}", err))?;

    let mut response = Vec::new();
    stream
        .read_to_end(&mut response)
        .map_err(|err| format!("failed to read CDP response: {}", err))?;
    parse_http_json_response(&response)
}

struct HttpEndpoint {
    host: String,
    port: u16,
    host_header: String,
    path: String,
}

fn parse_http_endpoint(api_url: &str, path: &str) -> Result<HttpEndpoint, String> {
    let trimmed = api_url.trim().trim_end_matches('/');
    if trimmed.starts_with("https://") {
        return Err("local HTTP endpoint must use http:// for desktop direct calls".to_string());
    }
    let without_scheme = trimmed
        .strip_prefix("http://")
        .ok_or_else(|| format!("unsupported local HTTP endpoint '{}'", api_url))?;
    let (authority, base_path) = without_scheme
        .split_once('/')
        .map(|(authority, base_path)| (authority, format!("/{}", base_path.trim_matches('/'))))
        .unwrap_or((without_scheme, String::new()));
    let (host, port) = authority
        .rsplit_once(':')
        .map(|(host, port)| {
            let parsed_port = port
                .parse::<u16>()
                .map_err(|_| format!("invalid local HTTP endpoint port '{}'", port))?;
            Ok::<(String, u16), String>((host.to_string(), parsed_port))
        })
        .unwrap_or_else(|| Ok((authority.to_string(), 80)))?;
    let request_path = format!("{}{}", base_path, path);

    Ok(HttpEndpoint {
        host: host.clone(),
        port,
        host_header: if authority.contains(':') {
            authority.to_string()
        } else {
            format!("{}:{}", host, port)
        },
        path: request_path,
    })
}

fn parse_http_json_response(response: &[u8]) -> Result<JsonValue, String> {
    let response_text = String::from_utf8_lossy(response);
    let (head, body) = response_text
        .split_once("\r\n\r\n")
        .ok_or_else(|| "invalid HTTP response from local endpoint".to_string())?;
    let status_line = head.lines().next().unwrap_or_default();
    if !status_line.contains(" 200 ") {
        return Err(format!("local endpoint HTTP error: {}", status_line));
    }
    serde_json::from_str(body.trim())
        .map_err(|err| format!("failed to parse local endpoint JSON response: {}", err))
}

fn cdp_http_base(endpoint: &str) -> Result<String, String> {
    let trimmed = endpoint.trim().trim_end_matches('/');
    let without_scheme = trimmed
        .strip_prefix("http://")
        .or_else(|| trimmed.strip_prefix("ws://"))
        .ok_or_else(|| "CDP endpoint must use http:// or ws://".to_string())?;
    let authority = without_scheme
        .split('/')
        .next()
        .filter(|value| !value.is_empty())
        .ok_or_else(|| "CDP endpoint is missing host".to_string())?;
    let (host, port) = authority
        .rsplit_once(':')
        .ok_or_else(|| "CDP endpoint must include a debugging port".to_string())?;
    port.parse::<u16>()
        .map_err(|_| format!("invalid CDP endpoint port '{}'", port))?;
    let host = host.trim_matches(|ch| ch == '[' || ch == ']');

    if !matches!(host, "127.0.0.1" | "localhost" | "::1") {
        return Err("CDP endpoint must point to localhost".to_string());
    }

    Ok(format!("http://{}", authority))
}

fn capture_cdp_screenshot(ws_url: &str) -> Result<String, String> {
    let mut socket = connect_websocket(ws_url)?;
    websocket_send_json(
        &mut socket,
        &json!({
            "id": 1,
            "method": "Page.captureScreenshot",
            "params": {
                "format": "jpeg",
                "quality": 65,
                "captureBeyondViewport": false,
                "fromSurface": true
            }
        }),
    )?;

    loop {
        let message = websocket_read_text(&mut socket)?;
        let value: JsonValue = serde_json::from_str(&message)
            .map_err(|err| format!("failed to parse CDP message: {}", err))?;
        if value.get("id").and_then(JsonValue::as_i64) != Some(1) {
            continue;
        }
        if let Some(error) = value.get("error") {
            return Err(api_message(error, "CDP screenshot failed"));
        }
        return value
            .get("result")
            .and_then(|result| result.get("data"))
            .and_then(JsonValue::as_str)
            .map(ToString::to_string)
            .ok_or_else(|| "CDP screenshot returned no image data".to_string());
    }
}

fn connect_websocket(ws_url: &str) -> Result<TcpStream, String> {
    let endpoint = parse_ws_endpoint(ws_url)?;
    let addr = (endpoint.host.as_str(), endpoint.port)
        .to_socket_addrs()
        .map_err(|err| format!("failed to resolve CDP WebSocket host: {}", err))?
        .next()
        .ok_or_else(|| "failed to resolve CDP WebSocket host".to_string())?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_secs(5))
        .map_err(|err| format!("failed to connect CDP WebSocket: {}", err))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(10)))
        .map_err(|err| format!("failed to set WebSocket read timeout: {}", err))?;
    stream
        .set_write_timeout(Some(Duration::from_secs(5)))
        .map_err(|err| format!("failed to set WebSocket write timeout: {}", err))?;

    let request = format!(
        "GET {} HTTP/1.1\r\nHost: {}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n",
        endpoint.path, endpoint.host_header
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|err| format!("failed to write WebSocket handshake: {}", err))?;

    let mut reader = BufReader::new(
        stream
            .try_clone()
            .map_err(|err| format!("failed to clone WebSocket stream: {}", err))?,
    );
    let mut status_line = String::new();
    reader
        .read_line(&mut status_line)
        .map_err(|err| format!("failed to read WebSocket handshake: {}", err))?;
    if !status_line.contains(" 101 ") {
        return Err(format!(
            "CDP WebSocket handshake failed: {}",
            status_line.trim()
        ));
    }
    loop {
        let mut line = String::new();
        reader
            .read_line(&mut line)
            .map_err(|err| format!("failed to read WebSocket headers: {}", err))?;
        if line == "\r\n" || line.is_empty() {
            break;
        }
    }

    Ok(stream)
}

fn websocket_send_json(stream: &mut TcpStream, value: &JsonValue) -> Result<(), String> {
    let payload = serde_json::to_vec(value)
        .map_err(|err| format!("failed to serialize CDP request: {}", err))?;
    let mut frame = Vec::with_capacity(payload.len() + 16);
    frame.push(0x81);
    if payload.len() < 126 {
        frame.push(0x80 | payload.len() as u8);
    } else if payload.len() <= u16::MAX as usize {
        frame.push(0x80 | 126);
        frame.extend_from_slice(&(payload.len() as u16).to_be_bytes());
    } else {
        frame.push(0x80 | 127);
        frame.extend_from_slice(&(payload.len() as u64).to_be_bytes());
    }
    let mask = [1_u8, 2, 3, 4];
    frame.extend_from_slice(&mask);
    for (index, byte) in payload.iter().enumerate() {
        frame.push(byte ^ mask[index % 4]);
    }
    stream
        .write_all(&frame)
        .map_err(|err| format!("failed to send CDP WebSocket frame: {}", err))
}

fn websocket_read_text(stream: &mut TcpStream) -> Result<String, String> {
    let mut payload = Vec::new();
    loop {
        let mut header = [0_u8; 2];
        stream
            .read_exact(&mut header)
            .map_err(|err| format!("failed to read CDP WebSocket frame: {}", err))?;
        let fin = header[0] & 0x80 != 0;
        let opcode = header[0] & 0x0f;
        let masked = header[1] & 0x80 != 0;
        let mut len = (header[1] & 0x7f) as u64;
        if len == 126 {
            let mut bytes = [0_u8; 2];
            stream
                .read_exact(&mut bytes)
                .map_err(|err| format!("failed to read WebSocket length: {}", err))?;
            len = u16::from_be_bytes(bytes) as u64;
        } else if len == 127 {
            let mut bytes = [0_u8; 8];
            stream
                .read_exact(&mut bytes)
                .map_err(|err| format!("failed to read WebSocket length: {}", err))?;
            len = u64::from_be_bytes(bytes);
        }
        if len > 8 * 1024 * 1024 {
            return Err("CDP WebSocket frame is too large".to_string());
        }
        let mask = if masked {
            let mut bytes = [0_u8; 4];
            stream
                .read_exact(&mut bytes)
                .map_err(|err| format!("failed to read WebSocket mask: {}", err))?;
            Some(bytes)
        } else {
            None
        };
        let mut chunk = vec![0_u8; len as usize];
        stream
            .read_exact(&mut chunk)
            .map_err(|err| format!("failed to read WebSocket payload: {}", err))?;
        if let Some(mask) = mask {
            for (index, byte) in chunk.iter_mut().enumerate() {
                *byte ^= mask[index % 4];
            }
        }

        match opcode {
            0x1 | 0x0 => payload.extend_from_slice(&chunk),
            0x8 => return Err("CDP WebSocket closed".to_string()),
            0x9 | 0xa => continue,
            _ => continue,
        }
        if fin {
            return String::from_utf8(payload)
                .map_err(|err| format!("CDP WebSocket returned non-UTF8 text: {}", err));
        }
    }
}

fn parse_ws_endpoint(ws_url: &str) -> Result<HttpEndpoint, String> {
    let trimmed = ws_url.trim();
    let without_scheme = trimmed
        .strip_prefix("ws://")
        .ok_or_else(|| "CDP WebSocket URL must use ws://".to_string())?;
    let (authority, path) = without_scheme
        .split_once('/')
        .map(|(authority, path)| (authority, format!("/{}", path)))
        .ok_or_else(|| "CDP WebSocket URL is missing path".to_string())?;
    let (host, port) = authority
        .rsplit_once(':')
        .map(|(host, port)| {
            let parsed_port = port
                .parse::<u16>()
                .map_err(|_| format!("invalid CDP WebSocket port '{}'", port))?;
            Ok::<(String, u16), String>((host.to_string(), parsed_port))
        })
        .unwrap_or_else(|| Ok((authority.to_string(), 80)))?;
    let plain_host = host.trim_matches(|ch| ch == '[' || ch == ']');
    if !matches!(plain_host, "127.0.0.1" | "localhost" | "::1") {
        return Err("CDP WebSocket must point to localhost".to_string());
    }

    Ok(HttpEndpoint {
        host: plain_host.to_string(),
        port,
        host_header: authority.to_string(),
        path,
    })
}

fn socket_addr_from_url(url: &str) -> Result<SocketAddr, String> {
    let trimmed = url.trim();
    let without_scheme = trimmed
        .strip_prefix("http://")
        .or_else(|| trimmed.strip_prefix("https://"))
        .ok_or_else(|| format!("unsupported BitBrowser API URL '{}'", url))?;
    let authority = without_scheme
        .split('/')
        .next()
        .filter(|value| !value.is_empty())
        .ok_or_else(|| format!("missing host in BitBrowser API URL '{}'", url))?;
    let host_port = if authority.contains(':') {
        authority.to_string()
    } else if trimmed.starts_with("https://") {
        format!("{}:443", authority)
    } else {
        format!("{}:80", authority)
    };

    host_port
        .to_socket_addrs()
        .map_err(|err| format!("failed to resolve '{}': {}", host_port, err))?
        .next()
        .ok_or_else(|| format!("failed to resolve '{}'", host_port))
}

fn provider_capability_matrix() -> Vec<BrowserProviderCapability> {
    vec![
        BrowserProviderCapability {
            provider: "bitbrowser".to_string(),
            label: "BitBrowser".to_string(),
            implemented: true,
            production_ready: true,
            can_launch: true,
            can_close: true,
            provides_cdp_endpoint: true,
            requires_profile_id: true,
            supports_tiktok: true,
            risk_level: "stable".to_string(),
            notes: "Production default. Uses BitBrowser Local API and existing bitbrowser_profile_id.".to_string(),
        },
        BrowserProviderCapability {
            provider: "builtin_chromium".to_string(),
            label: "Built-in Chromium".to_string(),
            implemented: true,
            production_ready: true,
            can_launch: true,
            can_close: true,
            provides_cdp_endpoint: true,
            requires_profile_id: false,
            supports_tiktok: true,
            risk_level: "production_optional".to_string(),
            notes: "Production optional. Launches local Chromium with per-account user data and a temporary CDP port. It is not an equivalent replacement for BitBrowser fingerprint capabilities; BitBrowser remains the default recommendation.".to_string(),
        },
    ]
}

fn provider_capability(provider: &str) -> Option<BrowserProviderCapability> {
    provider_capability_matrix()
        .into_iter()
        .find(|capability| capability.provider == provider)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sync_request() -> SyncAccountsRequest {
        SyncAccountsRequest {
            prefix: "tiktok".to_string(),
            start: 101,
            end: 104,
            morning_start: 101,
            morning_end: 102,
            evening_start: 103,
            evening_end: 104,
            first_ip_group: 500,
        }
    }

    #[test]
    fn proxy_parser_masks_passwords_and_reports_line_numbers() {
        let proxy = parse_proxy("127.0.0.1:8080:user:secret").expect("proxy should parse");
        assert_eq!(proxy.host, "127.0.0.1");
        assert_eq!(proxy.port, 8080);
        assert_eq!(proxy.masked(), "127.0.0.1:8080:user:***");

        let parsed = parse_proxy_lines("\n# ignored\n127.0.0.1:8080:user:secret\nbad\n");
        assert_eq!(parsed.len(), 2);
        assert_eq!(parsed[0].as_ref().expect("valid line").0, 3);
        assert_eq!(parsed[1].as_ref().expect_err("invalid line").line_number, 4);
    }

    #[test]
    fn sync_request_validation_rejects_invalid_ranges() {
        let mut request = sync_request();
        assert!(validate_sync_request(&request).is_ok());

        request.start = 105;
        assert!(validate_sync_request(&request).is_err());

        request = sync_request();
        request.evening_end = 103;
        assert!(validate_sync_request(&request).is_err());
    }

    #[test]
    fn sync_account_builder_assigns_shift_and_ip_group() {
        let request = sync_request();
        let morning = build_account_input(101, "tiktok", "profile_morning", &request)
            .expect("morning account");
        let evening = build_account_input(103, "tiktok", "profile_evening", &request)
            .expect("evening account");

        assert_eq!(morning.id, "tiktok_101");
        assert_eq!(morning.ip_group, Some(500));
        assert_eq!(morning.active_hours, vec![[9.0, 12.0]]);
        assert_eq!(evening.id, "tiktok_103");
        assert_eq!(evening.ip_group, Some(500));
        assert_eq!(evening.active_hours, vec![[19.0, 23.0]]);
        assert_eq!(
            evening.bitbrowser_profile_id.as_deref(),
            Some("profile_evening")
        );
    }
}
