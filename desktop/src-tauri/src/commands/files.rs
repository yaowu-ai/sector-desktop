use chrono::Local;
use serde::{Deserialize, Serialize};
use serde_yaml::Value;
use std::collections::HashSet;
use std::fs;
use std::path::PathBuf;

use crate::commands::config::{normalize_platform, save_platform_comment_files_config};
use crate::paths::{normalize, project_paths, ProjectPaths};

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CommentPoolsSnapshot {
    platform: String,
    general: CommentPool,
    brand: CommentPool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CommentPool {
    kind: String,
    path: String,
    raw_text: String,
    comments: Vec<String>,
    comment_lines: usize,
    blank_lines: usize,
    duplicates: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SaveCommentPoolsRequest {
    platform: Option<String>,
    general_text: String,
    brand_text: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SaveCommentPoolsResult {
    general: CommentPool,
    brand: CommentPool,
    backup_paths: Vec<String>,
    warnings: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportLogFileRequest {
    filename: String,
    content: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportLogFileResult {
    cancelled: bool,
    path: Option<String>,
}

#[tauri::command]
pub fn load_comment_pools(platform: Option<String>) -> Result<CommentPoolsSnapshot, String> {
    let paths = project_paths()?;
    let platform = normalize_platform(platform.as_deref().unwrap_or("tiktok"), "platform")?;
    let comment_paths = platform_comment_paths(&paths, &platform)?;
    Ok(CommentPoolsSnapshot {
        platform,
        general: read_comment_pool("general", &comment_paths.general)?,
        brand: read_comment_pool("brand", &comment_paths.brand)?,
    })
}

#[tauri::command]
pub fn save_comment_pools(
    request: SaveCommentPoolsRequest,
) -> Result<SaveCommentPoolsResult, String> {
    let paths = project_paths()?;
    let platform = normalize_platform(request.platform.as_deref().unwrap_or("tiktok"), "platform")?;
    let comment_paths = platform_comment_paths(&paths, &platform)?;
    let general_cleaned =
        parse_comment_text("general", &comment_paths.general, &request.general_text);
    let brand_cleaned = parse_comment_text("brand", &comment_paths.brand, &request.brand_text);

    let mut warnings = Vec::new();
    append_duplicate_warnings("通用评论池", &general_cleaned.duplicates, &mut warnings);
    append_duplicate_warnings("品牌评论池", &brand_cleaned.duplicates, &mut warnings);

    let backup_paths = vec![
        backup_comment_file(&comment_paths.general)?,
        backup_comment_file(&comment_paths.brand)?,
    ];
    let mut backup_paths = backup_paths;

    let config_backup = save_platform_comment_files_config(
        &platform,
        file_name(&comment_paths.general)?,
        file_name(&comment_paths.brand)?,
    )?;
    backup_paths.push(config_backup.backup_path);

    write_comment_file(&comment_paths.general, &general_cleaned.comments)?;
    write_comment_file(&comment_paths.brand, &brand_cleaned.comments)?;

    Ok(SaveCommentPoolsResult {
        general: read_comment_pool("general", &comment_paths.general)?,
        brand: read_comment_pool("brand", &comment_paths.brand)?,
        backup_paths,
        warnings,
    })
}

#[tauri::command]
pub fn export_log_file(request: ExportLogFileRequest) -> Result<ExportLogFileResult, String> {
    let Some(path) = choose_log_save_path(&request.filename)? else {
        return Ok(ExportLogFileResult {
            cancelled: true,
            path: None,
        });
    };

    fs::write(&path, request.content)
        .map_err(|err| format!("failed to write {}: {}", normalize(&path), err))?;

    Ok(ExportLogFileResult {
        cancelled: false,
        path: Some(normalize(&path)),
    })
}

struct CommentPoolPaths {
    general: String,
    brand: String,
}

fn platform_comment_paths(
    paths: &ProjectPaths,
    platform: &str,
) -> Result<CommentPoolPaths, String> {
    let config_dir = PathBuf::from(&paths.config_path)
        .parent()
        .ok_or_else(|| {
            format!(
                "failed to resolve config directory for {}",
                paths.config_path
            )
        })?
        .to_path_buf();
    let config_value = fs::read_to_string(&paths.config_path)
        .ok()
        .and_then(|raw| serde_yaml::from_str::<Value>(&raw).ok());
    let uses_shared_comment_pool = matches!(platform, "tiktok" | "instagram");
    let default_general_file = if uses_shared_comment_pool {
        file_name(&paths.comments_path)?.to_string()
    } else {
        format!("comments_{}.txt", platform)
    };
    let default_brand_file = if uses_shared_comment_pool {
        file_name(&paths.brand_comments_path)?.to_string()
    } else {
        format!("comments_{}_brand.txt", platform)
    };
    let general_file = platform_comment_file(
        config_value.as_ref(),
        platform,
        "general_file",
        &default_general_file,
    );
    let brand_file = platform_comment_file(
        config_value.as_ref(),
        platform,
        "target_file",
        &default_brand_file,
    );

    Ok(CommentPoolPaths {
        general: normalize(&config_dir.join(general_file)),
        brand: normalize(&config_dir.join(brand_file)),
    })
}

fn platform_comment_file(
    config: Option<&Value>,
    platform: &str,
    key: &str,
    default_file: &str,
) -> String {
    config
        .and_then(|config| config.get("platforms"))
        .and_then(|platforms| platforms.get(platform))
        .and_then(|platform_config| platform_config.get("comments"))
        .and_then(|comments| comments.get(key))
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .and_then(file_name_opt)
        .unwrap_or(default_file)
        .to_string()
}

fn read_comment_pool(kind: &str, path: &str) -> Result<CommentPool, String> {
    let raw_text = fs::read_to_string(path).unwrap_or_default();
    Ok(parse_comment_text(kind, path, &raw_text))
}

fn parse_comment_text(kind: &str, path: &str, raw_text: &str) -> CommentPool {
    let mut comments = Vec::new();
    let mut comment_lines = 0;
    let mut blank_lines = 0;
    let mut duplicates = Vec::new();
    let mut seen = HashSet::new();

    for line in raw_text.lines() {
        let value = line.trim();
        if value.is_empty() {
            blank_lines += 1;
            continue;
        }
        if value.starts_with('#') {
            comment_lines += 1;
            continue;
        }
        if !seen.insert(value.to_lowercase()) {
            duplicates.push(value.to_string());
            continue;
        }
        comments.push(value.to_string());
    }

    CommentPool {
        kind: kind.to_string(),
        path: path.to_string(),
        raw_text: raw_text.to_string(),
        comments,
        comment_lines,
        blank_lines,
        duplicates,
    }
}

fn write_comment_file(path: &str, comments: &[String]) -> Result<(), String> {
    let mut body = comments.join("\n");
    if !body.is_empty() {
        body.push('\n');
    }
    fs::write(path, body).map_err(|err| format!("failed to write {}: {}", path, err))
}

fn backup_comment_file(path: &str) -> Result<String, String> {
    let source = PathBuf::from(path);
    let config_dir = source
        .parent()
        .ok_or_else(|| format!("failed to resolve parent directory for {}", path))?;
    fs::create_dir_all(config_dir)
        .map_err(|err| format!("failed to create config directory {}: {}", path, err))?;
    if !source.exists() {
        fs::write(&source, "")
            .map_err(|err| format!("failed to create missing comment file {}: {}", path, err))?;
    }

    let backup_dir = config_dir.join("backups");
    fs::create_dir_all(&backup_dir).map_err(|err| {
        format!(
            "failed to create backup directory {}: {}",
            normalize(&backup_dir),
            err
        )
    })?;

    let stem = source
        .file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or("comments");
    let extension = source
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or("txt");
    let filename = format!(
        "{}.{}.{}",
        stem,
        Local::now().format("%Y%m%d-%H%M%S"),
        extension
    );
    let target = backup_dir.join(filename);
    fs::copy(&source, &target).map_err(|err| {
        format!(
            "failed to backup {} to {}: {}",
            path,
            normalize(&target),
            err
        )
    })?;

    Ok(normalize(&target))
}

fn file_name(path: &str) -> Result<&str, String> {
    file_name_opt(path).ok_or_else(|| format!("failed to read file name from {}", path))
}

fn file_name_opt(path: &str) -> Option<&str> {
    std::path::Path::new(path)
        .file_name()
        .and_then(|value| value.to_str())
}

fn append_duplicate_warnings(label: &str, duplicates: &[String], warnings: &mut Vec<String>) {
    if duplicates.is_empty() {
        return;
    }
    warnings.push(format!(
        "{} 已忽略 {} 条重复评论：{}",
        label,
        duplicates.len(),
        duplicates
            .iter()
            .take(5)
            .cloned()
            .collect::<Vec<_>>()
            .join(" / ")
    ));
}

#[cfg(windows)]
fn choose_log_save_path(default_filename: &str) -> Result<Option<PathBuf>, String> {
    use windows_sys::Win32::UI::Controls::Dialogs::{
        CommDlgExtendedError, GetSaveFileNameW, OFN_NOCHANGEDIR, OFN_OVERWRITEPROMPT,
        OFN_PATHMUSTEXIST, OPENFILENAMEW,
    };

    let mut file_buffer = [0u16; 32768];
    let filename = safe_default_filename(default_filename);
    let filename_wide: Vec<u16> = filename.encode_utf16().collect();
    for (index, value) in filename_wide.iter().take(file_buffer.len() - 1).enumerate() {
        file_buffer[index] = *value;
    }

    let filter: Vec<u16> =
        "Log files (*.log)\0*.log\0Text files (*.txt)\0*.txt\0All files (*.*)\0*.*\0\0"
            .encode_utf16()
            .collect();
    let default_ext: Vec<u16> = "log\0".encode_utf16().collect();
    let title: Vec<u16> = "保存日志\0".encode_utf16().collect();

    let mut dialog = OPENFILENAMEW {
        lStructSize: std::mem::size_of::<OPENFILENAMEW>() as u32,
        lpstrFilter: filter.as_ptr(),
        lpstrFile: file_buffer.as_mut_ptr(),
        nMaxFile: file_buffer.len() as u32,
        lpstrDefExt: default_ext.as_ptr(),
        lpstrTitle: title.as_ptr(),
        Flags: OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR,
        ..OPENFILENAMEW::default()
    };

    let selected = unsafe { GetSaveFileNameW(&mut dialog) };
    if selected == 0 {
        let error = unsafe { CommDlgExtendedError() };
        if error == 0 {
            return Ok(None);
        }
        return Err(format!("failed to open save dialog: {}", error));
    }

    let len = file_buffer
        .iter()
        .position(|value| *value == 0)
        .unwrap_or(file_buffer.len());
    Ok(Some(PathBuf::from(String::from_utf16_lossy(
        &file_buffer[..len],
    ))))
}

#[cfg(not(windows))]
fn choose_log_save_path(_default_filename: &str) -> Result<Option<PathBuf>, String> {
    Err("custom log download location is only supported on Windows desktop builds".to_string())
}

fn safe_default_filename(filename: &str) -> String {
    let cleaned: String = filename
        .chars()
        .map(|value| match value {
            '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*' => '_',
            value if value.is_control() => '_',
            value => value,
        })
        .collect();
    let cleaned = cleaned.trim().trim_matches('.').to_string();
    if cleaned.is_empty() {
        "account-matrix.log".to_string()
    } else {
        cleaned
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn comment_parser_ignores_blank_comment_and_duplicate_lines() {
        let pool = parse_comment_text(
            "general",
            "comments.txt",
            " first comment \n\n# ignored\nSecond\nsecond\n",
        );

        assert_eq!(
            pool.comments,
            vec!["first comment".to_string(), "Second".to_string()]
        );
        assert_eq!(pool.blank_lines, 1);
        assert_eq!(pool.comment_lines, 1);
        assert_eq!(pool.duplicates, vec!["second".to_string()]);
    }

    #[test]
    fn comment_writer_uses_one_clean_comment_per_line() {
        let path = std::env::temp_dir().join(format!(
            "account-matrix-comments-{}-{}.txt",
            std::process::id(),
            "writer"
        ));
        let path_text = path.to_string_lossy().to_string();

        write_comment_file(&path_text, &["one".to_string(), "two".to_string()])
            .expect("comment file should be written");
        let content = fs::read_to_string(&path).expect("comment file should be readable");
        let _ = fs::remove_file(&path);

        assert_eq!(content, "one\ntwo\n");
    }

    #[test]
    fn platform_comment_file_uses_platform_config_and_filename_only() {
        let config: Value = serde_yaml::from_str(
            r#"
platforms:
  instagram:
    comments:
      general_file: config/comments_instagram.txt
      target_file: comments_instagram_brand.txt
"#,
        )
        .expect("test config should parse");

        assert_eq!(
            platform_comment_file(
                Some(&config),
                "instagram",
                "general_file",
                "comments_instagram.txt"
            ),
            "comments_instagram.txt"
        );
        assert_eq!(
            platform_comment_file(Some(&config), "instagram", "target_file", "fallback.txt"),
            "comments_instagram_brand.txt"
        );
        assert_eq!(
            platform_comment_file(
                Some(&config),
                "whatsapp",
                "general_file",
                "comments_whatsapp.txt"
            ),
            "comments_whatsapp.txt"
        );
    }

    #[test]
    fn safe_default_filename_removes_path_and_windows_reserved_chars() {
        assert_eq!(safe_default_filename("../bad:name?.log"), "_bad_name_.log");
        assert_eq!(safe_default_filename("..."), "account-matrix.log");
    }
}
