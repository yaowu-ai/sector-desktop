use chrono::Local;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value as JsonValue};
use std::fs;
use std::net::{TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

use crate::commands::bitbrowser::check_bitbrowser_api;
use crate::paths::{normalize, project_paths, project_root, python_command_parts, ProjectPaths};
use crate::security::redact_text;

const SCHEDULER_HOST: &str = "127.0.0.1";
const SCHEDULER_PORT: u16 = 9601;

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticCheck {
    name: String,
    status: String,
    detail: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeDiagnostics {
    status: String,
    checked_at: String,
    runtime_mode: String,
    runtime_version: Option<String>,
    runtime_manifest: Option<JsonValue>,
    runtime_diagnostic: Option<JsonValue>,
    paths: ProjectPaths,
    checks: Vec<DiagnosticCheck>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SupportBundleResult {
    path: String,
    diagnostics: RuntimeDiagnostics,
}

#[derive(Debug, Deserialize)]
struct RuntimeManifest {
    #[serde(rename = "schemaVersion")]
    schema_version: i64,
    #[serde(rename = "runtimeVersion")]
    runtime_version: String,
    executable: String,
    #[serde(rename = "supportedCommands")]
    supported_commands: Vec<String>,
}

#[tauri::command]
pub fn get_runtime_diagnostics() -> Result<RuntimeDiagnostics, String> {
    build_runtime_diagnostics()
}

#[tauri::command]
pub fn export_support_bundle() -> Result<SupportBundleResult, String> {
    let diagnostics = build_runtime_diagnostics()?;
    let paths = project_paths()?;
    let logs_dir = PathBuf::from(&paths.logs_dir);
    fs::create_dir_all(&logs_dir)
        .map_err(|err| format!("failed to create {}: {}", paths.logs_dir, err))?;
    let path = logs_dir.join(format!(
        "support-bundle-{}.json",
        Local::now().format("%Y%m%d-%H%M%S")
    ));
    let config_redacted = fs::read_to_string(&paths.config_path)
        .ok()
        .map(|content| redact_text(&content, &[]));
    let payload = json!({
        "diagnostics": diagnostics.clone(),
        "configRedacted": config_redacted,
    });
    fs::write(
        &path,
        serde_json::to_string_pretty(&payload)
            .map_err(|err| format!("failed to serialize support bundle: {}", err))?,
    )
    .map_err(|err| format!("failed to write {}: {}", normalize(&path), err))?;

    Ok(SupportBundleResult {
        path: normalize(&path),
        diagnostics,
    })
}

fn build_runtime_diagnostics() -> Result<RuntimeDiagnostics, String> {
    let paths = project_paths()?;
    let mut checks = Vec::new();

    push_check(
        &mut checks,
        "userConfig",
        Path::new(&paths.config_path).is_file(),
        &paths.config_path,
    );
    push_check(
        &mut checks,
        "userDataDir",
        Path::new(&paths.data_dir).is_dir(),
        &paths.data_dir,
    );
    push_check(
        &mut checks,
        "userLogsDir",
        Path::new(&paths.logs_dir).is_dir(),
        &paths.logs_dir,
    );

    let (manifest, runtime_version) = inspect_runtime(&paths, &mut checks);
    let runtime_diagnostic = invoke_runtime_json(&paths, "diagnostic", &mut checks).ok();
    let version_payload = invoke_runtime_json(&paths, "version", &mut checks).ok();
    let runtime_version = runtime_version.or_else(|| {
        version_payload
            .as_ref()
            .and_then(|value| value.get("runtimeVersion"))
            .and_then(JsonValue::as_str)
            .map(ToString::to_string)
    });

    let api_status = check_bitbrowser_api();
    checks.push(DiagnosticCheck {
        name: "bitBrowserApi".to_string(),
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
    checks.push(DiagnosticCheck {
        name: "schedulerPort".to_string(),
        status: if scheduler_port_open() {
            "ok"
        } else {
            "warning"
        }
        .to_string(),
        detail: format!("{}:{}", SCHEDULER_HOST, SCHEDULER_PORT),
    });

    let status = if checks.iter().any(|check| check.status == "error") {
        "error"
    } else if checks.iter().any(|check| check.status == "warning") {
        "warning"
    } else {
        "ok"
    };

    Ok(RuntimeDiagnostics {
        status: status.to_string(),
        checked_at: Local::now().to_rfc3339(),
        runtime_mode: paths.runtime_mode.clone(),
        runtime_version,
        runtime_manifest: manifest,
        runtime_diagnostic,
        paths,
        checks,
    })
}

fn inspect_runtime(
    paths: &ProjectPaths,
    checks: &mut Vec<DiagnosticCheck>,
) -> (Option<JsonValue>, Option<String>) {
    if paths.runtime_mode == "source" {
        push_check(
            checks,
            "sourceRuntime",
            Path::new(&paths.src_dir).join("runtime_cli.py").is_file(),
            &paths.src_dir,
        );
        return (None, None);
    }

    push_check(
        checks,
        "bundledRuntime",
        Path::new(&paths.runtime_path).is_file(),
        &paths.runtime_path,
    );
    let manifest_path = Path::new(&paths.runtime_manifest_path);
    push_check(
        checks,
        "runtimeManifest",
        manifest_path.is_file(),
        &paths.runtime_manifest_path,
    );

    let Ok(raw) = fs::read_to_string(manifest_path) else {
        return (None, None);
    };
    let manifest_json = serde_json::from_str::<JsonValue>(&raw).ok();
    match serde_json::from_str::<RuntimeManifest>(&raw) {
        Ok(manifest) => {
            let expected_exe = Path::new(&paths.runtime_path)
                .file_name()
                .and_then(|value| value.to_str())
                .unwrap_or_default();
            let commands_ok = ["run", "scheduler", "gmail", "diagnostic", "version"]
                .iter()
                .all(|command| {
                    manifest
                        .supported_commands
                        .iter()
                        .any(|item| item == command)
                });
            checks.push(DiagnosticCheck {
                name: "runtimeManifestSchema".to_string(),
                status: if manifest.schema_version == 1
                    && manifest.executable == expected_exe
                    && commands_ok
                {
                    "ok"
                } else {
                    "error"
                }
                .to_string(),
                detail: format!(
                    "schema={} executable={} commands={}",
                    manifest.schema_version,
                    manifest.executable,
                    manifest.supported_commands.join(",")
                ),
            });
            (manifest_json, Some(manifest.runtime_version))
        }
        Err(error) => {
            checks.push(DiagnosticCheck {
                name: "runtimeManifestSchema".to_string(),
                status: "error".to_string(),
                detail: error.to_string(),
            });
            (manifest_json, None)
        }
    }
}

fn invoke_runtime_json(
    paths: &ProjectPaths,
    command_name: &str,
    checks: &mut Vec<DiagnosticCheck>,
) -> Result<JsonValue, String> {
    let (command, current_dir) = runtime_json_command(paths, command_name)?;
    let output = Command::new(&command[0])
        .args(&command[1..])
        .current_dir(&current_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|err| format!("failed to start runtime {}: {}", command_name, err))?;
    if !output.status.success() {
        let detail = String::from_utf8_lossy(&output.stderr).trim().to_string();
        checks.push(DiagnosticCheck {
            name: format!("runtime{}Command", title_case(command_name)),
            status: "error".to_string(),
            detail,
        });
        return Err(format!("runtime {} failed", command_name));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let value = serde_json::from_str::<JsonValue>(&stdout)
        .map_err(|err| format!("failed to parse runtime {} JSON: {}", command_name, err))?;
    checks.push(DiagnosticCheck {
        name: format!("runtime{}Command", title_case(command_name)),
        status: "ok".to_string(),
        detail: command.join(" "),
    });
    Ok(value)
}

fn runtime_json_command(
    paths: &ProjectPaths,
    command_name: &str,
) -> Result<(Vec<String>, PathBuf), String> {
    let mut command = if paths.runtime_mode == "bundled" {
        vec![paths.runtime_path.clone()]
    } else {
        let mut parts = python_command_parts()?;
        parts.push("src/runtime_cli.py".to_string());
        parts
    };
    command.push(command_name.to_string());
    if command_name == "diagnostic" {
        command.extend([
            "--config".to_string(),
            paths.config_path.clone(),
            "--data-dir".to_string(),
            paths.data_dir.clone(),
        ]);
    }
    command.push("--json".to_string());

    let current_dir = if paths.runtime_mode == "bundled" {
        Path::new(&paths.runtime_path)
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(|| PathBuf::from("."))
    } else {
        project_root()?
    };
    Ok((command, current_dir))
}

fn scheduler_port_open() -> bool {
    let address = format!("{}:{}", SCHEDULER_HOST, SCHEDULER_PORT);
    let Ok(mut addrs) = address.to_socket_addrs() else {
        return false;
    };
    let Some(addr) = addrs.next() else {
        return false;
    };
    TcpStream::connect_timeout(&addr, Duration::from_millis(500)).is_ok()
}

fn push_check(checks: &mut Vec<DiagnosticCheck>, name: &str, ok: bool, detail: &str) {
    checks.push(DiagnosticCheck {
        name: name.to_string(),
        status: if ok { "ok" } else { "error" }.to_string(),
        detail: detail.to_string(),
    });
}

fn title_case(value: &str) -> String {
    let mut chars = value.chars();
    match chars.next() {
        Some(first) => format!("{}{}", first.to_ascii_uppercase(), chars.as_str()),
        None => String::new(),
    }
}
