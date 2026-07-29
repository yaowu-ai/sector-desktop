use serde::{Deserialize, Serialize};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

const APP_DIR_NAME: &str = "Account Matrix";
const ENV_PROJECT_ROOT: &str = "ACCOUNT_MATRIX_ROOT";
const ENV_SETTINGS_PATH: &str = "ACCOUNT_MATRIX_SETTINGS";
const LOCAL_SETTINGS_FILE: &str = "local-settings.json";
const RUNTIME_MANIFEST_FILE: &str = "runtime-manifest.json";
static RESOURCE_DIR: OnceLock<PathBuf> = OnceLock::new();

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectPaths {
    pub runtime_mode: String,
    pub project_root: String,
    pub config_path: String,
    pub comments_path: String,
    pub brand_comments_path: String,
    pub data_dir: String,
    pub logs_dir: String,
    pub actions_db_path: String,
    pub sessions_log_path: String,
    pub lock_file_path: String,
    pub src_dir: String,
    pub settings_path: String,
    pub runtime_path: String,
    pub runtime_manifest_path: String,
    pub runtime_version: Option<String>,
    pub python_executable: String,
    pub default_browser_provider: String,
    pub chromium_executable: String,
    pub bitbrowser_api_url: String,
    pub auto_close_profile: bool,
    pub log_poll_interval_seconds: u64,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LocalAppSettings {
    pub runtime_mode: Option<String>,
    pub project_root: Option<String>,
    pub python_executable: Option<String>,
    pub default_browser_provider: Option<String>,
    pub chromium_executable: Option<String>,
    pub bitbrowser_api_url: Option<String>,
    pub data_dir: Option<String>,
    pub config_path: Option<String>,
    pub comments_path: Option<String>,
    pub brand_comments_path: Option<String>,
    pub runtime_path: Option<String>,
    pub runtime_manifest_path: Option<String>,
    pub runtime_version: Option<String>,
    pub initialized_app_version: Option<String>,
    pub auto_close_profile: Option<bool>,
    pub log_poll_interval_seconds: Option<u64>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppInitializationStatus {
    pub initialized_app_version: String,
    pub settings_dir: String,
    pub config_dir: String,
    pub backups_dir: String,
    pub data_dir: String,
    pub logs_dir: String,
    pub settings_path: String,
    pub settings_created: bool,
    pub templates_copied: Vec<String>,
    pub runtime_mode: String,
}

#[derive(Debug, Clone)]
struct UserRuntimeDirs {
    app_config_root: PathBuf,
    settings_dir: PathBuf,
    config_dir: PathBuf,
    backups_dir: PathBuf,
    data_dir: PathBuf,
    logs_dir: PathBuf,
}

pub fn initialize_user_environment(
    app_version: &str,
    resource_dir: Option<PathBuf>,
) -> Result<AppInitializationStatus, String> {
    if let Some(dir) = resource_dir.clone() {
        let _ = RESOURCE_DIR.set(dir);
    }
    let dirs = user_runtime_dirs()?;
    fs::create_dir_all(&dirs.settings_dir).map_err(|err| {
        format!(
            "failed to create {}: {}",
            normalize(&dirs.settings_dir),
            err
        )
    })?;
    fs::create_dir_all(&dirs.config_dir)
        .map_err(|err| format!("failed to create {}: {}", normalize(&dirs.config_dir), err))?;
    fs::create_dir_all(&dirs.backups_dir)
        .map_err(|err| format!("failed to create {}: {}", normalize(&dirs.backups_dir), err))?;
    fs::create_dir_all(&dirs.data_dir)
        .map_err(|err| format!("failed to create {}: {}", normalize(&dirs.data_dir), err))?;
    fs::create_dir_all(&dirs.logs_dir)
        .map_err(|err| format!("failed to create {}: {}", normalize(&dirs.logs_dir), err))?;

    let template_dir = template_config_dir(resource_dir)?;
    let mut templates_copied = Vec::new();
    for name in ["accounts.yaml", "comments.txt", "comments_brand.txt"] {
        let source = template_dir.join(name);
        let target = dirs.config_dir.join(name);
        if !target.exists() {
            fs::copy(&source, &target).map_err(|err| {
                format!(
                    "failed to copy template {} to {}: {}",
                    normalize(&source),
                    normalize(&target),
                    err
                )
            })?;
            templates_copied.push(normalize(&target));
        }
    }

    let default_settings_path = app_data_settings_path()?;
    let settings_created = if candidate_settings_paths()
        .into_iter()
        .any(|path| path.exists())
    {
        false
    } else {
        let settings = LocalAppSettings {
            runtime_mode: Some(default_runtime_mode()),
            initialized_app_version: Some(app_version.to_string()),
            ..LocalAppSettings::default()
        };
        save_local_app_settings_to_path(&settings, &default_settings_path)?;
        true
    };

    let runtime_mode = load_local_app_settings()
        .unwrap_or_default()
        .runtime_mode
        .unwrap_or_else(default_runtime_mode);

    Ok(AppInitializationStatus {
        initialized_app_version: app_version.to_string(),
        settings_dir: normalize(&dirs.settings_dir),
        config_dir: normalize(&dirs.config_dir),
        backups_dir: normalize(&dirs.backups_dir),
        data_dir: normalize(&dirs.data_dir),
        logs_dir: normalize(&dirs.logs_dir),
        settings_path: normalize(&settings_path()?),
        settings_created,
        templates_copied,
        runtime_mode,
    })
}

pub fn project_root() -> Result<PathBuf, String> {
    if let Some(root) = env::var(ENV_PROJECT_ROOT)
        .ok()
        .as_deref()
        .and_then(non_empty)
    {
        return Ok(PathBuf::from(root));
    }

    let settings = load_local_app_settings().unwrap_or_default();
    if let Some(root) = settings.project_root.as_deref().and_then(non_empty) {
        return Ok(PathBuf::from(root));
    }
    discover_project_root().or_else(|_| default_project_root())
}

pub fn default_project_root() -> Result<PathBuf, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let desktop_dir = manifest_dir
        .parent()
        .ok_or_else(|| "failed to resolve desktop directory".to_string())?;
    let root = desktop_dir
        .parent()
        .ok_or_else(|| "failed to resolve project root from desktop/..".to_string())?;

    Ok(root.to_path_buf())
}

pub fn project_paths() -> Result<ProjectPaths, String> {
    let settings = load_local_app_settings().unwrap_or_default();
    let runtime_mode = effective_runtime_mode(&settings);
    let user_dirs = user_runtime_dirs()?;
    let root = if runtime_mode == "source" {
        project_root()?
    } else {
        project_root().unwrap_or_default()
    };
    let source_base = if root.as_os_str().is_empty() {
        default_project_root().unwrap_or_else(|_| PathBuf::from("."))
    } else {
        root.clone()
    };
    let config_base = if runtime_mode == "source" {
        source_base.join("config")
    } else {
        user_dirs.config_dir.clone()
    };
    let data_default = if runtime_mode == "source" {
        source_base.join("data")
    } else {
        user_dirs.data_dir.clone()
    };
    let resolve_base = if runtime_mode == "source" {
        source_base.as_path()
    } else {
        user_dirs.app_config_root.as_path()
    };
    let data_dir = resolve_path(settings.data_dir.as_deref(), data_default, resolve_base);
    let config_path = resolve_path(
        settings.config_path.as_deref(),
        config_base.join("accounts.yaml"),
        resolve_base,
    );
    let comments_path = resolve_path(
        settings.comments_path.as_deref(),
        config_base.join("comments.txt"),
        resolve_base,
    );
    let brand_comments_path = resolve_path(
        settings.brand_comments_path.as_deref(),
        config_base.join("comments_brand.txt"),
        resolve_base,
    );
    let runtime_path = resolve_path(
        settings.runtime_path.as_deref(),
        bundled_runtime_exe_path()?,
        resolve_base,
    );
    let runtime_manifest_path = resolve_path(
        settings.runtime_manifest_path.as_deref(),
        bundled_runtime_manifest_path()?,
        resolve_base,
    );
    let logs_dir = if runtime_mode == "source" {
        data_dir.clone()
    } else {
        user_dirs.logs_dir.clone()
    };
    let runtime_version = settings
        .runtime_version
        .clone()
        .or_else(|| read_runtime_version(&runtime_manifest_path));

    Ok(ProjectPaths {
        runtime_mode,
        project_root: normalize(&root),
        config_path: normalize(&config_path),
        comments_path: normalize(&comments_path),
        brand_comments_path: normalize(&brand_comments_path),
        data_dir: normalize(&data_dir),
        logs_dir: normalize(&logs_dir),
        actions_db_path: normalize(&data_dir.join("actions.db")),
        sessions_log_path: normalize(&data_dir.join("sessions.log")),
        lock_file_path: normalize(&data_dir.join("run.lock")),
        src_dir: normalize(&source_base.join("src")),
        settings_path: normalize(&settings_path()?),
        runtime_path: normalize(&runtime_path),
        runtime_manifest_path: normalize(&runtime_manifest_path),
        runtime_version,
        python_executable: effective_python_executable(&settings),
        default_browser_provider: effective_default_browser_provider(&settings),
        chromium_executable: effective_chromium_executable(&settings),
        bitbrowser_api_url: effective_bitbrowser_api_url(&settings),
        auto_close_profile: settings.auto_close_profile.unwrap_or(true),
        log_poll_interval_seconds: settings.log_poll_interval_seconds.unwrap_or(3).max(1),
    })
}

pub fn load_local_app_settings() -> Result<LocalAppSettings, String> {
    let Some(path) = candidate_settings_paths()
        .into_iter()
        .find(|path| path.exists())
    else {
        return Ok(LocalAppSettings::default());
    };
    if !path.exists() {
        return Ok(LocalAppSettings::default());
    }
    let raw = fs::read_to_string(&path)
        .map_err(|err| format!("failed to read {}: {}", normalize(&path), err))?;
    serde_json::from_str(&raw)
        .map_err(|err| format!("failed to parse {}: {}", normalize(&path), err))
}

pub fn save_local_app_settings(settings: &LocalAppSettings) -> Result<String, String> {
    let path = settings_path()?;
    save_local_app_settings_to_path(settings, &path)?;
    Ok(normalize(&path))
}

fn save_local_app_settings_to_path(settings: &LocalAppSettings, path: &Path) -> Result<(), String> {
    let raw = serde_json::to_string_pretty(settings)
        .map_err(|err| format!("failed to serialize local settings: {}", err))?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("failed to create {}: {}", normalize(parent), err))?;
    }
    fs::write(&path, format!("{}\n", raw))
        .map_err(|err| format!("failed to write {}: {}", normalize(&path), err))?;
    Ok(())
}

