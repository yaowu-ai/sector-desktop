use chrono::Local;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{BufRead, BufReader};
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tauri::State;

use crate::commands::bitbrowser::{auto_configure_chromium_executable, check_bitbrowser_api};
use crate::commands::config::{
    ensure_account_ids_belong_to_platform, ensure_platform_capability, load_config,
    normalize_platform, read_ai_comment_api_key_for_runtime, read_login_password_for_runtime,
};
use crate::paths::{normalize, project_paths, project_root, python_command_parts, ProjectPaths};
use crate::security::redact_line;
use crate::state::{AppState, AuthInterventionState, BrowserPreviewState, RunState};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;
const AI_COMMENT_API_KEY_ENV: &str = "AM_AI_COMMENT_API_KEY";

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PythonRunRequest {
    script_name: String,
    args: Vec<String>,
    mode: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlatformTaskRequest {
    platform: String,
    task_type: String,
    account_ids: Vec<String>,
    mode: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GmailSetupRequest {
    browser_name: String,
    email: Option<String>,
    password: Option<String>,
    new_password: Option<String>,
    query: Option<String>,
    email_file: Option<String>,
    timeout_seconds: i64,
    terms_timeout_seconds: i64,
    keep_open_on_error: bool,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ProcessStartResult {
    process_id: Option<u32>,
    command: Vec<String>,
    status: String,
    task_type: String,
    account_id: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ScriptRunResult {
    account_id: String,
    command: Vec<String>,
    exit_code: Option<i32>,
    stdout: String,
    stderr: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessStatus {
    status: String,
    process_id: Option<u32>,
    task_type: Option<String>,
    account_id: Option<String>,
    started_at: Option<String>,
    ended_at: Option<String>,
    error: Option<String>,
    command: Vec<String>,
    queued_accounts: Vec<String>,
    completed_accounts: Vec<String>,
    browser_preview: Option<BrowserPreview>,
    auth_intervention: Option<AuthIntervention>,
    stdout_length: usize,
    stderr_length: usize,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct BrowserPreview {
    account_id: String,
    profile_id: String,
    cdp_endpoint: String,
    opened_at: String,
}

#[derive(Debug, Deserialize)]
struct BrowserPreviewEvent {
    event: String,
    account_id: String,
    profile_id: Option<String>,
    cdp_endpoint: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AuthIntervention {
    account_id: String,
    platform: String,
    state: String,
    detail: String,
    reason: String,
    url: Option<String>,
    checked_at: String,
}

#[derive(Debug, Deserialize)]
struct AuthEvent {
    event: String,
    account_id: String,
    platform: String,
    state: String,
    detail: Option<String>,
    intervention_required: Option<bool>,
    reason: Option<String>,
    url: Option<String>,
    checked_at: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessLogRequest {
    offset: usize,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessLogChunk {
    offset: usize,
    next_offset: usize,
    content: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct StopResult {
    status: String,
    process_id: Option<u32>,
    message: String,
}

#[tauri::command]
pub fn run_python_script(
    request: PythonRunRequest,
    state: State<'_, AppState>,
) -> Result<ProcessStartResult, String> {
    validate_script_name(&request.script_name)?;
    validate_args(&request.args)?;
    validate_script_capability(&request.script_name, &request.args)?;
    let args = std::iter::once(format!("src/{}", request.script_name))
        .chain(request.args)
        .collect::<Vec<_>>();
    start_single_python_process(
        state.current_run.clone(),
        args,
        request.mode.unwrap_or_else(|| "script".to_string()),
        None,
        false,
    )
}

#[tauri::command]
pub fn run_one_account(
    account_id: String,
    state: State<'_, AppState>,
) -> Result<ProcessStartResult, String> {
    validate_account_id(&account_id)?;
    run_platform_task_inner(
        state.current_run.clone(),
        PlatformTaskRequest {
            platform: "tiktok".to_string(),
            task_type: "fyp".to_string(),
            account_ids: vec![account_id],
            mode: Some("single".to_string()),
        },
    )
}

#[tauri::command]
pub fn run_account_script(
    account_id: String,
    state: State<'_, AppState>,
) -> Result<ProcessStartResult, String> {
    run_one_account(account_id, state)
}

#[tauri::command]
pub fn run_all_accounts(state: State<'_, AppState>) -> Result<ProcessStartResult, String> {
    run_platform_task_inner(
        state.current_run.clone(),
        PlatformTaskRequest {
            platform: "tiktok".to_string(),
            task_type: "fyp".to_string(),
            account_ids: Vec::new(),
            mode: Some("all".to_string()),
        },
    )
}

#[tauri::command]
pub fn run_selected_accounts(
    account_ids: Vec<String>,
    state: State<'_, AppState>,
) -> Result<ProcessStartResult, String> {
    if account_ids.is_empty() {
        return Err("account_ids must contain at least one account".to_string());
    }
    run_platform_task_inner(
        state.current_run.clone(),
        PlatformTaskRequest {
            platform: "tiktok".to_string(),
            task_type: "fyp".to_string(),
            account_ids,
            mode: Some("selected".to_string()),
        },
    )
}

#[tauri::command]
pub fn run_platform_task(
    request: PlatformTaskRequest,
    state: State<'_, AppState>,
) -> Result<ProcessStartResult, String> {
    run_platform_task_inner(state.current_run.clone(), request)
}

#[tauri::command]
pub fn run_tiktok_register(
    account_id: String,
    state: State<'_, AppState>,
) -> Result<ProcessStartResult, String> {
    let account_id = account_id.trim().to_string();
    validate_account_id(&account_id)?;
    ensure_tiktok_register_account(&account_id)?;

    {
        let mut run = state
            .current_run
            .lock()
            .map_err(|_| "failed to lock process state".to_string())?;
        ensure_no_current_process(&run)?;
        reset_run_state(&mut run, "tiktok_register");
    }

    spawn_account_process(
        state.current_run.clone(),
        account_id,
        "tiktok_register".to_string(),
    )
}

#[tauri::command]
pub fn run_tiktok_register_batch(
    account_ids: Vec<String>,
    state: State<'_, AppState>,
) -> Result<ProcessStartResult, String> {
    let account_ids = account_ids
        .into_iter()
        .map(|account_id| account_id.trim().to_string())
        .filter(|account_id| !account_id.is_empty())
        .collect::<Vec<_>>();
    if account_ids.is_empty() {
        return Err("accountIds must contain at least one account".to_string());
    }
    for account_id in &account_ids {
        validate_account_id(account_id)?;
        ensure_tiktok_register_account(account_id)?;
    }

    let mut queue = account_ids.clone();
    let first = queue.remove(0);
    let remaining = queue;

    {
        let mut run = state
            .current_run
            .lock()
            .map_err(|_| "failed to lock process state".to_string())?;
        ensure_no_current_process(&run)?;
        reset_run_state(&mut run, "tiktok_register");
        run.queue = remaining;
    }

    spawn_account_process(
        state.current_run.clone(),
        first,
        "tiktok_register".to_string(),
    )
}

#[tauri::command]
pub fn get_current_run_status(state: State<'_, AppState>) -> Result<ProcessStatus, String> {
    let run = state
        .current_run
        .lock()
        .map_err(|_| "failed to lock process state".to_string())?;

    Ok(ProcessStatus {
        status: run.status.clone(),
        process_id: run.process_id,
        task_type: run.task_type.clone(),
        account_id: run.account_id.clone(),
        started_at: run.started_at.clone(),
        ended_at: run.ended_at.clone(),
        error: run.error.clone(),
        command: run.command.clone(),
        queued_accounts: run.queue.clone(),
        completed_accounts: run.completed_accounts.clone(),
        browser_preview: run.browser_preview.clone().map(Into::into),
        auth_intervention: run.auth_intervention.clone().map(Into::into),
        stdout_length: run.stdout.len(),
        stderr_length: run.stderr.len(),
    })
}

#[tauri::command]
pub fn get_stdout_chunk(
    request: ProcessLogRequest,
    state: State<'_, AppState>,
) -> Result<ProcessLogChunk, String> {
    read_process_buffer(state.current_run.clone(), request.offset, true)
}

#[tauri::command]
pub fn get_stderr_chunk(
    request: ProcessLogRequest,
    state: State<'_, AppState>,
) -> Result<ProcessLogChunk, String> {
    read_process_buffer(state.current_run.clone(), request.offset, false)
}

#[tauri::command]
pub fn run_gmail_setup(
    request: GmailSetupRequest,
    state: State<'_, AppState>,
) -> Result<ProcessStartResult, String> {
    let browser_name = request.browser_name.trim();
    if browser_name.is_empty() {
        return Err("browserName is required".to_string());
    }
    validate_safe_text(browser_name, "browserName")?;

    let timeout_seconds = request.timeout_seconds.clamp(1, 600);
    let terms_timeout_seconds = request.terms_timeout_seconds.clamp(1, 600);
    let query = request
        .query
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or("gmail");
    validate_safe_text(query, "query")?;

    let email_file = request
        .email_file
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty());
    let email = request
        .email
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty());
    let password = request.password.as_deref();
    let new_password = request.new_password.as_deref();

    if email_file.is_some() {
        if email.is_some() || option_has_text(password) || option_has_text(new_password) {
            return Err(
                "batch mode uses --file; email/password/newPassword must be empty".to_string(),
            );
        }
    } else if option_has_text(password) && email.is_none() {
        return Err("email is required when password is provided".to_string());
    } else if option_has_text(new_password) && !option_has_text(password) {
        return Err("password is required when newPassword is provided".to_string());
    }

    let mut args = vec![
        "src/gmail_setup.py".to_string(),
        "--browser-name".to_string(),
        browser_name.to_string(),
        "--query".to_string(),
        query.to_string(),
        "--timeout".to_string(),
        timeout_seconds.to_string(),
        "--terms-timeout".to_string(),
        terms_timeout_seconds.to_string(),
    ];
    let mut env_vars = HashMap::new();
    let mut redactions = Vec::new();

    if let Some(email_file) = email_file {
        args.push("--file".to_string());
        args.push(email_file.to_string());
        redactions.push(email_file.to_string());
        if request.keep_open_on_error {
            args.push("--keep-open-on-error".to_string());
        }
    } else {
        if let Some(email) = email {
            validate_safe_text(email, "email")?;
            args.push("--email".to_string());
            args.push(email.to_string());
        }
        if let Some(password) = password.filter(|value| !value.is_empty()) {
            env_vars.insert("AM_GMAIL_PASSWORD".to_string(), password.to_string());
            redactions.push(password.to_string());
            args.push("--password-env".to_string());
            args.push("AM_GMAIL_PASSWORD".to_string());
        }
        if let Some(new_password) = new_password.filter(|value| !value.is_empty()) {
            env_vars.insert(
                "AM_GMAIL_NEW_PASSWORD".to_string(),
                new_password.to_string(),
            );
            redactions.push(new_password.to_string());
            args.push("--new-password-env".to_string());
            args.push("AM_GMAIL_NEW_PASSWORD".to_string());
        }
    }

    preflight_common(false)?;
    {
        let mut run = state
            .current_run
            .lock()
            .map_err(|_| "failed to lock process state".to_string())?;
        ensure_no_current_process(&run)?;
        reset_run_state(&mut run, "gmail");
        run.redactions = redactions;
    }

    spawn_process_with_env(
        state.current_run.clone(),
        args,
        "gmail".to_string(),
        None,
        env_vars,
    )
}

#[tauri::command]
pub fn stop_current_run(force: bool, state: State<'_, AppState>) -> Result<StopResult, String> {
    let mut run = state
        .current_run
        .lock()
        .map_err(|_| "failed to lock process state".to_string())?;

    if !matches!(
        run.status.as_str(),
        "starting" | "running" | "pause_pending" | "intervention_required"
    ) {
        return Ok(StopResult {
            status: run.status.clone(),
            process_id: run.process_id,
            message: "no active account run".to_string(),
        });
    }

    if force {
        let process_id = run.process_id;
        if let Some(child) = run.child.as_mut() {
            let _ = child.kill();
        }
        run.status = "stopped".to_string();
        run.ended_at = Some(now());
        run.error = Some("force stopped by user".to_string());
        run.queue.clear();
        run.browser_preview = None;
        run.auth_intervention = None;
        run.child = None;
        return Ok(StopResult {
            status: run.status.clone(),
            process_id,
            message: "current process was force stopped".to_string(),
        });
    }

    run.stop_after_current = true;
    run.status = "pause_pending".to_string();
    Ok(StopResult {
        status: run.status.clone(),
        process_id: run.process_id,
        message: "will stop after current account finishes".to_string(),
    })
}

#[tauri::command]
pub fn continue_auth_intervention(state: State<'_, AppState>) -> Result<StopResult, String> {
    write_auth_intervention_action(state.current_run.clone(), "continue")
}

#[tauri::command]
pub fn skip_auth_intervention(state: State<'_, AppState>) -> Result<StopResult, String> {
    write_auth_intervention_action(state.current_run.clone(), "skip")
}

fn run_accounts(
    run_state: Arc<Mutex<RunState>>,
    account_ids: Vec<String>,
    task_type: String,
) -> Result<ProcessStartResult, String> {
    run_accounts_for_platform(run_state, "tiktok", "warmupTask", account_ids, task_type)
}

fn run_platform_task_inner(
    run_state: Arc<Mutex<RunState>>,
    request: PlatformTaskRequest,
) -> Result<ProcessStartResult, String> {
    let platform = normalize_platform(&request.platform, "platform")?;
    let task_type = normalize_task_type(&request.task_type)?;
    let mut account_ids = request
        .account_ids
        .into_iter()
        .map(|account_id| account_id.trim().to_string())
        .filter(|account_id| !account_id.is_empty())
        .collect::<Vec<_>>();
    for account_id in &account_ids {
        validate_account_id(account_id)?;
    }
    if !matches!(task_type.as_str(), "fyp" | "warmup" | "target_engagement") {
        return Err(format!(
            "taskType '{}' is not supported by run_platform_task in V1; platform='{}', accountIds='{}'",
            task_type,
            platform,
            account_ids_label(&account_ids),
        ));
    }
    let capability = capability_for_task(&task_type)?;
    if !account_ids.is_empty() {
        ensure_account_ids_belong_to_platform(&platform, &account_ids)
            .map_err(|error| format!("{}; capability='{}'", error, capability))?;
    }
    ensure_platform_capability(&platform, capability).map_err(|error| {
        format!(
            "{}; platform='{}', capability='{}', accountIds='{}'",
            error,
            platform,
            capability,
            account_ids_label(&account_ids),
        )
    })?;
    ensure_platform_can_execute(&platform, capability, &account_ids)?;

    let mode = request
        .mode
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or(if account_ids.is_empty() {
            "all"
        } else {
            "selected"
        });
    if !matches!(mode, "all" | "single" | "selected") {
        return Err(format!("unsupported task mode '{}'", mode));
    }

    if mode == "all" && account_ids.is_empty() {
        account_ids = enabled_account_ids_for_platform(&platform, capability)?;
    }

    if account_ids.is_empty() {
        return Err("accountIds must contain at least one account".to_string());
    }
    if mode == "single" && account_ids.len() != 1 {
        return Err("single mode requires exactly one accountId".to_string());
    }
    if mode == "all" {
        account_ids = enabled_account_ids_for_platform(&platform, capability)?;
        if account_ids.is_empty() {
            return Err(format!(
                "no enabled accounts to run; platform='{}', capability='{}', accountIds='<all>'",
                platform, capability,
            ));
        }
    }

    run_accounts_for_platform(
        run_state,
        &platform,
        capability,
        account_ids,
        format!("{}_{}", platform, task_type),
    )
}

fn run_accounts_for_platform(
    run_state: Arc<Mutex<RunState>>,
    platform: &str,
    capability: &str,
    account_ids: Vec<String>,
    task_type: String,
) -> Result<ProcessStartResult, String> {
    ensure_account_ids_belong_to_platform(platform, &account_ids)?;
    for account_id in &account_ids {
        ensure_account_can_execute_for_platform(platform, capability, account_id)?;
    }

    let mut queue = account_ids.clone();
    let first = queue.remove(0);
    let remaining = queue;

    {
        let mut run = run_state
            .lock()
            .map_err(|_| "failed to lock process state".to_string())?;
        ensure_no_current_process(&run)?;
        reset_run_state(&mut run, &task_type);
        run.queue = remaining;
    }

    spawn_account_process(run_state, first, task_type)
}

fn start_single_python_process(
    run_state: Arc<Mutex<RunState>>,
    script_args: Vec<String>,
    task_type: String,
    account_id: Option<String>,
    account_preflight: bool,
) -> Result<ProcessStartResult, String> {
    preflight_common(account_preflight)?;
    {
        let mut run = run_state
            .lock()
            .map_err(|_| "failed to lock process state".to_string())?;
        ensure_no_current_process(&run)?;
        reset_run_state(&mut run, &task_type);
    }

    spawn_process(run_state, script_args, task_type, account_id)
}

fn spawn_account_process(
    run_state: Arc<Mutex<RunState>>,
    account_id: String,
    task_type: String,
) -> Result<ProcessStartResult, String> {
    if let Err(error) = preflight_common(true) {
        mark_start_failure(&run_state, &error);
        return Err(error);
    }
    let (mut env_vars, redactions) = match login_env_for_account(&account_id) {
        Ok(result) => result,
        Err(error) => {
            mark_start_failure(&run_state, &error);
            return Err(error);
        }
    };
    let (ai_env_vars, ai_redactions) = ai_comment_env_for_runtime();
    for (key, value) in ai_env_vars {
        env_vars.insert(key, value);
    }
    let mut redactions = redactions;
    redactions.extend(ai_redactions);
    env_vars.insert(
        "AM_TASK_TYPE".to_string(),
        runtime_task_type(&task_type).to_string(),
    );
    {
        let mut run = run_state
            .lock()
            .map_err(|_| "failed to lock process state".to_string())?;
        for value in redactions {
            if !run.redactions.contains(&value) {
                run.redactions.push(value);
            }
        }
    }
    spawn_process_with_env(
        run_state,
        vec![
            "src/main.py".to_string(),
            "--account".to_string(),
            account_id.clone(),
        ],
        task_type,
        Some(account_id),
        env_vars,
    )
}

fn runtime_task_type(task_type: &str) -> &'static str {
    if task_type.contains("target_engagement") {
        "target_engagement"
    } else if task_type == "tiktok_register" {
        "tiktok_register"
    } else {
        "fyp"
    }
}

fn spawn_process(
    run_state: Arc<Mutex<RunState>>,
    script_args: Vec<String>,
    task_type: String,
    account_id: Option<String>,
) -> Result<ProcessStartResult, String> {
    spawn_process_with_env(
        run_state,
        script_args,
        task_type,
        account_id,
        HashMap::new(),
    )
}

fn spawn_process_with_env(
    run_state: Arc<Mutex<RunState>>,
    script_args: Vec<String>,
    task_type: String,
    account_id: Option<String>,
    mut env_vars: HashMap<String, String>,
) -> Result<ProcessStartResult, String> {
    let result = spawn_process_with_env_inner(
        run_state.clone(),
        script_args,
        task_type,
        account_id,
        &mut env_vars,
    );
    if let Err(error) = &result {
        mark_start_failure(&run_state, error);
    }
    result
}

fn login_env_for_account(
    account_id: &str,
) -> Result<(HashMap<String, String>, Vec<String>), String> {
    let config = load_config()?;
    let Some(account) = config
        .accounts()
        .iter()
        .find(|account| account.id() == account_id)
    else {
        return Err(format!("account '{}' does not exist in config", account_id));
    };
    if !account.login_enabled() {
        return Ok((HashMap::new(), Vec::new()));
    }
    let username = account
        .login_username()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            format!(
                "account '{}' auto login is enabled but login.username is missing",
                account_id
            )
        })?;
    let password = read_login_password_for_runtime(account_id)?
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            format!(
                "account '{}' auto login is enabled but its saved password is missing or unreadable",
                account_id
            )
        })?;
    let mut env_vars = HashMap::new();
    env_vars.insert("AM_LOGIN_ACCOUNT_ID".to_string(), account_id.to_string());
    env_vars.insert("AM_LOGIN_USERNAME".to_string(), username.to_string());
    env_vars.insert("AM_LOGIN_PASSWORD".to_string(), password.clone());
    env_vars.insert(
        "AM_LOGIN_CREDENTIAL_SOURCE".to_string(),
        "local_secure_store".to_string(),
    );
    Ok((env_vars, vec![password]))
}

fn ai_comment_env_for_runtime() -> (HashMap<String, String>, Vec<String>) {
    let Ok(config) = load_config() else {
        return (HashMap::new(), Vec::new());
    };
    if !config.ai_comment_enabled() {
        return (HashMap::new(), Vec::new());
    }
    let provider = config.ai_comment_provider().to_string();
    let Ok(Some(api_key)) = read_ai_comment_api_key_for_runtime(Some(&provider)) else {
        return (HashMap::new(), Vec::new());
    };
    if api_key.trim().is_empty() {
        return (HashMap::new(), Vec::new());
    }
    let mut env_vars = HashMap::new();
    env_vars.insert(AI_COMMENT_API_KEY_ENV.to_string(), api_key.clone());
    (env_vars, vec![api_key])
}

fn sensitive_env_redactions(env_vars: &HashMap<String, String>) -> Vec<String> {
    env_vars
        .iter()
        .filter(|(key, value)| {
            let key = key.to_ascii_lowercase();
            !value.is_empty()
                && (key.contains("password")
                    || key.contains("api_key")
                    || key.contains("apikey")
                    || key.contains("secret")
                    || key.contains("token")
                    || key.contains("credential")
                    || key.contains("authorization"))
        })
        .map(|(_, value)| value.clone())
        .collect()
}

fn spawn_process_with_env_inner(
    run_state: Arc<Mutex<RunState>>,
    script_args: Vec<String>,
    task_type: String,
    account_id: Option<String>,
    env_vars: &mut HashMap<String, String>,
) -> Result<ProcessStartResult, String> {
    let paths = project_paths()?;
    let (command, current_dir) = build_runtime_command(&script_args, &paths)?;
    env_vars.insert(
        "AM_AUTO_CLOSE_PROFILE".to_string(),
        if paths.auto_close_profile { "1" } else { "0" }.to_string(),
    );
    if !paths.chromium_executable.trim().is_empty() {
        env_vars.insert(
            "AM_CHROMIUM_EXECUTABLE".to_string(),
            paths.chromium_executable.clone(),
        );
    }
    if paths.runtime_mode == "source" {
        env_vars.insert("AM_DATA_DIR".to_string(), paths.data_dir.clone());
        env_vars.insert("AM_CONFIG_PATH".to_string(), paths.config_path.clone());
    }
    let env_redactions = sensitive_env_redactions(env_vars);
    if !env_redactions.is_empty() {
        let mut run = run_state
            .lock()
            .map_err(|_| "failed to lock process state".to_string())?;
        for value in env_redactions {
            if !run.redactions.contains(&value) {
                run.redactions.push(value);
            }
        }
    }
    let mut command_builder = Command::new(&command[0]);
    command_builder
        .args(&command[1..])
        .current_dir(&current_dir)
        .env("PYTHONUNBUFFERED", "1")
        .envs(env_vars.iter())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    hide_console_window(&mut command_builder);
    let mut child = command_builder.spawn().map_err(|err| {
        format!(
            "failed to start {:?} in {}: {}",
            command,
            normalize(&current_dir),
            err
        )
    })?;

    let process_id = child.id();
    if let Some(stdout) = child.stdout.take() {
        spawn_output_reader(run_state.clone(), stdout, true);
    }
    if let Some(stderr) = child.stderr.take() {
        spawn_output_reader(run_state.clone(), stderr, false);
    }

    {
        let mut run = run_state
            .lock()
            .map_err(|_| "failed to lock process state".to_string())?;
        run.status = "running".to_string();
        run.process_id = Some(process_id);
        run.task_type = Some(task_type.clone());
        run.account_id = account_id.clone();
        run.command = command.clone();
        run.started_at.get_or_insert_with(now);
        run.ended_at = None;
        run.child = Some(child);
    }

    spawn_waiter(run_state.clone(), task_type.clone());

    Ok(ProcessStartResult {
        process_id: Some(process_id),
        command,
        status: "running".to_string(),
        task_type,
        account_id,
    })
}

fn hide_console_window(command: &mut Command) {
    #[cfg(windows)]
    {
        command.creation_flags(CREATE_NO_WINDOW);
    }
}

fn mark_start_failure(run_state: &Arc<Mutex<RunState>>, error: &str) {
    let Ok(mut run) = run_state.lock() else {
        return;
    };
    if run.status != "starting" {
        return;
    }
    run.status = "failed".to_string();
    run.process_id = None;
    run.account_id = None;
    run.ended_at = Some(now());
    run.error = Some(error.to_string());
    run.queue.clear();
    run.browser_preview = None;
    run.auth_intervention = None;
    run.child = None;
}

fn spawn_waiter(run_state: Arc<Mutex<RunState>>, task_type: String) {
    thread::spawn(move || loop {
        thread::sleep(Duration::from_millis(500));

        let exit_result = {
            let mut run = match run_state.lock() {
                Ok(run) => run,
                Err(_) => return,
            };
            let Some(child) = run.child.as_mut() else {
                return;
            };
            match child.try_wait() {
                Ok(Some(status)) => {
                    run.child = None;
                    Some(Ok(status.code()))
                }
                Ok(None) => None,
                Err(error) => {
                    run.child = None;
                    Some(Err(error.to_string()))
                }
            }
        };

        let Some(exit_result) = exit_result else {
            continue;
        };

        let next_account = {
            let mut run = match run_state.lock() {
                Ok(run) => run,
                Err(_) => return,
            };

            if let Some(account_id) = run.account_id.clone() {
                run.completed_accounts.push(account_id);
            }

            match exit_result {
                Ok(Some(0)) => {}
                Ok(code) => {
                    run.error = Some(format!("process exited with code {:?}", code));
                }
                Err(error) => {
                    run.error = Some(format!("failed to wait process: {}", error));
                }
            }

            if run.stop_after_current {
                run.status = "stopped".to_string();
                run.queue.clear();
                run.browser_preview = None;
                run.auth_intervention = None;
                run.ended_at = Some(now());
                None
            } else if let Some(next) = run.queue.first().cloned() {
                run.queue.remove(0);
                Some(next)
            } else {
                run.status = if run.error.is_some() {
                    "failed".to_string()
                } else {
                    "completed".to_string()
                };
                run.process_id = None;
                run.account_id = None;
                run.browser_preview = None;
                run.auth_intervention = None;
                run.ended_at = Some(now());
                None
            }
        };

        if let Some(account_id) = next_account {
            if let Err(error) =
                spawn_account_process(run_state.clone(), account_id, task_type.clone())
            {
                if let Ok(mut run) = run_state.lock() {
                    run.status = "partial_failed".to_string();
                    run.error = Some(error);
                    run.process_id = None;
                    run.account_id = None;
                    run.browser_preview = None;
                    run.auth_intervention = None;
                    run.ended_at = Some(now());
                }
            }
        }
        return;
    });
}

fn spawn_output_reader<R>(run_state: Arc<Mutex<RunState>>, reader: R, stdout: bool)
where
    R: std::io::Read + Send + 'static,
{
    thread::spawn(move || {
        let reader = BufReader::new(reader);
        for line in reader.lines() {
            let Ok(line) = line else {
                break;
            };
            if let Ok(mut run) = run_state.lock() {
                if stdout && apply_browser_preview_event(&mut run, &line) {
                    continue;
                }
                if stdout && apply_auth_event(&mut run, &line) {
                    continue;
                }
                let redactions = run.redactions.clone();
                let target = if stdout {
                    &mut run.stdout
                } else {
                    &mut run.stderr
                };
                target.push_str(&redact_line(&line, &redactions));
                target.push('\n');
                if target.len() > 300_000 {
                    let keep_from = target.len().saturating_sub(220_000);
                    target.replace_range(..keep_from, "");
                }
            } else {
                break;
            }
        }
    });
}

fn read_process_buffer(
    run_state: Arc<Mutex<RunState>>,
    offset: usize,
    stdout: bool,
) -> Result<ProcessLogChunk, String> {
    let run = run_state
        .lock()
        .map_err(|_| "failed to lock process state".to_string())?;
    let buffer = if stdout { &run.stdout } else { &run.stderr };
    let start = offset.min(buffer.len());
    Ok(ProcessLogChunk {
        offset,
        next_offset: buffer.len(),
        content: buffer[start..].to_string(),
    })
}

fn reset_run_state(run: &mut RunState, task_type: &str) {
    *run = RunState {
        status: "starting".to_string(),
        task_type: Some(task_type.to_string()),
        started_at: Some(now()),
        ..RunState::default()
    };
}

impl From<BrowserPreviewState> for BrowserPreview {
    fn from(value: BrowserPreviewState) -> Self {
        Self {
            account_id: value.account_id,
            profile_id: value.profile_id,
            cdp_endpoint: value.cdp_endpoint,
            opened_at: value.opened_at,
        }
    }
}

impl From<AuthInterventionState> for AuthIntervention {
    fn from(value: AuthInterventionState) -> Self {
        Self {
            account_id: value.account_id,
            platform: value.platform,
            state: value.state,
            detail: value.detail,
            reason: value.reason,
            url: value.url,
            checked_at: value.checked_at,
        }
    }
}

fn apply_browser_preview_event(run: &mut RunState, line: &str) -> bool {
    const PREFIX: &str = "AM_BROWSER_PREVIEW ";
    let Some(payload) = line.strip_prefix(PREFIX) else {
        return false;
    };
    let Ok(event) = serde_json::from_str::<BrowserPreviewEvent>(payload) else {
        return true;
    };

    match event.event.as_str() {
        "opened" => {
            if let Some(cdp_endpoint) = event.cdp_endpoint {
                run.browser_preview = Some(BrowserPreviewState {
                    account_id: event.account_id,
                    profile_id: event.profile_id.unwrap_or_else(|| "browser".to_string()),
                    cdp_endpoint,
                    opened_at: now(),
                });
            }
        }
        "closed" => {
            if run
                .browser_preview
                .as_ref()
                .map(|preview| event.profile_id.as_deref() == Some(preview.profile_id.as_str()))
                .unwrap_or(false)
            {
                run.browser_preview = None;
            }
        }
        _ => {}
    }
    true
}

fn apply_auth_event(run: &mut RunState, line: &str) -> bool {
    const PREFIX: &str = "AM_AUTH_EVENT ";
    let Some(payload) = line.strip_prefix(PREFIX) else {
        return false;
    };
    let Ok(event) = serde_json::from_str::<AuthEvent>(payload) else {
        return true;
    };
    if event.event != "auth_state" {
        return true;
    }
    if event.intervention_required.unwrap_or(false) {
        run.status = "intervention_required".to_string();
        run.auth_intervention = Some(AuthInterventionState {
            account_id: event.account_id,
            platform: event.platform,
            state: event.state,
            detail: event.detail.unwrap_or_default(),
            reason: event
                .reason
                .unwrap_or_else(|| "manual_intervention".to_string()),
            url: event.url,
            checked_at: event.checked_at.unwrap_or_else(now),
        });
    } else if event.state == "logged_in" {
        if run.status == "intervention_required" {
            run.status = "running".to_string();
        }
        run.auth_intervention = None;
    }
    true
}

fn write_auth_intervention_action(
    run_state: Arc<Mutex<RunState>>,
    action: &str,
) -> Result<StopResult, String> {
    if !matches!(action, "continue" | "skip" | "stop") {
        return Err(format!("unsupported auth intervention action '{}'", action));
    }
    let (account_id, process_id) = {
        let mut run = run_state
            .lock()
            .map_err(|_| "failed to lock process state".to_string())?;
        let intervention = run
            .auth_intervention
            .clone()
            .ok_or_else(|| "no active auth intervention".to_string())?;
        let process_id = run.process_id;
        if action == "continue" || action == "skip" {
            run.status = "running".to_string();
            run.auth_intervention = None;
        }
        (intervention.account_id, process_id)
    };
    write_auth_action_flag(&account_id, action)?;
    Ok(StopResult {
        status: "running".to_string(),
        process_id,
        message: match action {
            "continue" => {
                "auth intervention marked complete; runtime will recheck login".to_string()
            }
            "skip" => "current account will be skipped after auth intervention".to_string(),
            _ => "auth intervention action sent".to_string(),
        },
    })
}

fn write_auth_action_flag(account_id: &str, action: &str) -> Result<(), String> {
    validate_account_id(account_id)?;
    let paths = project_paths()?;
    let dir = PathBuf::from(paths.data_dir)
        .join("auth_intervention")
        .join(account_id);
    std::fs::create_dir_all(&dir)
        .map_err(|err| format!("failed to create {}: {}", normalize(&dir), err))?;
    std::fs::write(dir.join(format!("{}.flag", action)), now())
        .map_err(|err| format!("failed to write auth intervention action: {}", err))
}

fn preflight_common(account_run: bool) -> Result<(), String> {
    let paths = project_paths()?;
    if paths.runtime_mode == "source" {
        ensure_python_available()?;
    } else {
        ensure_bundled_runtime_available(&paths)?;
    }
    if !Path::new(&paths.config_path).is_file() {
        return Err(format!(
            "config file is not readable: {}",
            paths.config_path
        ));
    }
    let _ = load_config()?;

    if account_run {
        ensure_no_active_run_lock(&PathBuf::from(&paths.lock_file_path))?;
    }

    Ok(())
}

fn ensure_python_available() -> Result<(), String> {
    let command = python_command_parts()?;
    let mut check_command = command.clone();
    check_command.push("--version".to_string());
    Command::new(&check_command[0])
        .args(&check_command[1..])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map_err(|err| format!("failed to start Python via {}: {}", command.join(" "), err))
        .and_then(|status| {
            if status.success() {
                Ok(())
            } else {
                Err(format!("Python check failed with status {}", status))
            }
        })
}

fn ensure_bundled_runtime_available(paths: &ProjectPaths) -> Result<(), String> {
    let runtime_path = Path::new(&paths.runtime_path);
    if !runtime_path.is_file() {
        return Err(format!(
            "bundled runtime is not readable: {}",
            paths.runtime_path
        ));
    }
    let manifest_path = Path::new(&paths.runtime_manifest_path);
    if !manifest_path.is_file() {
        return Err(format!(
            "bundled runtime manifest is not readable: {}",
            paths.runtime_manifest_path
        ));
    }
    Ok(())
}

fn ensure_no_active_run_lock(lock_path: &Path) -> Result<(), String> {
    if !lock_path.exists() {
        return Ok(());
    }
    let content = std::fs::read_to_string(lock_path)
        .map_err(|err| format!("failed to read {}: {}", normalize(lock_path), err))?;
    let pid = content.trim().parse::<u32>().unwrap_or(0);
    if pid != 0 && pid_alive(pid) {
        return Err(format!(
            "active run.lock is held by PID {} at {}",
            pid,
            normalize(lock_path)
        ));
    }
    std::fs::remove_file(lock_path).map_err(|err| {
        format!(
            "stale run.lock exists at {}, but failed to clear it: {}",
            normalize(lock_path),
            err
        )
    })?;
    Ok(())
}

fn ensure_no_current_process(run: &RunState) -> Result<(), String> {
    if matches!(
        run.status.as_str(),
        "starting" | "running" | "pause_pending" | "intervention_required"
    ) {
        return Err("another account script is already running".to_string());
    }
    Ok(())
}

fn ensure_tiktok_register_account(account_id: &str) -> Result<(), String> {
    let config = load_config()?;
    let paths = project_paths()?;
    let account = config
        .accounts()
        .iter()
        .find(|account| account.id() == account_id)
        .ok_or_else(|| {
            format!(
                "REGISTER_ACCOUNT_NOT_FOUND: account '{}' does not exist",
                account_id
            )
        })?;

    if account.platform() != "tiktok" {
        return Err(format!(
            "REGISTER_UNSUPPORTED_PLATFORM: account '{}' belongs to platform '{}'",
            account_id,
            account.platform(),
        ));
    }

    match account.browser_provider() {
        "bitbrowser" => {
            if account.bitbrowser_profile_id().is_none() {
                return Err(format!(
                    "REGISTER_BROWSER_PROVIDER_INVALID: account '{}' has no bitbrowser_profile_id",
                    account_id,
                ));
            }
            let api_status = check_bitbrowser_api();
            if !api_status.available() {
                return Err(format!(
                    "REGISTER_BROWSER_PROVIDER_INVALID: BitBrowser API is not available at {}: {}",
                    api_status.api_url(),
                    api_status.error().unwrap_or("unknown error")
                ));
            }
        }
        "builtin_chromium" => {
            if paths.chromium_executable.trim().is_empty()
                && config.chromium_executable().is_none()
                && auto_configure_chromium_executable().is_err()
            {
                return Err(
                    "REGISTER_BROWSER_PROVIDER_INVALID: 未检测到可用 Chromium，请安装 Chrome/Edge 或手动指定可执行文件。"
                        .to_string(),
                );
            }
        }
        provider => {
            return Err(format!(
                "REGISTER_BROWSER_PROVIDER_INVALID: unsupported browser provider '{}'",
                provider
            ));
        }
    }

    Ok(())
}

fn ensure_account_can_execute(account_id: &str) -> Result<(), String> {
    ensure_account_can_execute_for_platform("tiktok", "warmupTask", account_id)
}

fn ensure_account_can_execute_for_platform(
    platform: &str,
    capability: &str,
    account_id: &str,
) -> Result<(), String> {
    let config = load_config()?;
    let paths = project_paths()?;
    let account = config
        .accounts()
        .iter()
        .find(|account| account.id() == account_id)
        .ok_or_else(|| format!("account '{}' does not exist in config", account_id))?;

    if account.platform() != platform {
        return Err(format!(
            "account '{}' belongs to platform '{}' but request.platform is '{}'; capability='{}'",
            account_id,
            account.platform(),
            platform,
            capability,
        ));
    }
    if platform != "tiktok" && !(platform == "instagram" && capability == "warmupTask") {
        return Err(format!(
            "platform '{}' capability '{}' for account '{}' is not adapted for automatic execution in V1",
            platform,
            capability,
            account_id
        ));
    }
    if !account.enabled() {
        return Err(format!(
            "account '{}' is disabled; platform='{}', capability='{}'",
            account_id, platform, capability,
        ));
    }
    if account.login_enabled() {
        account
            .login_username()
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| {
                format!(
                    "account '{}' auto login is enabled but login.username is missing",
                    account_id
                )
            })?;
        if read_login_password_for_runtime(account_id)?.is_none() {
            return Err(format!(
                "account '{}' auto login is enabled but its saved password is missing or unreadable",
                account_id
            ));
        }
    }
    match account.browser_provider() {
        "bitbrowser" => {
            if account.bitbrowser_profile_id().is_none() {
                return Err(format!(
                    "account '{}' has no bitbrowser_profile_id; platform='{}', capability='{}'",
                    account_id, platform, capability,
                ));
            }
            let api_status = check_bitbrowser_api();
            if !api_status.available() {
                return Err(format!(
                    "BitBrowser API is not available at {}: {}",
                    api_status.api_url(),
                    api_status.error().unwrap_or("unknown error")
                ));
            }
        }
        "builtin_chromium" => {
            if paths.chromium_executable.trim().is_empty()
                && config.chromium_executable().is_none()
                && auto_configure_chromium_executable().is_err()
            {
                return Err(
                    "未检测到可用 Chromium，请安装 Chrome/Edge 或手动指定可执行文件。".to_string(),
                );
            }
        }
        provider => {
            return Err(format!("unsupported browser provider '{}'", provider));
        }
    }

    Ok(())
}

fn ensure_all_enabled_accounts_can_execute() -> Result<(), String> {
    ensure_all_enabled_accounts_can_execute_for_platform("tiktok", "warmupTask")
}

fn ensure_all_enabled_accounts_can_execute_for_platform(
    platform: &str,
    capability: &str,
) -> Result<(), String> {
    ensure_platform_can_execute(platform, capability, &[])?;
    let config = load_config()?;
    let paths = project_paths()?;
    let executable_accounts = config
        .accounts()
        .iter()
        .filter(|account| account.enabled() && account.platform() == platform)
        .collect::<Vec<_>>();

    if executable_accounts.is_empty() {
        return Err(format!(
            "no enabled accounts to run; platform='{}', capability='{}', accountIds='<all>'",
            platform, capability,
        ));
    }
    let login_errors = executable_accounts
        .iter()
        .filter_map(|account| {
            if !account.login_enabled() {
                return None;
            }
            let username_missing = account
                .login_username()
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .is_none();
            let password_missing = read_login_password_for_runtime(account.id())
                .map(|value| value.is_none())
                .unwrap_or(true);
            if username_missing || password_missing {
                Some(account.id().to_string())
            } else {
                None
            }
        })
        .collect::<Vec<_>>();
    if !login_errors.is_empty() {
        return Err(format!(
            "enabled auto-login account(s) are missing login.username or a readable saved password; accountIds='{}'",
            login_errors.join(", ")
        ));
    }
    let missing_profiles = executable_accounts
        .iter()
        .filter(|account| {
            account.browser_provider() == "bitbrowser" && account.bitbrowser_profile_id().is_none()
        })
        .map(|account| account.id().to_string())
        .collect::<Vec<_>>();
    if !missing_profiles.is_empty() {
        return Err(format!(
            "enabled account(s) have no bitbrowser_profile_id; platform='{}', capability='{}', accountIds='{}'",
            platform,
            capability,
            missing_profiles.join(", ")
        ));
    }
    if executable_accounts
        .iter()
        .any(|account| account.browser_provider() == "bitbrowser")
    {
        let api_status = check_bitbrowser_api();
        if !api_status.available() {
            return Err(format!(
                "BitBrowser API is not available at {}: {}",
                api_status.api_url(),
                api_status.error().unwrap_or("unknown error")
            ));
        }
    }
    if executable_accounts
        .iter()
        .any(|account| account.browser_provider() == "builtin_chromium")
        && paths.chromium_executable.trim().is_empty()
        && config.chromium_executable().is_none()
        && auto_configure_chromium_executable().is_err()
    {
        return Err("未检测到可用 Chromium，请安装 Chrome/Edge 或手动指定可执行文件。".to_string());
    }

    Ok(())
}

fn enabled_account_ids_for_platform(
    platform: &str,
    capability: &str,
) -> Result<Vec<String>, String> {
    ensure_all_enabled_accounts_can_execute_for_platform(platform, capability)?;
    Ok(load_config()?
        .accounts()
        .iter()
        .filter(|account| account.enabled() && account.platform() == platform)
        .map(|account| account.id().to_string())
        .collect())
}

fn ensure_platform_can_execute(
    platform: &str,
    capability: &str,
    account_ids: &[String],
) -> Result<(), String> {
    if platform == "tiktok" || (platform == "instagram" && capability == "warmupTask") {
        Ok(())
    } else {
        Err(format!(
            "platform '{}' capability '{}' is not adapted for automatic execution in V1; accountIds='{}'",
            platform,
            capability,
            account_ids_label(account_ids),
        ))
    }
}

fn account_ids_label(account_ids: &[String]) -> String {
    if account_ids.is_empty() {
        "<all>".to_string()
    } else {
        account_ids.join(", ")
    }
}

fn normalize_task_type(task_type: &str) -> Result<String, String> {
    let task_type = task_type.trim();
    match task_type {
        "fyp" => Ok("fyp".to_string()),
        "warmup" => Ok("warmup".to_string()),
        "target" | "target_engagement" => Ok("target_engagement".to_string()),
        "scheduler" | "gmail" | "diagnostic" => Ok(task_type.to_string()),
        _ => Err(format!("unsupported taskType '{}'", task_type)),
    }
}

fn capability_for_task(task_type: &str) -> Result<&'static str, String> {
    match task_type {
        "fyp" | "warmup" => Ok("warmupTask"),
        "target_engagement" | "target" => Ok("targetEngagement"),
        "scheduler" => Ok("scheduler"),
        "gmail" => Ok("gmailSetup"),
        "diagnostic" => Ok("diagnostics"),
        _ => Err(format!("unsupported taskType '{}'", task_type)),
    }
}

fn validate_script_name(script_name: &str) -> Result<(), String> {
    let allowed = [
        "main.py",
        "scheduler.py",
        "stats.py",
        "create_browser.py",
        "sync_accounts_config.py",
        "test_like.py",
        "test_comment.py",
    ];
    if allowed.contains(&script_name) {
        Ok(())
    } else {
        Err(format!("script '{}' is not allowed", script_name))
    }
}

fn validate_args(args: &[String]) -> Result<(), String> {
    if args.iter().any(|arg| arg.contains('\0')) {
        return Err("script args must not contain NUL bytes".to_string());
    }
    Ok(())
}

fn validate_script_capability(script_name: &str, args: &[String]) -> Result<(), String> {
    if matches!(script_name, "test_like.py" | "test_comment.py") {
        let account_id = script_arg_value(args, "--account")
            .ok_or_else(|| format!("{} requires --account", script_name))?;
        validate_account_id(account_id)?;
        ensure_account_can_execute_for_platform("tiktok", "diagnostics", account_id)?;
    }
    Ok(())
}

fn script_arg_value<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    args.windows(2)
        .find(|pair| pair[0] == name)
        .map(|pair| pair[1].as_str())
}

