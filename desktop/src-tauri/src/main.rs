#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod paths;
mod security;
mod state;

use tauri::Manager;

fn main() {
    tauri::Builder::default()
        .manage(state::AppState::default())
        .setup(|app| {
            let resource_dir = app.path().resource_dir().ok();
            let status = paths::initialize_user_environment(
                &app.package_info().version.to_string(),
                resource_dir,
            )
            .map_err(|err| tauri::Error::Anyhow(anyhow::anyhow!(err)))?;
            let state = app.state::<state::AppState>();
            let mut init_status = state.initialization_status.lock().map_err(|_| {
                tauri::Error::Anyhow(anyhow::anyhow!("failed to lock initialization state"))
            })?;
            *init_status = Some(status);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::config::get_project_paths,
            commands::config::load_config,
            commands::config::load_accounts,
            commands::config::validate_config,
            commands::config::backup_config,
            commands::config::preview_config_migration,
            commands::config::apply_config_migration,
            commands::config::save_config,
            commands::config::save_accounts,
            commands::config::get_login_credential_status,
            commands::config::save_login_password,
            commands::config::delete_login_password,
            commands::config::save_fyp_settings,
            commands::config::save_target_engagement_settings,
            commands::config::save_scheduler_settings,
            commands::config::save_notify_settings,
            commands::config::query_account_logs,
            commands::settings::load_system_settings,
            commands::settings::get_initialization_status,
            commands::settings::save_system_settings,
            commands::settings::test_notification,
            commands::diagnostics::get_runtime_diagnostics,
            commands::diagnostics::export_support_bundle,
            commands::bitbrowser::check_bitbrowser_api,
            commands::bitbrowser::get_browser_provider_matrix,
            commands::bitbrowser::diagnose_account_browser,
            commands::bitbrowser::get_builtin_chromium_status,
            commands::bitbrowser::cleanup_builtin_chromium_data,
            commands::bitbrowser::list_browser_profiles,
            commands::bitbrowser::get_profile_status,
            commands::bitbrowser::open_profile,
            commands::bitbrowser::close_profile,
            commands::bitbrowser::resolve_cdp_page_ws,
            commands::bitbrowser::capture_browser_preview,
            commands::bitbrowser::check_proxy,
            commands::bitbrowser::create_single_browser_profile,
            commands::bitbrowser::create_batch_browser_profiles,
            commands::bitbrowser::sync_accounts_dry_run,
            commands::bitbrowser::sync_accounts_apply,
            commands::files::load_comment_pools,
            commands::files::save_comment_pools,
            commands::files::export_log_file,
            commands::process::get_current_run_status,
            commands::process::run_python_script,
            commands::process::run_gmail_setup,
            commands::process::run_platform_task,
            commands::logs::tail_session_log,
            commands::logs::clear_session_log,
            commands::stats::get_home_summary,
            commands::stats::get_sqlite_status,
            commands::stats::query_fyp_stats,
            commands::stats::query_action_logs,
            commands::stats::query_target_engagements,
            commands::stats::query_target_follows,
            commands::stats::query_target_watermarks,
            commands::stats::query_target_stats,
            commands::stats::reset_target_watermark,
            commands::process::run_all_accounts,
            commands::process::run_one_account,
            commands::process::run_selected_accounts,
            commands::process::get_stdout_chunk,
            commands::process::get_stderr_chunk,
            commands::process::stop_current_run,
            commands::process::continue_auth_intervention,
            commands::process::skip_auth_intervention,
            commands::scheduler::start_scheduler,
            commands::scheduler::stop_scheduler,
            commands::scheduler::get_scheduler_process_status,
            commands::scheduler::get_scheduler_health,
            commands::scheduler::clear_run_lock,
            commands::process::run_account_script
        ])
        .run(tauri::generate_context!())
        .expect("error while running Account Matrix desktop app");
}