pub fn python_command_parts() -> Result<Vec<String>, String> {
    let settings = load_local_app_settings().unwrap_or_default();
    let executable = effective_python_executable(&settings);
    if executable == "py" {
        Ok(vec![executable, "-3.13".to_string()])
    } else {
        Ok(vec![executable])
    }
}

pub fn effective_bitbrowser_api_url(settings: &LocalAppSettings) -> String {
    settings
        .bitbrowser_api_url
        .as_deref()
        .and_then(non_empty)
        .unwrap_or("http://127.0.0.1:54345")
        .to_string()
}

pub fn effective_default_browser_provider(settings: &LocalAppSettings) -> String {
    match settings
        .default_browser_provider
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        Some("bitbrowser") => "bitbrowser".to_string(),
        Some("builtin_chromium") => "builtin_chromium".to_string(),
        _ => "bitbrowser".to_string(),
    }
}

pub fn effective_chromium_executable(settings: &LocalAppSettings) -> String {
    settings
        .chromium_executable
        .as_deref()
        .and_then(non_empty)
        .unwrap_or("")
        .to_string()
}

pub fn settings_path() -> Result<PathBuf, String> {
    if let Some(path) = env::var(ENV_SETTINGS_PATH)
        .ok()
        .as_deref()
        .and_then(non_empty)
    {
        return Ok(PathBuf::from(path));
    }

    if let Some(existing) = candidate_settings_paths()
        .into_iter()
        .find(|path| path.exists())
    {
        return Ok(existing);
    }

    app_data_settings_path().or_else(|_| default_desktop_settings_path())
}

