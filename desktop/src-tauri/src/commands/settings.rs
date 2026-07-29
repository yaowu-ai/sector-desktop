use serde::{Deserialize, Serialize};
use std::process::{Command, Stdio};
use tauri::State;

use crate::commands::bitbrowser::auto_configure_chromium_executable;
use crate::commands::config::{load_config, NotifySettingsPayload};
use crate::paths::{
    effective_bitbrowser_api_url, effective_chromium_executable, load_local_app_settings,
    project_paths, python_command_parts, save_local_app_settings, AppInitializationStatus,
    LocalAppSettings,
};
use crate::security::redact_text;
use crate::state::AppState;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemSettingsPayload {
    runtime_mode: Option<String>,
    project_root: String,
    python_executable: String,
    default_browser_provider: String,
    chromium_executable: String,
    bitbrowser_api_url: String,
    data_dir: String,
    config_path: String,
    comments_path: String,
    brand_comments_path: String,
    runtime_path: Option<String>,
    runtime_manifest_path: Option<String>,
    auto_close_profile: bool,
    log_poll_interval_seconds: u64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemSettingsSnapshot {
    settings_path: String,
    runtime_mode: String,
    project_root: String,
    python_executable: String,
    default_browser_provider: String,
    chromium_executable: String,
    bitbrowser_api_url: String,
    data_dir: String,
    logs_dir: String,
    config_path: String,
    comments_path: String,
    brand_comments_path: String,
    runtime_path: String,
    runtime_manifest_path: String,
    runtime_version: Option<String>,
    initialized_app_version: Option<String>,
    auto_close_profile: bool,
    log_poll_interval_seconds: u64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NotifyTestResult {
    notify_type: String,
    message: String,
}

#[tauri::command]
pub fn load_system_settings() -> Result<SystemSettingsSnapshot, String> {
    system_settings_snapshot()
}

#[tauri::command]
pub fn get_initialization_status(
    state: State<'_, AppState>,
) -> Result<Option<AppInitializationStatus>, String> {
    let status = state
        .initialization_status
        .lock()
        .map_err(|_| "failed to lock initialization state".to_string())?;
    Ok(status.clone())
}

#[tauri::command]
pub fn save_system_settings(
    payload: SystemSettingsPayload,
) -> Result<SystemSettingsSnapshot, String> {
    if payload.log_poll_interval_seconds == 0 || payload.log_poll_interval_seconds > 60 {
        return Err("log polling interval must be between 1 and 60 seconds".to_string());
    }

    let existing = load_local_app_settings().unwrap_or_default();
    let default_browser_provider = normalize_browser_provider(&payload.default_browser_provider)?;
    let mut chromium_executable = blank_to_none(payload.chromium_executable);
    if chromium_executable.is_none()
        && default_browser_provider.as_deref() == Some("builtin_chromium")
    {
        chromium_executable = Some(auto_configure_chromium_executable()?);
    }

    let settings = LocalAppSettings {
        runtime_mode: payload
            .runtime_mode
            .and_then(blank_to_none)
            .or(existing.runtime_mode),
        project_root: blank_to_none(payload.project_root),
        python_executable: blank_to_none(payload.python_executable),
        default_browser_provider,
        chromium_executable,
        bitbrowser_api_url: blank_to_none(payload.bitbrowser_api_url),
        data_dir: blank_to_none(payload.data_dir),
        config_path: blank_to_none(payload.config_path),
        comments_path: blank_to_none(payload.comments_path),
        brand_comments_path: blank_to_none(payload.brand_comments_path),
        runtime_path: payload
            .runtime_path
            .and_then(blank_to_none)
            .or(existing.runtime_path),
        runtime_manifest_path: payload
            .runtime_manifest_path
            .and_then(blank_to_none)
            .or(existing.runtime_manifest_path),
        runtime_version: existing.runtime_version,
        initialized_app_version: existing.initialized_app_version,
        auto_close_profile: Some(payload.auto_close_profile),
        log_poll_interval_seconds: Some(payload.log_poll_interval_seconds),
    };
    save_local_app_settings(&settings)?;
    system_settings_snapshot()
}

#[tauri::command]
pub fn test_notification(payload: NotifySettingsPayload) -> Result<NotifyTestResult, String> {
    let notify_type = payload.notify_type.trim();
    if !matches!(notify_type, "serverchan" | "bark" | "webhook") {
        return Err("notify.type must be serverchan, bark, or webhook".to_string());
    }

    let mut envs = vec![
        ("AM_NOTIFY_TYPE".to_string(), notify_type.to_string()),
        (
            "AM_NOTIFY_TITLE".to_string(),
            "Account Matrix notification test".to_string(),
        ),
        (
            "AM_NOTIFY_MESSAGE".to_string(),
            "Desktop notification test sent successfully.".to_string(),
        ),
    ];
    let mut redactions = Vec::new();

    match notify_type {
        "serverchan" => {
            let sendkey = payload
                .serverchan
                .as_ref()
                .and_then(|value| value.sendkey.as_deref())
                .and_then(non_empty_ref)
                .ok_or_else(|| "ServerChan sendkey is required".to_string())?;
            redactions.push(sendkey.to_string());
            envs.push(("AM_NOTIFY_SENDKEY".to_string(), sendkey.to_string()));
        }
        "bark" => {
            let url = payload
                .bark
                .as_ref()
                .and_then(|value| value.url.as_deref())
                .and_then(non_empty_ref)
                .ok_or_else(|| "Bark URL is required".to_string())?;
            redactions.push(url.to_string());
            envs.push(("AM_NOTIFY_URL".to_string(), url.to_string()));
        }
        "webhook" => {
            let url = payload
                .webhook
                .as_ref()
                .and_then(|value| value.url.as_deref())
                .and_then(non_empty_ref)
                .ok_or_else(|| "Webhook URL is required".to_string())?;
            redactions.push(url.to_string());
            envs.push(("AM_NOTIFY_URL".to_string(), url.to_string()));
        }
        _ => unreachable!(),
    }

    let command = notification_test_command()?;
    let output = Command::new(&command[0])
        .args(&command[1..])
        .env("PYTHONUNBUFFERED", "1")
        .envs(envs)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|err| format!("failed to start notification test: {}", err))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let detail = if stderr.is_empty() { stdout } else { stderr };
        return Err(redact_text(&detail, &redactions));
    }

    Ok(NotifyTestResult {
        notify_type: notify_type.to_string(),
        message: "notification test sent".to_string(),
    })
}