fn validate_safe_text(value: &str, field: &str) -> Result<(), String> {
    if value.contains('\0') || value.contains('\r') || value.contains('\n') {
        return Err(format!("{} must not contain control characters", field));
    }
    Ok(())
}

fn option_has_text(value: Option<&str>) -> bool {
    value.map(|value| !value.is_empty()).unwrap_or(false)
}

fn validate_account_id(account_id: &str) -> Result<(), String> {
    if account_id.is_empty()
        || !account_id
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-')
    {
        return Err("invalid account id".to_string());
    }
    Ok(())
}

fn build_python_command(script_args: &[String]) -> Result<Vec<String>, String> {
    let mut command = python_command_parts()?;
    command.extend(script_args.iter().cloned());
    Ok(command)
}

fn build_runtime_command(
    script_args: &[String],
    paths: &ProjectPaths,
) -> Result<(Vec<String>, PathBuf), String> {
    if paths.runtime_mode == "bundled" {
        build_bundled_command(script_args, paths)
    } else {
        let script_args = with_config_arg(script_args.to_vec(), &paths.config_path);
        Ok((build_python_command(&script_args)?, project_root()?))
    }
}

fn build_bundled_command(
    script_args: &[String],
    paths: &ProjectPaths,
) -> Result<(Vec<String>, PathBuf), String> {
    let Some(script_name) = script_args.first().map(String::as_str) else {
        return Err("missing script name for bundled runtime command".to_string());
    };
    let mut command = vec![paths.runtime_path.clone()];
    match script_name {
        "src/main.py" => {
            command.push("run".to_string());
            append_config_and_data_args(&mut command, paths);
            append_filtered_args(&mut command, &script_args[1..], &["--config", "--data-dir"]);
        }
        "src/gmail_setup.py" => {
            command.push("gmail".to_string());
            command.extend(script_args.iter().skip(1).cloned());
        }
        "src/test_like.py" => {
            command.push("diagnostic".to_string());
            command.push("--kind".to_string());
            command.push("like".to_string());
            append_config_and_data_args(&mut command, paths);
            append_filtered_args(&mut command, &script_args[1..], &["--config", "--data-dir"]);
        }
        "src/test_comment.py" => {
            command.push("diagnostic".to_string());
            command.push("--kind".to_string());
            command.push("comment".to_string());
            append_config_and_data_args(&mut command, paths);
            append_filtered_args(&mut command, &script_args[1..], &["--config", "--data-dir"]);
        }
        _ => {
            return Err(format!(
                "script '{}' is not supported in bundled runtime mode",
                script_name
            ));
        }
    }
    let current_dir = Path::new(&paths.runtime_path)
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    Ok((command, current_dir))
}