pub fn normalize(path: &std::path::Path) -> String {
    path.to_string_lossy().replace('\\', "/")
}

fn effective_python_executable(settings: &LocalAppSettings) -> String {
    settings
        .python_executable
        .as_deref()
        .and_then(non_empty)
        .unwrap_or(default_python_executable())
        .to_string()
}

fn effective_runtime_mode(settings: &LocalAppSettings) -> String {
    match settings
        .runtime_mode
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        Some("bundled") => "bundled".to_string(),
        Some("source") => "source".to_string(),
        _ => default_runtime_mode(),
    }
}

fn default_runtime_mode() -> String {
    if cfg!(debug_assertions) {
        "source".to_string()
    } else {
        "bundled".to_string()
    }
}

fn bundled_runtime_exe_path() -> Result<PathBuf, String> {
    let runtime_dir = bundled_runtime_dir()?;
    let exe = if cfg!(windows) {
        "account-matrix-runtime.exe"
    } else {
        "account-matrix-runtime"
    };
    Ok(runtime_dir.join(exe))
}

fn bundled_runtime_manifest_path() -> Result<PathBuf, String> {
    Ok(bundled_runtime_dir()?.join(RUNTIME_MANIFEST_FILE))
}

fn bundled_runtime_dir() -> Result<PathBuf, String> {
    if let Some(resource_dir) = RESOURCE_DIR.get() {
        return Ok(resource_dir.join("runtime"));
    }
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    Ok(manifest_dir.join("resources").join("runtime"))
}