fn system_settings_snapshot() -> Result<SystemSettingsSnapshot, String> {
    let paths = project_paths()?;
    let local_settings = load_local_app_settings().unwrap_or_default();
    let bitbrowser_api_url = local_settings
        .bitbrowser_api_url
        .as_deref()
        .and_then(non_empty_ref)
        .map(ToString::to_string)
        .or_else(|| {
            load_config()
                .ok()
                .and_then(|snapshot| snapshot.bitbrowser_api_url())
        })
        .unwrap_or_else(|| effective_bitbrowser_api_url(&local_settings));

    Ok(SystemSettingsSnapshot {
        settings_path: paths.settings_path,
        runtime_mode: paths.runtime_mode,
        project_root: paths.project_root,
        python_executable: paths.python_executable,
        default_browser_provider: paths.default_browser_provider,
        bitbrowser_api_url,
        chromium_executable: local_settings
            .chromium_executable
            .as_deref()
            .and_then(non_empty_ref)
            .map(ToString::to_string)
            .or_else(|| {
                load_config()
                    .ok()
                    .and_then(|snapshot| snapshot.chromium_executable())
            })
            .unwrap_or_else(|| effective_chromium_executable(&local_settings)),
        data_dir: paths.data_dir,
        logs_dir: paths.logs_dir,
        config_path: paths.config_path,
        comments_path: paths.comments_path,
        brand_comments_path: paths.brand_comments_path,
        runtime_path: paths.runtime_path,
        runtime_manifest_path: paths.runtime_manifest_path,
        runtime_version: paths.runtime_version,
        initialized_app_version: local_settings.initialized_app_version,
        auto_close_profile: paths.auto_close_profile,
        log_poll_interval_seconds: paths.log_poll_interval_seconds,
    })
}

fn notification_test_command() -> Result<Vec<String>, String> {
    let mut command = python_command_parts()?;
    command.push("-c".to_string());
    command.push(NOTIFICATION_TEST_SCRIPT.to_string());
    Ok(command)
}

const NOTIFICATION_TEST_SCRIPT: &str = r#"
import json
import os
import sys
import urllib.parse
import urllib.request

kind = os.environ["AM_NOTIFY_TYPE"]
title = os.environ["AM_NOTIFY_TITLE"]
message = os.environ["AM_NOTIFY_MESSAGE"]
headers = {}
data = None

if kind == "serverchan":
    sendkey = os.environ["AM_NOTIFY_SENDKEY"]
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    data = urllib.parse.urlencode({"title": title, "desp": message}).encode("utf-8")
    headers["Content-Type"] = "application/x-www-form-urlencoded"
elif kind == "bark":
    base = os.environ["AM_NOTIFY_URL"].rstrip("/")
    url = f"{base}/{urllib.parse.quote(title)}/{urllib.parse.quote(message)}"
else:
    url = os.environ["AM_NOTIFY_URL"]
    data = json.dumps({"title": title, "message": message}).encode("utf-8")
    headers["Content-Type"] = "application/json"

request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
        print(f"sent {kind} notification")
except Exception as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(1)
"#;

fn blank_to_none(value: String) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

fn non_empty_ref(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed)
    }
}

fn normalize_browser_provider(value: &str) -> Result<Option<String>, String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Ok(Some("bitbrowser".to_string()));
    }
    if matches!(trimmed, "bitbrowser" | "builtin_chromium") {
        Ok(Some(trimmed.to_string()))
    } else {
        Err("default browser provider must be bitbrowser or builtin_chromium".to_string())
    }
}
