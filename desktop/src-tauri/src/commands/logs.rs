use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;

use crate::paths::project_paths;
use crate::security::redact_text;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TailRequest {
    offset: u64,
    generation: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LogChunk {
    offset: u64,
    next_offset: u64,
    content: String,
    exists: bool,
    generation: Option<String>,
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

    read_session_chunk(&path, request.offset, request.generation.as_deref())
        .map_err(|err| format!("failed to read {}: {}", paths.sessions_log_path, err))
}

fn generation(path: &Path) -> std::io::Result<String> {
    file_generation(&fs::File::open(path)?)
}

fn file_generation(file: &fs::File) -> std::io::Result<String> {
    #[cfg(windows)]
    {
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::Storage::FileSystem::{
            GetFileInformationByHandle, BY_HANDLE_FILE_INFORMATION,
        };
        let mut info: BY_HANDLE_FILE_INFORMATION = unsafe { std::mem::zeroed() };
        if unsafe { GetFileInformationByHandle(file.as_raw_handle() as _, &mut info) } == 0 {
            return Err(std::io::Error::last_os_error());
        }
        Ok(format!(
            "{}-{}-{}",
            info.dwVolumeSerialNumber, info.nFileIndexHigh, info.nFileIndexLow
        ))
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        let metadata = file.metadata()?;
        Ok(format!("{}-{}", metadata.dev(), metadata.ino()))
    }
}

fn read_session_chunk(
    path: &Path,
    offset: u64,
    previous: Option<&str>,
) -> std::io::Result<LogChunk> {
    const CHUNK_BYTES: u64 = 64 * 1024;
    let mut file = match fs::File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(LogChunk {
                offset,
                next_offset: offset,
                content: String::new(),
                exists: false,
                generation: previous.map(str::to_owned),
            });
        }
        Err(error) => return Err(error),
    };
    let current = file_generation(&file)?;
    let mut source_generation = current.clone();
    let mut start = offset;
    if previous.is_some_and(|previous| previous != current) {
        // Finish an unread rotated file before consuming the new one.
        let archive = fs::read_dir(path.parent().unwrap_or(Path::new(".")))?
            .filter_map(Result::ok)
            .find(|entry| {
                let name = entry.file_name();
                let name = name.to_string_lossy();
                name.starts_with("sessions.")
                    && name.ends_with(".log")
                    && entry.file_type().map(|t| t.is_file()).unwrap_or(false)
                    && generation(&entry.path()).ok().as_deref() == previous
                    && entry.metadata().map(|m| m.len() > offset).unwrap_or(false)
            });
        if let Some(archive) = archive {
            if let Ok(archived_file) = fs::File::open(archive.path()) {
                source_generation = file_generation(&archived_file)?;
                file = archived_file;
            } else {
                start = 0;
            }
        } else {
            start = 0;
        }
    }
    let length = file.metadata()?.len();
    if start > length {
        start = 0;
    }
    if previous.is_none() {
        start = length.saturating_sub(CHUNK_BYTES);
    }
    file.seek(SeekFrom::Start(start))?;
    let mut bytes = Vec::new();
    file.take(CHUNK_BYTES).read_to_end(&mut bytes)?;
    // Leave an incomplete UTF-8 character for the next poll.
    if let Err(error) = std::str::from_utf8(&bytes) {
        if error.error_len().is_none() && error.valid_up_to() > 0 {
            bytes.truncate(error.valid_up_to());
        }
    }
    let mut content = redact_text(&String::from_utf8_lossy(&bytes), &[]);
    if bytes.ends_with(b"\n") {
        content.push('\n');
    }
    Ok(LogChunk {
        offset: start,
        next_offset: start + bytes.len() as u64,
        content,
        exists: true,
        generation: Some(source_generation),
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tail_is_bounded_and_finishes_old_file_after_rotation() {
        let dir = std::env::current_dir().unwrap().join(format!(
            "log-tail-test-{}",
            chrono::Utc::now().timestamp_nanos_opt().unwrap()
        ));
        fs::create_dir(&dir).unwrap();
        let path = dir.join("sessions.log");
        fs::write(&path, "x".repeat(200_000)).unwrap();
        let first = read_session_chunk(&path, 0, None).unwrap();
        assert_eq!(first.content.len(), 64 * 1024);
        assert_eq!(first.next_offset, 200_000);
        OpenOptions::new()
            .append(true)
            .open(&path)
            .unwrap()
            .write_all(b"unread\n")
            .unwrap();
        fs::rename(&path, dir.join("sessions.20261125-120000-1.log")).unwrap();
        let gap =
            read_session_chunk(&path, first.next_offset, first.generation.as_deref()).unwrap();
        assert!(!gap.exists);
        assert_eq!(gap.next_offset, first.next_offset);
        assert_eq!(gap.generation, first.generation);
        fs::write(&path, "new\n").unwrap();
        let old =
            read_session_chunk(&path, first.next_offset, first.generation.as_deref()).unwrap();
        assert_eq!(old.content, "unread\n");
        let new = read_session_chunk(&path, old.next_offset, old.generation.as_deref()).unwrap();
        assert_eq!(new.content, "new\n");
        assert_ne!(new.generation, first.generation);
        fs::remove_dir_all(dir).unwrap();
    }

    use std::fs::OpenOptions;
    use std::io::Write;
}