fn read_runtime_version(path: &Path) -> Option<String> {
    let raw = fs::read_to_string(path).ok()?;
    let value: serde_json::Value = serde_json::from_str(&raw).ok()?;
    value
        .get("runtimeVersion")
        .and_then(serde_json::Value::as_str)
        .map(ToString::to_string)
}

fn candidate_settings_paths() -> Vec<PathBuf> {
    let mut paths = Vec::new();
    if let Some(path) = env::var(ENV_SETTINGS_PATH)
        .ok()
        .as_deref()
        .and_then(non_empty)
    {
        push_unique(&mut paths, PathBuf::from(path));
    }

    if let Ok(path) = app_data_settings_path() {
        push_unique(&mut paths, path);
    }
    if let Ok(path) = legacy_app_data_settings_path() {
        push_unique(&mut paths, path);
    }
    for root in discover_project_root_candidates() {
        push_unique(&mut paths, root.join("desktop").join("local-settings.json"));
    }
    if let Ok(path) = default_desktop_settings_path() {
        push_unique(&mut paths, path);
    }
    paths
}

fn discover_project_root() -> Result<PathBuf, String> {
    discover_project_root_candidates()
        .into_iter()
        .find(|path| is_project_root(path))
        .ok_or_else(|| {
            "failed to discover account-matrix project root; configure it in Settings or set ACCOUNT_MATRIX_ROOT"
                .to_string()
        })
}

fn discover_project_root_candidates() -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    if let Some(root) = env::var(ENV_PROJECT_ROOT)
        .ok()
        .as_deref()
        .and_then(non_empty)
    {
        push_unique(&mut candidates, PathBuf::from(root));
    }

    if let Ok(current_dir) = env::current_dir() {
        add_root_candidates_from(&mut candidates, &current_dir);
    }

    if let Ok(exe_path) = env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            add_root_candidates_from(&mut candidates, exe_dir);
        }
    }

    if let Ok(root) = default_project_root() {
        push_unique(&mut candidates, root);
    }

    candidates
}

fn add_root_candidates_from(candidates: &mut Vec<PathBuf>, start: &Path) {
    let mut current = Some(start);
    while let Some(dir) = current {
        push_unique(candidates, dir.to_path_buf());
        push_unique(candidates, dir.join("account-matrix"));
        current = dir.parent();
    }
}

fn is_project_root(path: &Path) -> bool {
    path.join("config").join("accounts.yaml").is_file()
        && path.join("src").join("main.py").is_file()
}

fn app_data_settings_path() -> Result<PathBuf, String> {
    Ok(user_runtime_dirs()?.settings_dir.join(LOCAL_SETTINGS_FILE))
}

