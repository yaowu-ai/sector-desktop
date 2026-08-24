use serde::{Deserialize, Serialize};
use std::fs;

use crate::paths::project_paths;
use crate::security::redact_text;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TailRequest {
    offset: u64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LogChunk {
    offset: u64,
    next_offset: u64,
    content: String,
    exists: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ClearLogResult {
    path: String,
    cleared: bool,
}

#[tauri::command]
pub fn tail_session_log(request: TailRequest) -> Result<LogChunk, String> {
    let paths = project_paths()?;
    let path = std::path::PathBuf::from(&paths.sessions_log_path);

    if !path.exists() {
        return Ok(LogChunk {
            offset: request.offset,
            next_offset: request.offset,
            content: String::new(),
            exists: false,
        });
    }

    let bytes = fs::read(&path)
        .map_err(|err| format!("failed to read {}: {}", paths.sessions_log_path, err))?;
    let start = request.offset.min(bytes.len() as u64) as usize;
    let content = String::from_utf8_lossy(&bytes[start..]).to_string();

    Ok(LogChunk {
        offset: request.offset,
        next_offset: bytes.len() as u64,
        content: redact_text(&content, &[]),
        exists: true,
    })
}

#[tauri::command]
pub fn clear_session_log() -> Result<ClearLogResult, String> {
    let paths = project_paths()?;
    let path = std::path::PathBuf::from(&paths.sessions_log_path);
    if !path.exists() {
        return Ok(ClearLogResult {
            path: paths.sessions_log_path,
            cleared: false,
        });
    }
    fs::write(&path, "")
        .map_err(|err| format!("failed to clear {}: {}", paths.sessions_log_path, err))?;
    Ok(ClearLogResult {
        path: paths.sessions_log_path,
        cleared: true,
    })
}
