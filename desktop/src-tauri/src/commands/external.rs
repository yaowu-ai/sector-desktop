use std::process::Command;

const BITBROWSER_DOWNLOAD_URL: &str = "https://www.bitbrowser.cn/download";

#[tauri::command]
pub fn open_bitbrowser_download_page() -> Result<(), String> {
    open_external_url(BITBROWSER_DOWNLOAD_URL)
}

fn open_external_url(url: &str) -> Result<(), String> {
    open_external_url_impl(url).map_err(|err| {
        format!(
            "failed to open system browser for BitBrowser download page: {}",
            err
        )
    })
}

#[cfg(target_os = "windows")]
fn open_external_url_impl(url: &str) -> Result<(), String> {
    use std::os::windows::process::CommandExt;

    const CREATE_NO_WINDOW: u32 = 0x08000000;

    Command::new("cmd")
        .args(["/C", "start", "", url])
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
