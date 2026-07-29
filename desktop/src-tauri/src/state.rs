use std::process::Child;
use std::sync::{Arc, Mutex};

use crate::paths::AppInitializationStatus;

#[derive(Default)]
pub struct AppState {
    pub current_run: Arc<Mutex<RunState>>,
    pub scheduler_process: Mutex<Option<u32>>,
    pub initialization_status: Mutex<Option<AppInitializationStatus>>,
}

pub struct RunState {
    pub status: String,
    pub process_id: Option<u32>,
    pub task_type: Option<String>,
    pub account_id: Option<String>,
    pub started_at: Option<String>,
    pub ended_at: Option<String>,
    pub error: Option<String>,
    pub command: Vec<String>,
    pub queue: Vec<String>,
    pub completed_accounts: Vec<String>,
    pub browser_preview: Option<BrowserPreviewState>,
    pub auth_intervention: Option<AuthInterventionState>,
    pub stdout: String,
    pub stderr: String,
    pub redactions: Vec<String>,
    pub child: Option<Child>,
    pub stop_after_current: bool,
}

#[derive(Clone)]
pub struct BrowserPreviewState {
    pub account_id: String,
    pub profile_id: String,
    pub cdp_endpoint: String,
    pub opened_at: String,
}

#[derive(Clone)]
pub struct AuthInterventionState {
    pub account_id: String,
    pub platform: String,
    pub state: String,
    pub detail: String,
    pub reason: String,
    pub url: Option<String>,
    pub checked_at: String,
}

impl Default for RunState {
    fn default() -> Self {
        Self {
            status: "idle".to_string(),
            process_id: None,
            task_type: None,
            account_id: None,
            started_at: None,
            ended_at: None,
            error: None,
            command: Vec::new(),
            queue: Vec::new(),
            completed_accounts: Vec::new(),
            browser_preview: None,
            auth_intervention: None,
            stdout: String::new(),
            stderr: String::new(),
            redactions: Vec::new(),
            child: None,
            stop_after_current: false,
        }
    }
}