fn legacy_app_data_settings_path() -> Result<PathBuf, String> {
    Ok(app_config_root()?.join(LOCAL_SETTINGS_FILE))
}

fn default_desktop_settings_path() -> Result<PathBuf, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let desktop_dir = manifest_dir
        .parent()
        .ok_or_else(|| "failed to resolve desktop directory".to_string())?;
    Ok(desktop_dir.join("local-settings.json"))
}

fn user_runtime_dirs() -> Result<UserRuntimeDirs, String> {
    let app_config_root = app_config_root()?;
    let app_local_root = app_local_root()?;
    let settings_dir = app_config_root.join("settings");
    let config_dir = app_config_root.join("config");
    let backups_dir = config_dir.join("backups");
    let data_dir = app_local_root.join("data");
    let logs_dir = app_local_root.join("logs");
    Ok(UserRuntimeDirs {
        app_config_root,
        settings_dir,
        config_dir,
        backups_dir,
        data_dir,
        logs_dir,
    })
}

fn app_config_root() -> Result<PathBuf, String> {
    Ok(app_config_base()?.join(APP_DIR_NAME))
}

fn app_local_root() -> Result<PathBuf, String> {
    Ok(app_local_base()?.join(APP_DIR_NAME))
}

fn default_python_executable() -> &'static str {
    if cfg!(windows) {
        "py"
    } else {
        "python3"
    }
}

fn app_config_base() -> Result<PathBuf, String> {
    if cfg!(windows) {
        return env::var("APPDATA")
            .ok()
            .or_else(|| env::var("LOCALAPPDATA").ok())
            .map(PathBuf::from)
            .ok_or_else(|| "APPDATA and LOCALAPPDATA are not set".to_string());
    }

    if cfg!(target_os = "macos") {
        return Ok(home_dir()?.join("Library").join("Application Support"));
    }

    env::var("XDG_CONFIG_HOME")
        .ok()
        .map(PathBuf::from)
        .or_else(|| home_dir().ok().map(|home| home.join(".config")))
        .ok_or_else(|| "XDG_CONFIG_HOME and HOME are not set".to_string())
}

fn app_local_base() -> Result<PathBuf, String> {
    if cfg!(windows) {
        return env::var("LOCALAPPDATA")
            .ok()
            .or_else(|| env::var("APPDATA").ok())
            .map(PathBuf::from)
            .ok_or_else(|| "LOCALAPPDATA and APPDATA are not set".to_string());
    }

    if cfg!(target_os = "macos") {
        return Ok(home_dir()?.join("Library").join("Application Support"));
    }

    env::var("XDG_DATA_HOME")
        .ok()
        .map(PathBuf::from)
        .or_else(|| {
            home_dir()
                .ok()
                .map(|home| home.join(".local").join("share"))
        })
        .ok_or_else(|| "XDG_DATA_HOME and HOME are not set".to_string())
}

fn home_dir() -> Result<PathBuf, String> {
    env::var("HOME")
        .ok()
        .map(PathBuf::from)
        .filter(|path| !path.as_os_str().is_empty())
        .ok_or_else(|| "HOME is not set".to_string())
}

fn template_config_dir(resource_dir: Option<PathBuf>) -> Result<PathBuf, String> {
    let resource_candidate = resource_dir
        .map(|dir| dir.join("templates").join("config"))
        .filter(|dir| dir.is_dir());
    if let Some(dir) = resource_candidate {
        return Ok(dir);
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let dev_dir = manifest_dir
        .join("resources")
        .join("templates")
        .join("config");
    if dev_dir.is_dir() {
        return Ok(dev_dir);
    }

    Err(format!(
        "template config directory is missing: {}",
        normalize(&dev_dir)
    ))
}

fn push_unique(paths: &mut Vec<PathBuf>, path: PathBuf) {
    if !paths.iter().any(|existing| existing == &path) {
        paths.push(path);
    }
}

fn resolve_path(value: Option<&str>, default_path: PathBuf, base: &Path) -> PathBuf {
    let Some(value) = value.and_then(non_empty) else {
        return default_path;
    };
    let path = PathBuf::from(value);
    if path.is_absolute() {
        path
    } else {
        base.join(path)
    }
}

fn non_empty(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed)
    }
}
