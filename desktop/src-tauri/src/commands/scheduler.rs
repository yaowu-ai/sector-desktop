use chrono::Local;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::{Read, Write};
use std::net::TcpStream;
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;
use tauri::State;

use crate::commands::config::{
    load_config, read_ai_comment_api_key_for_runtime, read_login_password_for_runtime,
};
use crate::paths::{normalize, project_paths, project_root, python_command_parts, ProjectPaths};
use crate::state::{AppState, SchedulerProcessState};

const SCHEDULER_HOST: &str = "127.0.0.1";
const SCHEDULER_PORT: u16 = 9601;
const TIKTOK_PLATFORM: &str = "tiktok";
const INSTAGRAM_PLATFORM: &str = "instagram";
const SCHEDULER_LOGIN_CREDENTIALS_ENV: &str = "AM_SCHEDULER_LOGIN_CREDENTIALS";
const AI_COMMENT_API_KEY_ENV: &str = "AM_AI_COMMENT_API_KEY";
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerStartResult {
    process_id: u32,
    command: Vec<String>,
    status: String,
}

#[derive(Debug, Serialize)]
struct SchedulerLoginCredential {
    username: String,
    password: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerProcessStatus {
    status: String,
    process_id: Option<u32>,
    command: Vec<String>,
    health_url: String,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerStopResult {
    status: String,
    process_id: Option<u32>,
    message: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ClearRunLockResult {
    path: String,
    cleared: bool,
    message: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerJob {
    id: String,
    account_id: Option<String>,
    next_run: Option<String>,
    status: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RunLockStatus {
    path: String,
    exists: bool,
    pid: Option<u32>,
    active: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct IpGroupConflict {
    ip_group: i64,
    left_account_id: String,
    right_account_id: String,
    left_active_hours: Vec<[f64; 2]>,
    right_active_hours: Vec<[f64; 2]>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerHealth {
    status: String,
    process_id: Option<u32>,
    jobs: Vec<SchedulerJob>,
    next_run: Option<String>,
    next_account_id: Option<String>,
    lock_held_externally: Option<bool>,
    today_schedule_count: usize,
    fires_per_day: i64,
    run_lock: RunLockStatus,
    ip_group_conflicts: Vec<IpGroupConflict>,
    error: Option<String>,
}

#[derive(Debug, Deserialize)]
struct RawHealthJob {
    id: String,
    next_run: Option<String>,
}

#[derive(Debug, Deserialize)]
struct RawHealth {
    status: String,
    process_id: Option<u32>,
    config_path: Option<String>,
    jobs: Vec<RawHealthJob>,
    lock_held_externally: Option<bool>,
}

#[derive(Debug, Deserialize)]
struct InstagramScheduleState {
    day: Option<String>,
    events: Vec<InstagramScheduleEvent>,
}

#[derive(Debug, Deserialize)]
struct InstagramScheduleEvent {
    id: String,
    account_id: Option<String>,
    at: Option<String>,
    status: Option<String>,
}

#[tauri::command]
pub fn start_scheduler(
    platform: Option<String>,
    state: State<'_, AppState>,
) -> Result<SchedulerStartResult, String> {
    let platform = scheduler_platform(platform);
    ensure_scheduler_supported(&platform)?;
    {
        let mut scheduler = state
            .scheduler_process
            .lock()
            .map_err(|_| "failed to lock scheduler state".to_string())?;
        if let Some(current) = scheduler.clone() {
            if process_is_alive(current.process_id) {
                if current.platform == platform {
                    return Ok(SchedulerStartResult {
                        process_id: current.process_id,
                        command: scheduler_command(&platform)?,
                        status: "running".to_string(),
                    });
                }
                return Err(format!(
                    "{} scheduler is already running (PID {}); stop it before starting {} scheduler",
                    current.platform, current.process_id, platform
                ));
            }
            *scheduler = None;
        }
    }

    let paths = project_paths()?;
    if platform == TIKTOK_PLATFORM {
        if let Ok(raw) = read_health_endpoint() {
            let process_id = raw.process_id.or_else(scheduler_port_process_id);
            if raw
                .config_path
                .as_deref()
                .map(|path| same_path(path, &paths.config_path))
                .unwrap_or(false)
            {
                if let Some(process_id) = process_id.filter(|pid| process_is_alive(*pid)) {
                    let mut scheduler = state
                        .scheduler_process
                        .lock()
                        .map_err(|_| "failed to lock scheduler state".to_string())?;
                    *scheduler = Some(SchedulerProcessState {
                        platform: platform.clone(),
                        process_id,
                    });
                    return Ok(SchedulerStartResult {
                        process_id,
                        command: scheduler_command_for_paths(&paths, &platform)?.0,
                        status: "running".to_string(),
                    });
                }
            }

            return Err(format!(
                "scheduler port {} is already occupied by an existing scheduler{}; stop it before starting the current configuration {}",
                SCHEDULER_PORT,
                process_id
                    .map(|pid| format!(" (PID {})", pid))
                    .unwrap_or_default(),
                paths.config_path
            ));
        }
    } else if read_health_endpoint().is_ok() {
        return Err(
            "TikTok scheduler is already running; stop it before starting Instagram scheduler"
                .to_string(),
        );
    }

    if platform == INSTAGRAM_PLATFORM {
        ensure_instagram_scheduler_accounts()?;
    }

    let login_credentials = if platform == TIKTOK_PLATFORM {
        scheduler_login_credentials()?
    } else {
        "{}".to_string()
    };
    let ai_comment_api_key = scheduler_ai_comment_api_key();
    let (command, current_dir) = scheduler_command_for_paths(&paths, &platform)?;
    let mut command_builder = Command::new(&command[0]);
    command_builder
        .args(&command[1..])
        .current_dir(&current_dir)
        .env("PYTHONUNBUFFERED", "1")
        .env(SCHEDULER_LOGIN_CREDENTIALS_ENV, login_credentials)
        .envs(ai_comment_api_key)
        .env(
            "AM_AUTO_CLOSE_PROFILE",
            if paths.auto_close_profile { "1" } else { "0" },
        )
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    hide_console_window(&mut command_builder);
    let child = command_builder.spawn().map_err(|err| {
        format!(
            "failed to start {} scheduler {:?} in {}: {}",
            platform,
            command,
            normalize(&current_dir),
            err
        )
    })?;

    let process_id = child.id();
    let mut scheduler = state
        .scheduler_process
        .lock()
        .map_err(|_| "failed to lock scheduler state".to_string())?;
    *scheduler = Some(SchedulerProcessState {
        platform,
        process_id,
    });

    Ok(SchedulerStartResult {
        process_id,
        command,
        status: "starting".to_string(),
    })
}

fn ensure_instagram_scheduler_accounts() -> Result<(), String> {
    let config = load_config()?;
    let accounts = config
        .accounts()
        .iter()
        .filter(|account| {
            account.enabled() && account.scheduled() && account.platform() == INSTAGRAM_PLATFORM
        })
        .collect::<Vec<_>>();
    if accounts.is_empty() {
        return Err("no enabled scheduled Instagram accounts are configured".to_string());
    }
    for account in accounts {
        if account.browser_provider() != "bitbrowser" {
            return Err(format!(
                "account '{}' Instagram scheduler requires BitBrowser",
                account.id()
            ));
        }
        if account
            .bitbrowser_profile_id()
            .map(str::trim)
            .filter(|profile| !profile.is_empty())
            .is_none()
        {
            return Err(format!(
                "account '{}' requires a BitBrowser profile id",
                account.id()
            ));
        }
    }
    Ok(())
}

fn scheduler_platform(platform: Option<String>) -> String {
    platform
        .unwrap_or_else(|| TIKTOK_PLATFORM.to_string())
        .trim()
        .to_ascii_lowercase()
}

fn ensure_scheduler_supported(platform: &str) -> Result<(), String> {
    if matches!(platform, TIKTOK_PLATFORM | INSTAGRAM_PLATFORM) {
        Ok(())
    } else {
        Err(format!(
            "platform '{}' does not have an executable scheduler yet",
            platform
        ))
    }
}

fn scheduler_ai_comment_api_key() -> HashMap<String, String> {
    let Ok(config) = load_config() else {
        return HashMap::new();
    };
    if !config.ai_comment_enabled() {
        return HashMap::new();
    }
    let provider = config.ai_comment_provider().to_string();
    let Ok(Some(api_key)) = read_ai_comment_api_key_for_runtime(Some(&provider)) else {
        return HashMap::new();
    };
    if api_key.trim().is_empty() {
        return HashMap::new();
    }
    HashMap::from([(AI_COMMENT_API_KEY_ENV.to_string(), api_key)])
}

fn scheduler_login_credentials() -> Result<String, String> {
    let config = load_config()?;
    let mut credentials = HashMap::new();

    for account in config.accounts().iter().filter(|account| {
        account.enabled()
            && account.scheduled()
            && account.platform() == "tiktok"
            && account.login_enabled()
    }) {
        let username = account
            .login_username()
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| {
                format!(
                    "account '{}' auto login is enabled but login.username is missing",
                    account.id()
                )
            })?;
        let password = read_login_password_for_runtime(account.id())?
            .filter(|value| !value.is_empty())
            .ok_or_else(|| {
                format!(
                    "account '{}' auto login is enabled but its saved password is missing or unreadable",
                    account.id()
                )
            })?;
        credentials.insert(
            account.id().to_string(),
            SchedulerLoginCredential {
                username: username.to_string(),
                password,
            },
        );
    }

    serde_json::to_string(&credentials)
        .map_err(|err| format!("failed to serialize scheduler login credentials: {}", err))
}

fn hide_console_window(command: &mut Command) {
    #[cfg(windows)]
    {
        command.creation_flags(CREATE_NO_WINDOW);
    }
}

fn hidden_command(program: &str) -> Command {
    let mut command = Command::new(program);
    hide_console_window(&mut command);
    command
}

#[tauri::command]
pub fn stop_scheduler(
    platform: Option<String>,
    state: State<'_, AppState>,
) -> Result<SchedulerStopResult, String> {
    let platform = scheduler_platform(platform);
    let mut process_id = {
        let scheduler = state
            .scheduler_process
            .lock()
            .map_err(|_| "failed to lock scheduler state".to_string())?;
        scheduler
            .as_ref()
            .filter(|current| current.platform == platform)
            .map(|current| current.process_id)
    };

    if process_id.is_none() && platform == TIKTOK_PLATFORM && read_health_endpoint().is_ok() {
        process_id = scheduler_port_process_id();
    }

    let Some(process_id) = process_id else {
        return Ok(SchedulerStopResult {
            status: "stopped".to_string(),
            process_id: None,
            message: format!("{} scheduler is not running", platform),
        });
    };

    if process_is_alive(process_id) {
        stop_process(process_id)?;
    }

    let mut scheduler = state
        .scheduler_process
        .lock()
        .map_err(|_| "failed to lock scheduler state".to_string())?;
    if scheduler
        .as_ref()
        .map(|current| current.platform == platform)
        .unwrap_or(false)
    {
        *scheduler = None;
    }

    Ok(SchedulerStopResult {
        status: "stopped".to_string(),
        process_id: Some(process_id),
        message: format!(
            "{} scheduler stopped; already triggered account runs may continue separately",
            platform
        ),
    })
}

#[tauri::command]
pub fn get_scheduler_process_status(
    platform: Option<String>,
    state: State<'_, AppState>,
) -> Result<SchedulerProcessStatus, String> {
    let platform = scheduler_platform(platform);
    if !matches!(platform.as_str(), TIKTOK_PLATFORM | INSTAGRAM_PLATFORM) {
        return Ok(stopped_scheduler_process_status(&platform, None));
    }

    let current = {
        let scheduler = state
            .scheduler_process
            .lock()
            .map_err(|_| "failed to lock scheduler state".to_string())?;
        scheduler.clone()
    };

    match current {
        Some(current) if current.platform == platform && process_is_alive(current.process_id) => {
            Ok(SchedulerProcessStatus {
                status: "running".to_string(),
                process_id: Some(current.process_id),
                command: scheduler_command(&platform)?,
                health_url: scheduler_health_url(&platform)?,
                error: None,
            })
        }
        Some(current) if current.platform == platform => {
            let mut scheduler = state
                .scheduler_process
                .lock()
                .map_err(|_| "failed to lock scheduler state".to_string())?;
            *scheduler = None;
            Ok(SchedulerProcessStatus {
                status: "stopped".to_string(),
                process_id: Some(current.process_id),
                command: scheduler_command(&platform)?,
                health_url: scheduler_health_url(&platform)?,
                error: Some("tracked scheduler process is no longer alive".to_string()),
            })
        }
        Some(current) if process_is_alive(current.process_id) => Ok(SchedulerProcessStatus {
            status: "stopped".to_string(),
            process_id: None,
            command: scheduler_command(&platform)?,
            health_url: scheduler_health_url(&platform)?,
            error: Some(format!(
                "{} scheduler is running (PID {})",
                current.platform, current.process_id
            )),
        }),
        Some(_) => {
            let mut scheduler = state
                .scheduler_process
                .lock()
                .map_err(|_| "failed to lock scheduler state".to_string())?;
            *scheduler = None;
            Ok(stopped_scheduler_process_status(&platform, None))
        }
        None if platform == TIKTOK_PLATFORM => match read_health_endpoint() {
            Ok(raw) => {
                let paths = project_paths()?;
                let discovered_pid = raw.process_id.or_else(scheduler_port_process_id);
                if raw
                    .config_path
                    .as_deref()
                    .map(|path| same_path(path, &paths.config_path))
                    .unwrap_or(false)
                {
                    if let Some(process_id) = discovered_pid.filter(|pid| process_is_alive(*pid)) {
                        let mut scheduler = state
                            .scheduler_process
                            .lock()
                            .map_err(|_| "failed to lock scheduler state".to_string())?;
                        *scheduler = Some(SchedulerProcessState {
                            platform: platform.clone(),
                            process_id,
                        });
                        return Ok(SchedulerProcessStatus {
                            status: "running".to_string(),
                            process_id: Some(process_id),
                            command: scheduler_command_for_paths(&paths, &platform)?.0,
                            health_url: scheduler_health_url(&platform)?,
                            error: None,
                        });
                    }
                }
                Ok(SchedulerProcessStatus {
                    status: "error".to_string(),
                    process_id: discovered_pid,
                    command: scheduler_command_for_paths(&paths, &platform)?.0,
                    health_url: scheduler_health_url(&platform)?,
                    error: Some(
                        "an untracked scheduler is using port 9601 with a different or unknown config path"
                            .to_string(),
                    ),
                })
            }
            Err(_) => Ok(SchedulerProcessStatus {
                status: "stopped".to_string(),
                process_id: None,
                command: scheduler_command(&platform)?,
                health_url: scheduler_health_url(&platform)?,
                error: None,
            }),
        },
        None => Ok(stopped_scheduler_process_status(&platform, None)),
    }
}

#[tauri::command]
pub fn get_scheduler_health(
    platform: Option<String>,
    state: State<'_, AppState>,
) -> Result<SchedulerHealth, String> {
    let platform = scheduler_platform(platform);
    let process = get_scheduler_process_status(Some(platform.clone()), state)?;
    let config = load_config()?;
    let fires_per_day = scheduler_fires_per_day(&config, &platform);
    let run_lock = read_run_lock_status()?;
    let ip_group_conflicts = detect_ip_group_conflicts(&platform)?;

    if platform == INSTAGRAM_PLATFORM {
        return instagram_scheduler_health(process, fires_per_day, run_lock, ip_group_conflicts);
    }

    if platform != TIKTOK_PLATFORM {
        return Ok(SchedulerHealth {
            status: "stopped".to_string(),
            process_id: None,
            jobs: vec![],
            next_run: None,
            next_account_id: None,
            lock_held_externally: None,
            today_schedule_count: 0,
            fires_per_day,
            run_lock,
            ip_group_conflicts,
            error: None,
        });
    }

    match read_health_endpoint() {
        Ok(raw) => {
            let expected_config_path = project_paths()?.config_path;
            if raw
                .config_path
                .as_deref()
                .map(|path| !same_path(path, &expected_config_path))
                .unwrap_or(false)
            {
                return Ok(SchedulerHealth {
                    status: "error".to_string(),
                    process_id: raw.process_id.or_else(scheduler_port_process_id),
                    jobs: vec![],
                    next_run: None,
                    next_account_id: None,
                    lock_held_externally: raw.lock_held_externally,
                    today_schedule_count: 0,
                    fires_per_day,
                    run_lock,
                    ip_group_conflicts,
                    error: Some(format!(
                        "scheduler is using {}, but the app is using {}; stop and restart the scheduler",
                        raw.config_path.as_deref().unwrap_or("an unknown config"),
                        expected_config_path
                    )),
                });
            }

            let scheduled_account_ids = config
                .accounts()
                .iter()
                .filter(|account| {
                    account.enabled() && account.scheduled() && account.platform() == "tiktok"
                })
                .map(|account| account.id().to_string())
                .collect::<HashSet<_>>();
            let mut jobs = raw
                .jobs
                .into_iter()
                .map(|job| SchedulerJob {
                    account_id: account_id_from_job_id(&job.id),
                    status: Some("scheduled".to_string()),
                    id: job.id,
                    next_run: job.next_run,
                })
                .filter(|job| {
                    job.account_id
                        .as_ref()
                        .map(|account_id| scheduled_account_ids.contains(account_id))
                        .unwrap_or(false)
                })
                .collect::<Vec<_>>();
            jobs.sort_by(|left, right| {
                left.next_run
                    .cmp(&right.next_run)
                    .then_with(|| left.id.cmp(&right.id))
            });

            let today = Local::now().format("%Y-%m-%d").to_string();
            let today_schedule_count = jobs
                .iter()
                .filter(|job| {
                    job.account_id.is_some()
                        && job
                            .next_run
                            .as_deref()
                            .map(|next_run| next_run.starts_with(&today))
                            .unwrap_or(false)
                })
                .count();
            let next_job = jobs
                .iter()
                .find(|job| job.account_id.is_some() && job.next_run.is_some());

            Ok(SchedulerHealth {
                status: if raw.status == "ok" {
                    "running".to_string()
                } else {
                    raw.status
                },
                process_id: process
                    .process_id
                    .or(raw.process_id)
                    .or_else(scheduler_port_process_id),
                next_run: next_job.and_then(|job| job.next_run.clone()),
                next_account_id: next_job.and_then(|job| job.account_id.clone()),
                jobs,
                lock_held_externally: raw.lock_held_externally,
                today_schedule_count,
                fires_per_day,
                run_lock,
                ip_group_conflicts,
                error: process.error,
            })
        }
        Err(error) => Ok(SchedulerHealth {
            status: if process.status == "running" {
                "error".to_string()
            } else {
                process.status
            },
            process_id: process.process_id,
            jobs: vec![],
            next_run: None,
            next_account_id: None,
            lock_held_externally: None,
            today_schedule_count: 0,
            fires_per_day,
            run_lock,
            ip_group_conflicts,
            error: Some(error),
        }),
    }
}

fn scheduler_fires_per_day(config: &crate::commands::config::ConfigSnapshot, platform: &str) -> i64 {
    if platform == TIKTOK_PLATFORM {
        return config.scheduler_fires_per_day().unwrap_or(3).max(0);
    }
    0
}

fn instagram_scheduler_health(
    process: SchedulerProcessStatus,
    fires_per_day: i64,
    run_lock: RunLockStatus,
    ip_group_conflicts: Vec<IpGroupConflict>,
) -> Result<SchedulerHealth, String> {
    let state_path = instagram_schedule_state_path()?;
    let state = read_instagram_schedule_state(&state_path).ok();
    let mut jobs = state
        .as_ref()
        .map(instagram_schedule_jobs)
        .unwrap_or_default();
    jobs.sort_by(|left, right| {
        left.next_run
            .cmp(&right.next_run)
            .then_with(|| left.id.cmp(&right.id))
    });
    let next_job = jobs
        .iter()
        .find(|job| job.account_id.is_some() && job.next_run.is_some());
    let today = Local::now().format("%Y-%m-%d").to_string();
    let today_schedule_count = state
        .as_ref()
        .filter(|state| state.day.as_deref() == Some(today.as_str()))
        .map(|state| state.events.len())
        .unwrap_or(0);

    Ok(SchedulerHealth {
        status: process.status.clone(),
        process_id: process.process_id,
        next_run: next_job.and_then(|job| job.next_run.clone()),
        next_account_id: next_job.and_then(|job| job.account_id.clone()),
        jobs,
        lock_held_externally: Some(run_lock.active),
        today_schedule_count,
        fires_per_day,
        run_lock,
        ip_group_conflicts,
        error: process.error,
    })
}

fn read_instagram_schedule_state(path: &Path) -> Result<InstagramScheduleState, String> {
    if !path.exists() {
        return Err("Instagram schedule state does not exist yet".to_string());
    }
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read {}: {}", normalize(path), err))?;
    serde_json::from_str::<InstagramScheduleState>(&raw)
        .map_err(|err| format!("failed to parse {}: {}", normalize(path), err))
}

fn instagram_schedule_jobs(state: &InstagramScheduleState) -> Vec<SchedulerJob> {
    state
        .events
        .iter()
        .filter(|event| {
            matches!(
                event.status.as_deref().unwrap_or("pending"),
                "pending" | "running"
            )
        })
        .map(|event| SchedulerJob {
            id: format!("ins_schedule::{}", event.id),
            account_id: event.account_id.clone(),
            next_run: event.at.clone(),
            status: Some(instagram_schedule_status(event.status.as_deref())),
        })
        .collect()
}

fn instagram_schedule_status(status: Option<&str>) -> String {
    match status.unwrap_or("pending") {
        "running" => "running",
        "pending" => "scheduled",
        "done" => "done",
        "skipped" | "missed" => "skipped",
        "error" | "blocked" | "interrupted" => "error",
        other => other,
    }
    .to_string()
}

#[tauri::command]
pub fn clear_run_lock() -> Result<ClearRunLockResult, String> {
    let paths = project_paths()?;
    let path = std::path::PathBuf::from(&paths.lock_file_path);
    if !path.exists() {
        return Ok(ClearRunLockResult {
            path: paths.lock_file_path,
            cleared: false,
            message: "run.lock does not exist".to_string(),
        });
    }

    let lock = read_run_lock_status()?;
    if lock.active {
        return Err(format!(
            "run.lock is held by active PID {}; stop the process before clearing {}",
            lock.pid
                .map(|pid| pid.to_string())
                .unwrap_or_else(|| "unknown".to_string()),
            lock.path
        ));
    }

    fs::remove_file(&path)
        .map_err(|err| format!("failed to remove {}: {}", paths.lock_file_path, err))?;
    Ok(ClearRunLockResult {
        path: paths.lock_file_path,
        cleared: true,
        message: "stale run.lock cleared".to_string(),
    })
}

fn scheduler_command(platform: &str) -> Result<Vec<String>, String> {
    Ok(scheduler_command_for_paths(&project_paths()?, platform)?.0)
}

fn scheduler_command_for_paths(
    paths: &ProjectPaths,
    platform: &str,
) -> Result<(Vec<String>, PathBuf), String> {
    ensure_scheduler_supported(platform)?;
    if paths.runtime_mode == "bundled" {
        let runtime_path = PathBuf::from(&paths.runtime_path);
        if !runtime_path.is_file() {
            return Err(format!(
                "bundled runtime is not readable: {}",
                paths.runtime_path
            ));
        }
        let manifest_path = std::path::PathBuf::from(&paths.runtime_manifest_path);
        if !manifest_path.is_file() {
            return Err(format!(
                "bundled runtime manifest is not readable: {}",
                paths.runtime_manifest_path
            ));
        }
        let mut command = vec![
            paths.runtime_path.clone(),
        ];
        if platform == INSTAGRAM_PLATFORM {
            command.push("instagram-scheduler".to_string());
            command.push("--config".to_string());
            command.push(paths.config_path.clone());
            command.push("--data-dir".to_string());
            command.push(paths.data_dir.clone());
            command.push("--schedule".to_string());
        } else {
            command.push("scheduler".to_string());
            command.push("--config".to_string());
            command.push(paths.config_path.clone());
            command.push("--data-dir".to_string());
            command.push(paths.data_dir.clone());
            command.push("--host".to_string());
            command.push(SCHEDULER_HOST.to_string());
            command.push("--port".to_string());
            command.push(SCHEDULER_PORT.to_string());
        }
        let current_dir = runtime_path
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(|| PathBuf::from("."));
        return Ok((command, current_dir));
    }

    let mut command = python_command_parts()?;
    if platform == INSTAGRAM_PLATFORM {
        command.push("-m".to_string());
        command.push("platforms.instagram_runner".to_string());
        command.push("--config".to_string());
        command.push(paths.config_path.clone());
        command.push("--data-dir".to_string());
        command.push(paths.data_dir.clone());
        command.push("--schedule".to_string());
    } else {
        command.push("src/scheduler.py".to_string());
        command.push("--config".to_string());
        command.push(paths.config_path.clone());
        command.push("--data-dir".to_string());
        command.push(paths.data_dir.clone());
    }
    Ok((command, project_root()?))
}

fn health_url() -> String {
    format!("http://{}:{}/health", SCHEDULER_HOST, SCHEDULER_PORT)
}

fn scheduler_health_url(platform: &str) -> Result<String, String> {
    if platform == INSTAGRAM_PLATFORM {
        let path = instagram_schedule_state_path()?;
        return Ok(normalize(&path));
    }
    Ok(health_url())
}

fn instagram_schedule_state_path() -> Result<PathBuf, String> {
    Ok(PathBuf::from(project_paths()?.data_dir)
        .join("ins")
        .join("schedule_state.json"))
}

fn stopped_scheduler_process_status(
    platform: &str,
    error: Option<String>,
) -> SchedulerProcessStatus {
    SchedulerProcessStatus {
        status: "stopped".to_string(),
        process_id: None,
        command: scheduler_command(platform).unwrap_or_default(),
        health_url: scheduler_health_url(platform).unwrap_or_default(),
        error,
    }
}

fn read_health_endpoint() -> Result<RawHealth, String> {
    let address = format!("{}:{}", SCHEDULER_HOST, SCHEDULER_PORT);
    let mut stream = TcpStream::connect(address.as_str())
        .map_err(|err| format!("scheduler health endpoint is not reachable: {}", err))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(2)))
        .map_err(|err| format!("failed to set scheduler read timeout: {}", err))?;
    stream
        .set_write_timeout(Some(Duration::from_secs(2)))
        .map_err(|err| format!("failed to set scheduler write timeout: {}", err))?;

    let request = format!(
        "GET /health HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n",
        address
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|err| format!("failed to request scheduler health: {}", err))?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|err| format!("failed to read scheduler health response: {}", err))?;

    let (headers, body) = response
        .split_once("\r\n\r\n")
        .ok_or_else(|| "scheduler health response is malformed".to_string())?;
    if !headers.starts_with("HTTP/1.1 200") && !headers.starts_with("HTTP/1.0 200") {
        return Err(format!(
            "scheduler health returned non-200 response: {}",
            headers.lines().next().unwrap_or("unknown")
        ));
    }

    serde_json::from_str::<RawHealth>(body)
        .map_err(|err| format!("failed to parse scheduler health response: {}", err))
}

fn same_path(left: &str, right: &str) -> bool {
    let normalize_value = |value: &str| {
        let normalized = value.replace('\\', "/").trim_end_matches('/').to_string();
        #[cfg(windows)]
        {
            normalized.to_lowercase()
        }
        #[cfg(not(windows))]
        {
            normalized
        }
    };
    normalize_value(left) == normalize_value(right)
}

fn scheduler_port_process_id() -> Option<u32> {
    #[cfg(windows)]
    {
        let output = hidden_command("netstat")
            .args(["-ano", "-p", "tcp"])
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .output()
            .ok()?;
        if !output.status.success() {
            return None;
        }
        for line in String::from_utf8_lossy(&output.stdout).lines() {
            let columns = line.split_whitespace().collect::<Vec<_>>();
            if columns.len() >= 5
                && columns[1].ends_with(&format!(":{}", SCHEDULER_PORT))
                && columns[3].eq_ignore_ascii_case("LISTENING")
            {
                if let Ok(process_id) = columns[4].parse::<u32>() {
                    return Some(process_id);
                }
            }
        }
        None
    }

    #[cfg(not(windows))]
    {
        let output = hidden_command("lsof")
            .args(["-t", &format!("-iTCP:{}", SCHEDULER_PORT), "-sTCP:LISTEN"])
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .output()
            .ok()?;
        String::from_utf8_lossy(&output.stdout)
            .lines()
            .find_map(|line| line.trim().parse::<u32>().ok())
    }
}

fn read_run_lock_status() -> Result<RunLockStatus, String> {
    let paths = project_paths()?;
    let lock_path = std::path::PathBuf::from(&paths.lock_file_path);
    if !lock_path.exists() {
        return Ok(RunLockStatus {
            path: paths.lock_file_path,
            exists: false,
            pid: None,
            active: false,
        });
    }

    let raw_pid = std::fs::read_to_string(&lock_path).unwrap_or_default();
    let pid = raw_pid.trim().parse::<u32>().ok();
    Ok(RunLockStatus {
        path: paths.lock_file_path,
        exists: true,
        pid,
        active: pid.map(process_is_alive).unwrap_or(false),
    })
}

fn detect_ip_group_conflicts(platform: &str) -> Result<Vec<IpGroupConflict>, String> {
    let config = load_config()?;
    let accounts = config
        .accounts()
        .iter()
        .filter(|account| {
            account.enabled() && account.scheduled() && account.platform() == platform
        })
        .collect::<Vec<_>>();
    let mut conflicts = Vec::new();

    for left_index in 0..accounts.len() {
        for right_index in (left_index + 1)..accounts.len() {
            let left = accounts[left_index];
            let right = accounts[right_index];
            let (Some(left_group), Some(right_group)) = (left.ip_group(), right.ip_group()) else {
                continue;
            };
            if left_group != right_group {
                continue;
            }
            if active_hours_overlap(left.active_hours(), right.active_hours()) {
                conflicts.push(IpGroupConflict {
                    ip_group: left_group,
                    left_account_id: left.id().to_string(),
                    right_account_id: right.id().to_string(),
                    left_active_hours: left.active_hours().to_vec(),
                    right_active_hours: right.active_hours().to_vec(),
                });
            }
        }
    }

    Ok(conflicts)
}

fn active_hours_overlap(left: &[[f64; 2]], right: &[[f64; 2]]) -> bool {
    left.iter().any(|left_range| {
        right
            .iter()
            .any(|right_range| left_range[0] < right_range[1] && right_range[0] < left_range[1])
    })
}

fn account_id_from_job_id(job_id: &str) -> Option<String> {
    let rest = job_id.strip_prefix("fire_")?;
    let parts = rest.split('_').collect::<Vec<_>>();
    if parts.len() < 3 {
        return None;
    }
    Some(parts[..parts.len() - 2].join("_"))
}

fn process_is_alive(process_id: u32) -> bool {
    #[cfg(windows)]
    {
        let Ok(output) = hidden_command("tasklist")
            .args([
                "/FI",
                &format!("PID eq {}", process_id),
                "/FO",
                "CSV",
                "/NH",
            ])
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .output()
        else {
            return false;
        };
        if !output.status.success() {
            return false;
        }
        String::from_utf8_lossy(&output.stdout).contains(&process_id.to_string())
    }

    #[cfg(not(windows))]
    {
        hidden_command("kill")
            .args(["-0", &process_id.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
    }
}

fn stop_process(process_id: u32) -> Result<(), String> {
    #[cfg(windows)]
    {
        let status = hidden_command("taskkill")
            .args(["/PID", &process_id.to_string(), "/T", "/F"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map_err(|err| format!("failed to stop scheduler process {}: {}", process_id, err))?;
        if !status.success() {
            return Err(format!(
                "taskkill failed for scheduler process {}",
                process_id
            ));
        }
        Ok(())
    }

    #[cfg(not(windows))]
    {
        let status = hidden_command("kill")
            .arg(process_id.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map_err(|err| format!("failed to stop scheduler process {}: {}", process_id, err))?;
        if !status.success() {
            return Err(format!("kill failed for scheduler process {}", process_id));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::{account_id_from_job_id, same_path};

    #[test]
    fn parses_account_ids_with_underscores() {
        assert_eq!(
            account_id_from_job_id("fire_tiktok_109_20260803_090400").as_deref(),
            Some("tiktok_109")
        );
        assert_eq!(account_id_from_job_id("daily_reschedule"), None);
    }

    #[test]
    fn compares_normalized_config_paths() {
        assert!(same_path(
            "C:\\星域\\config\\accounts.yaml",
            "C:/星域/config/accounts.yaml"
        ));
        assert!(!same_path(
            "C:/星域/config/accounts.yaml",
            "D:/星域/config/accounts.yaml"
        ));
    }
}
