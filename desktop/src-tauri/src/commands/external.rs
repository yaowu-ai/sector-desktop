use std::process::Command;

const BITBROWSER_DOWNLOAD_URL: &str = "https://www.bitbrowser.cn/download";

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppReleaseContext {
    pub version: String,
    pub platform: String,
    pub arch: String,
}

#[tauri::command]
pub fn get_app_release_context(app: tauri::AppHandle) -> AppReleaseContext {
    AppReleaseContext {
        version: app.package_info().version.to_string(),
        platform: normalize_platform(std::env::consts::OS).to_string(),
        arch: normalize_arch(std::env::consts::ARCH).to_string(),
    }
}

#[tauri::command]
pub fn open_bitbrowser_download_page() -> Result<(), String> {
    open_external_url(BITBROWSER_DOWNLOAD_URL)
}

#[tauri::command]
pub fn open_external_link(url: String) -> Result<(), String> {
    let normalized = url.trim();
    validate_external_url(normalized)?;
    open_external_url(normalized)
}

fn open_external_url(url: &str) -> Result<(), String> {
    open_external_url_impl(url)
        .map_err(|err| format!("failed to open system browser for external url: {}", err))
}

fn validate_external_url(url: &str) -> Result<(), String> {
    let normalized = url.trim();
    if let Ok(parsed) = reqwest::Url::parse(normalized) {
        if matches!(parsed.host_str(), Some("tiktok.com" | "www.tiktok.com")) {
            let path = parsed.path().strip_suffix('/').unwrap_or(parsed.path());
            let segments: Vec<_> = path.split('/').collect();
            if parsed.scheme() != "https"
                || !parsed.username().is_empty()
                || parsed.password().is_some()
                || parsed.port().is_some()
                || segments.len() != 4
                || !segments[1].starts_with('@')
                || segments[1].len() < 2
                || segments[2] != "video"
                || segments[3].is_empty()
                || !segments[3].bytes().all(|c| c.is_ascii_digit())
            {
                return Err("仅支持 HTTPS TikTok 作品链接".into());
            }
        }
    }
    if (normalized.starts_with("http://") || normalized.starts_with("https://"))
        && !normalized.contains('\n')
        && !normalized.contains('\r')
    {
        return Ok(());
    }
    Err("only http or https download links can be opened".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn tiktok_post_links_require_exact_https_post_path() {
        assert!(validate_external_url("https://www.tiktok.com/@alice/video/101").is_ok());
        assert!(validate_external_url("https://www.tiktok.com/@alice/video/101/").is_ok());
        assert!(validate_external_url("https://www.tiktok.com/@alice/video/101//").is_err());
        assert!(validate_external_url("http://www.tiktok.com/@alice/video/101").is_err());
        assert!(validate_external_url("https://www.tiktok.com/@alice").is_err());
        assert!(validate_external_url("https://www.tiktok.com/@alice/video/no-id").is_err());
        assert!(validate_external_url("https://www.bitbrowser.cn/download").is_ok());
    }
}

fn normalize_platform(platform: &str) -> &str {
    match platform {
        "windows" => "windows",
        "macos" => "macos",
        "linux" => "linux",
        other => other,
    }
}

fn normalize_arch(arch: &str) -> &str {
    match arch {
        "x86_64" => "x64",
        "aarch64" => "arm64",
        other => other,
    }
}

#[cfg(target_os = "windows")]
fn open_external_url_impl(url: &str) -> Result<(), String> {
    use std::os::windows::process::CommandExt;

    const CREATE_NO_WINDOW: u32 = 0x08000000;

    Command::new("rundll32.exe")
        .args(["url.dll,FileProtocolHandler", url])
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .map_err(|err| err.to_string())?;
    Ok(())
}

#[cfg(target_os = "macos")]
fn open_external_url_impl(url: &str) -> Result<(), String> {
    Command::new("/usr/bin/open")
        .arg(url)
        .spawn()
        .map_err(|err| err.to_string())?;
    Ok(())
}

#[cfg(target_os = "linux")]
fn open_external_url_impl(url: &str) -> Result<(), String> {
    Command::new("xdg-open")
        .arg(url)
        .spawn()
        .map_err(|err| err.to_string())?;
    Ok(())
}

#[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
fn open_external_url_impl(_url: &str) -> Result<(), String> {
    Err("opening external browser is not supported on this operating system".to_string())
}