fn append_config_and_data_args(command: &mut Vec<String>, paths: &ProjectPaths) {
    command.extend([
        "--config".to_string(),
        paths.config_path.clone(),
        "--data-dir".to_string(),
        paths.data_dir.clone(),
    ]);
}

fn append_filtered_args(command: &mut Vec<String>, args: &[String], skip_options: &[&str]) {
    let mut index = 0;
    while index < args.len() {
        if skip_options.contains(&args[index].as_str()) {
            index += 2;
            continue;
        }
        command.push(args[index].clone());
        index += 1;
    }
}

fn with_config_arg(script_args: Vec<String>, config_path: &str) -> Vec<String> {
    let Some(script_name) = script_args.first() else {
        return script_args;
    };
    if !matches!(
        script_name.as_str(),
        "src/main.py" | "src/test_like.py" | "src/test_comment.py" | "src/scheduler.py"
    ) || script_args.iter().any(|arg| arg == "--config")
    {
        return script_args;
    }

    let mut next = Vec::with_capacity(script_args.len() + 2);
    next.push(script_name.clone());
    next.push("--config".to_string());
    next.push(config_path.to_string());
    next.extend(script_args.into_iter().skip(1));
    next
}

fn pid_alive(pid: u32) -> bool {
    if cfg!(windows) {
        let filter = format!("PID eq {}", pid);
        Command::new("tasklist")
            .args(["/FI", filter.as_str(), "/NH"])
            .output()
            .map(|output| String::from_utf8_lossy(&output.stdout).contains(&pid.to_string()))
            .unwrap_or(false)
    } else {
        Command::new("sh")
            .args(["-c", &format!("kill -0 {}", pid)])
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
    }
}

fn now() -> String {
    Local::now().to_rfc3339()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_paths(runtime_mode: &str) -> ProjectPaths {
        ProjectPaths {
            runtime_mode: runtime_mode.to_string(),
            project_root: "E:/repo/account-matrix".to_string(),
            config_path: "C:/Users/me/AppData/Roaming/星域/config/accounts.yaml"
                .to_string(),
            comments_path: "C:/Users/me/AppData/Roaming/星域/config/comments.txt"
                .to_string(),
            brand_comments_path:
                "C:/Users/me/AppData/Roaming/星域/config/comments_brand.txt".to_string(),
            data_dir: "C:/Users/me/AppData/Local/星域/data".to_string(),
            logs_dir: "C:/Users/me/AppData/Local/星域/logs".to_string(),
            actions_db_path: "C:/Users/me/AppData/Local/星域/data/actions.db".to_string(),
            sessions_log_path: "C:/Users/me/AppData/Local/星域/data/sessions.log"
                .to_string(),
            lock_file_path: "C:/Users/me/AppData/Local/星域/data/run.lock".to_string(),
            src_dir: "E:/repo/account-matrix/src".to_string(),
            settings_path:
                "C:/Users/me/AppData/Roaming/星域/settings/local-settings.json"
                    .to_string(),
            runtime_path:
                "C:/Program Files/星域/resources/runtime/account-matrix-runtime.exe"
                    .to_string(),
            runtime_manifest_path:
                "C:/Program Files/星域/resources/runtime/runtime-manifest.json"
                    .to_string(),
            runtime_version: Some("0.1.0".to_string()),
            python_executable: "py".to_string(),
            default_browser_provider: "bitbrowser".to_string(),
            chromium_executable: String::new(),
            bitbrowser_api_url: "http://127.0.0.1:54345".to_string(),
            auto_close_profile: true,
            log_poll_interval_seconds: 3,
        }
    }

    #[test]
    fn config_arg_is_inserted_after_supported_script_name() {
        let args = with_config_arg(
            vec![
                "src/main.py".to_string(),
                "--account".to_string(),
                "acct_1".to_string(),
            ],
            "config/accounts.yaml",
        );

        assert_eq!(
            args,
            vec![
                "src/main.py",
                "--config",
                "config/accounts.yaml",
                "--account",
                "acct_1"
            ]
        );
    }

    #[test]
    fn config_arg_is_not_duplicated_or_added_to_unsupported_scripts() {
        let existing = with_config_arg(
            vec![
                "src/main.py".to_string(),
                "--config".to_string(),
                "custom.yaml".to_string(),
            ],
            "config/accounts.yaml",
        );
        let unsupported = with_config_arg(vec!["src/stats.py".to_string()], "config/accounts.yaml");

        assert_eq!(existing, vec!["src/main.py", "--config", "custom.yaml"]);
        assert_eq!(unsupported, vec!["src/stats.py"]);
    }

    #[test]
    fn process_argument_validation_rejects_unsafe_values() {
        assert!(validate_script_name("main.py").is_ok());
        assert!(validate_script_name("../main.py").is_err());
        assert!(validate_account_id("acct-1_ok").is_ok());
        assert!(validate_account_id("acct 1").is_err());
        assert!(validate_args(&["--account".to_string(), "acct\0bad".to_string()]).is_err());
    }

    #[test]
    fn runtime_task_type_maps_desktop_task_names() {
        assert_eq!(runtime_task_type("tiktok_fyp"), "fyp");
        assert_eq!(
            runtime_task_type("tiktok_target_engagement"),
            "target_engagement"
        );
        assert_eq!(runtime_task_type("instagram_fyp"), "fyp");
        assert_eq!(runtime_task_type("instagram_warmup"), "fyp");
    }

    #[test]
    fn instagram_warmup_task_maps_to_supported_capability() {
        let normalized = normalize_task_type("warmup").expect("warmup should normalize");

        assert_eq!(normalized, "warmup");
        assert_eq!(
            capability_for_task(&normalized).expect("fyp should map to capability"),
            "warmupTask"
        );
    }

    #[test]
    fn auth_event_marks_run_as_intervention_required() {
        let mut run = RunState {
            status: "running".to_string(),
            ..RunState::default()
        };
        let line = r#"AM_AUTH_EVENT {"event":"auth_state","account_id":"acct_1","platform":"tiktok","state":"captcha","detail":"TikTok captcha detected","intervention_required":true,"reason":"captcha","url":"https://www.tiktok.com/login","checked_at":"2026-07-28T12:00:00+08:00"}"#;

        assert!(apply_auth_event(&mut run, line));
        let intervention = run
            .auth_intervention
            .expect("auth intervention should be recorded");

        assert_eq!(run.status, "intervention_required");
        assert_eq!(intervention.account_id, "acct_1");
        assert_eq!(intervention.state, "captcha");
        assert_eq!(
            intervention.url.as_deref(),
            Some("https://www.tiktok.com/login")
        );
    }

    #[test]
    fn bundled_runtime_command_maps_account_run_to_sidecar() {
        let paths = test_paths("bundled");
        let (command, current_dir) = build_bundled_command(
            &[
                "src/main.py".to_string(),
                "--account".to_string(),
                "acct_1".to_string(),
            ],
            &paths,
        )
        .expect("bundled command should build");

        assert_eq!(command[0], paths.runtime_path);
        assert_eq!(command[1], "run");
        assert!(command.contains(&"--config".to_string()));
        assert!(command.contains(&paths.config_path));
        assert!(command.contains(&"--data-dir".to_string()));
        assert!(command.contains(&paths.data_dir));
        assert!(command.contains(&"--account".to_string()));
        assert!(command.contains(&"acct_1".to_string()));
        assert!(current_dir.ends_with("runtime"));
    }

    #[test]
    fn bundled_runtime_command_maps_comment_diagnostic_to_sidecar() {
        let paths = test_paths("bundled");
        let (command, _) = build_bundled_command(
            &[
                "src/test_comment.py".to_string(),
                "--account".to_string(),
                "acct_1".to_string(),
                "--min".to_string(),
                "1000".to_string(),
                "--no-post".to_string(),
            ],
            &paths,
        )
        .expect("diagnostic command should build");

        assert_eq!(
            command,
            vec![
                paths.runtime_path,
                "diagnostic".to_string(),
                "--kind".to_string(),
                "comment".to_string(),
                "--config".to_string(),
                paths.config_path,
                "--data-dir".to_string(),
                paths.data_dir,
                "--account".to_string(),
                "acct_1".to_string(),
                "--min".to_string(),
                "1000".to_string(),
                "--no-post".to_string(),
            ]
        );
    }
}
