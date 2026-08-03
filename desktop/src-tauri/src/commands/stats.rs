use chrono::{Duration, Local};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

use crate::commands::bitbrowser::{check_bitbrowser_api, ApiStatus};
use crate::commands::config::load_config;
use crate::paths::project_paths;
use crate::security::redact_line;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HomeSummary {
    tiktok_enabled_accounts: usize,
    bitbrowser: ApiStatus,
    today_planned_tasks: usize,
    today_completed_accounts: usize,
    today_failed_accounts: usize,
    today_target_interactions: usize,
}

#[derive(Debug, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct StatsScopeRequest {
    scope: Option<String>,
    platform: Option<String>,
    account_id: Option<String>,
    days: Option<i64>,
    start_ts: Option<String>,
    end_ts: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct FypAccountStats {
    platform: String,
    account_id: String,
    ok: usize,
    err: usize,
    skip: usize,
    videos: usize,
    likes: usize,
    follows: usize,
    comments: usize,
}

#[derive(Debug, Serialize, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct FypStatsTotal {
    accounts: usize,
    ok: usize,
    err: usize,
    skip: usize,
    videos: usize,
    likes: usize,
    follows: usize,
    comments: usize,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FypStatsSummary {
    scope: String,
    label: String,
    by_account: Vec<FypAccountStats>,
    total: FypStatsTotal,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ActionLogFilter {
    platform: Option<String>,
    account_id: Option<String>,
    action: Option<String>,
    status: Option<String>,
    start_ts: Option<String>,
    end_ts: Option<String>,
    limit: Option<usize>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ActionLogRecord {
    id: i64,
    platform: String,
    account_id: String,
    action: String,
    status: String,
    detail: String,
    ts: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerJobRunFilter {
    platform: Option<String>,
    account_id: Option<String>,
    start_ts: Option<String>,
    end_ts: Option<String>,
    include_pending: Option<bool>,
    limit: Option<usize>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SchedulerJobRunRecord {
    job_id: String,
    platform: String,
    account_id: String,
    scheduled_run: Option<String>,
    status: String,
    started_at: Option<String>,
    ended_at: Option<String>,
    detail: String,
}

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct TargetRecordFilter {
    platform: Option<String>,
    account_id: Option<String>,
    handle: Option<String>,
    start_ts: Option<String>,
    end_ts: Option<String>,
    limit: Option<usize>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TargetEngagementRecord {
    platform: String,
    our_account: String,
    handle: String,
    video_id: String,
    liked: bool,
    commented: bool,
    ts: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TargetFollowRecord {
    platform: String,
    our_account: String,
    handle: String,
    followed: bool,
    ts: String,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct TargetWatermark {
    platform: String,
    our_account: String,
    handle: String,
    max_video_id: Option<String>,
    latest_ts: Option<String>,
    videos: usize,
    likes: usize,
    comments: usize,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct TargetAccountStats {
    platform: String,
    account_id: String,
    videos: usize,
    likes: usize,
    comments: usize,
    follows: usize,
    handles: Vec<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct TargetHandleStats {
    handle: String,
    videos: usize,
    likes: usize,
    comments: usize,
    follows: usize,
    accounts: Vec<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TargetStatsSummary {
    scope: String,
    label: String,
    by_account: Vec<TargetAccountStats>,
    by_handle: Vec<TargetHandleStats>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResetTargetWatermarkRequest {
    account_id: Option<String>,
    handle: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ResetTargetWatermarkResult {
    deleted_rows: usize,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SqliteStatus {
    path: String,
    exists: bool,
    action_log: bool,
    scheduler_job_runs: bool,
    target_engagements: bool,
    target_follows: bool,
}

#[tauri::command]
pub fn get_sqlite_status() -> Result<SqliteStatus, String> {
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(SqliteStatus {
            path: paths.actions_db_path,
            exists: false,
            action_log: false,
            scheduler_job_runs: false,
            target_engagements: false,
            target_follows: false,
        });
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    Ok(SqliteStatus {
        path: paths.actions_db_path,
        exists: true,
        action_log: table_exists(&conn, "action_log")?,
        scheduler_job_runs: table_exists(&conn, "scheduler_job_runs")?,
        target_engagements: table_exists(&conn, "target_engagements")?,
        target_follows: table_exists(&conn, "target_follows")?,
    })
}

#[tauri::command]
pub fn query_fyp_stats(filter: StatsScopeRequest) -> Result<FypStatsSummary, String> {
    let (start_ts, end_ts, scope, label) = resolve_scope(&filter);
    let platform = normalized_platform_filter(filter.platform.as_deref())?;
    let account_id = optional_trim(filter.account_id.as_deref());
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(FypStatsSummary {
            scope,
            label,
            by_account: vec![],
            total: FypStatsTotal::default(),
        });
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    if !table_exists(&conn, "action_log")? {
        return Ok(FypStatsSummary {
            scope,
            label,
            by_account: vec![],
            total: FypStatsTotal::default(),
        });
    }

    let platform_expr = platform_select_expr(&conn, "action_log", "account_id")?;
    let query = format!(
        "SELECT {}, account_id, action, status, detail
             FROM action_log
             WHERE (?1 IS NULL OR ts >= ?1)
               AND (?2 IS NULL OR ts <= ?2)
               AND (?3 IS NULL OR {} = ?3)
               AND (?4 IS NULL OR account_id = ?4)",
        platform_expr, platform_expr,
    );
    let mut stmt = conn
        .prepare(&query)
        .map_err(|err| format!("failed to prepare fyp stats query: {}", err))?;
    let rows = stmt
        .query_map(params![start_ts, end_ts, platform, account_id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, Option<String>>(4)?.unwrap_or_default(),
            ))
        })
        .map_err(|err| format!("failed to query fyp stats: {}", err))?;

    let mut by_account: HashMap<(String, String), ActionStatsAccumulator> = HashMap::new();
    for row in rows {
        let (platform, account_id, action, status, detail) =
            row.map_err(|err| format!("failed to read fyp stats row: {}", err))?;
        let entry = by_account.entry((platform, account_id)).or_default();
        match (action.as_str(), status.as_str()) {
            ("fyp_browse", "ok") => {
                entry.ok += 1;
                entry.videos += parse_detail_count(&detail, "videos");
            }
            ("session", "error") => entry.err += 1,
            ("session", "skip") => entry.skip += 1,
            ("like", "ok") => entry.likes += parse_detail_count(&detail, "count"),
            ("follow", "ok") => entry.follows += parse_detail_count(&detail, "count"),
            ("comment", "ok") => entry.comments += parse_detail_count(&detail, "count"),
            _ => {}
        }
    }

    let mut account_rows = by_account
        .into_iter()
        .map(|((platform, account_id), stats)| FypAccountStats {
            platform,
            account_id,
            ok: stats.ok,
            err: stats.err,
            skip: stats.skip,
            videos: stats.videos,
            likes: stats.likes,
            follows: stats.follows,
            comments: stats.comments,
        })
        .collect::<Vec<_>>();
    account_rows.sort_by(|left, right| left.account_id.cmp(&right.account_id));
    let total = total_fyp_stats(&account_rows);

    Ok(FypStatsSummary {
        scope,
        label,
        by_account: account_rows,
        total,
    })
}

#[tauri::command]
pub fn get_home_summary() -> Result<HomeSummary, String> {
    let config = load_config()?;
    let tiktok_enabled_accounts = config
        .accounts()
        .iter()
        .filter(|account| account.platform() == "tiktok" && account.enabled())
        .count();
    let fires_per_day = config.scheduler_fires_per_day().unwrap_or(0).max(0) as usize;
    let today_planned_tasks = tiktok_enabled_accounts.saturating_mul(fires_per_day);
    let today = Local::now().format("%Y-%m-%d").to_string();
    let db_stats = read_today_db_stats(&today).unwrap_or_default();

    Ok(HomeSummary {
        tiktok_enabled_accounts,
        bitbrowser: check_bitbrowser_api(),
        today_planned_tasks,
        today_completed_accounts: db_stats.completed_accounts,
        today_failed_accounts: db_stats.failed_accounts,
        today_target_interactions: db_stats.target_interactions,
    })
}

#[tauri::command]
pub fn query_action_logs(filter: ActionLogFilter) -> Result<Vec<ActionLogRecord>, String> {
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(vec![]);
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    if !table_exists(&conn, "action_log")? {
        return Ok(vec![]);
    }

    let platform = normalized_platform_filter(filter.platform.as_deref())?;
    let account_id = optional_trim(filter.account_id.as_deref());
    let action = optional_trim(filter.action.as_deref());
    let status = optional_trim(filter.status.as_deref());
    let start_ts = optional_trim(filter.start_ts.as_deref());
    let end_ts = optional_trim(filter.end_ts.as_deref());
    let limit = normalized_limit(filter.limit) as i64;

    let platform_expr = platform_select_expr(&conn, "action_log", "account_id")?;
    let query = format!(
        "SELECT id, {}, account_id, action, status, detail, ts
             FROM action_log
             WHERE (?1 IS NULL OR {} = ?1)
               AND (?2 IS NULL OR account_id = ?2)
               AND (?3 IS NULL OR action = ?3)
               AND (?4 IS NULL OR status = ?4)
               AND (?5 IS NULL OR ts >= ?5)
               AND (?6 IS NULL OR ts <= ?6)
             ORDER BY ts DESC, id DESC
             LIMIT ?7",
        platform_expr, platform_expr,
    );
    let mut stmt = conn
        .prepare(&query)
        .map_err(|err| format!("failed to prepare action_log query: {}", err))?;
    let rows = stmt
        .query_map(
            params![platform, account_id, action, status, start_ts, end_ts, limit],
            |row| {
                Ok(ActionLogRecord {
                    id: row.get(0)?,
                    platform: row.get(1)?,
                    account_id: row.get(2)?,
                    action: row.get(3)?,
                    status: row.get(4)?,
                    detail: redact_line(&row.get::<_, Option<String>>(5)?.unwrap_or_default(), &[]),
                    ts: row.get(6)?,
                })
            },
        )
        .map_err(|err| format!("failed to query action_log: {}", err))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|err| format!("failed to read action_log row: {}", err))?);
    }
    Ok(result)
}

#[tauri::command]
pub fn query_scheduler_job_runs(
    filter: SchedulerJobRunFilter,
) -> Result<Vec<SchedulerJobRunRecord>, String> {
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(vec![]);
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    if !table_exists(&conn, "scheduler_job_runs")? {
        return Ok(vec![]);
    }

    let platform = normalized_platform_filter(filter.platform.as_deref())?;
    let account_id = optional_trim(filter.account_id.as_deref());
    let start_ts = optional_trim(filter.start_ts.as_deref());
    let end_ts = optional_trim(filter.end_ts.as_deref());
    let include_pending = filter.include_pending.unwrap_or(false);
    let limit = normalized_limit(filter.limit) as i64;

    let query = "
        SELECT job_id, platform, account_id, scheduled_run, status, started_at, ended_at, detail
        FROM scheduler_job_runs
        WHERE (?1 IS NULL OR platform = ?1)
          AND (?2 IS NULL OR account_id = ?2)
          AND (?3 IS NULL OR COALESCE(started_at, scheduled_run, created_at) >= ?3)
          AND (?4 IS NULL OR COALESCE(started_at, scheduled_run, created_at) <= ?4)
          AND (?5 OR status <> 'pending')
        ORDER BY COALESCE(started_at, scheduled_run, created_at) DESC, job_id DESC
        LIMIT ?6";
    let mut stmt = conn
        .prepare(query)
        .map_err(|err| format!("failed to prepare scheduler_job_runs query: {}", err))?;
    let rows = stmt
        .query_map(
            params![
                platform,
                account_id,
                start_ts,
                end_ts,
                include_pending,
                limit
            ],
            |row| {
                Ok(SchedulerJobRunRecord {
                    job_id: row.get(0)?,
                    platform: row.get(1)?,
                    account_id: row.get(2)?,
                    scheduled_run: row.get(3)?,
                    status: row.get(4)?,
                    started_at: row.get(5)?,
                    ended_at: row.get(6)?,
                    detail: redact_line(&row.get::<_, Option<String>>(7)?.unwrap_or_default(), &[]),
                })
            },
        )
        .map_err(|err| format!("failed to query scheduler_job_runs: {}", err))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|err| format!("failed to read scheduler_job_runs row: {}", err))?);
    }
    Ok(result)
}

#[tauri::command]
pub fn query_target_engagements(
    filter: TargetRecordFilter,
) -> Result<Vec<TargetEngagementRecord>, String> {
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(vec![]);
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    if !table_exists(&conn, "target_engagements")? {
        return Ok(vec![]);
    }

    let platform = normalized_platform_filter(filter.platform.as_deref())?;
    let account_id = optional_trim(filter.account_id.as_deref());
    let handle = optional_trim(filter.handle.as_deref()).map(|value| value.trim_start_matches('@'));
    let start_ts = optional_trim(filter.start_ts.as_deref());
    let end_ts = optional_trim(filter.end_ts.as_deref());
    let limit = normalized_limit(filter.limit) as i64;

    let platform_expr = platform_select_expr(&conn, "target_engagements", "our_account")?;
    let query = format!(
        "SELECT {}, our_account, handle, video_id, liked, commented, ts
             FROM target_engagements
             WHERE (?1 IS NULL OR {} = ?1)
               AND (?2 IS NULL OR our_account = ?2)
               AND (?3 IS NULL OR handle = ?3)
               AND (?4 IS NULL OR ts >= ?4)
               AND (?5 IS NULL OR ts <= ?5)
             ORDER BY ts DESC
             LIMIT ?6",
        platform_expr, platform_expr,
    );
    let mut stmt = conn
        .prepare(&query)
        .map_err(|err| format!("failed to prepare target_engagements query: {}", err))?;
    let rows = stmt
        .query_map(
            params![platform, account_id, handle, start_ts, end_ts, limit],
            |row| {
                Ok(TargetEngagementRecord {
                    platform: row.get(0)?,
                    our_account: row.get(1)?,
                    handle: row.get(2)?,
                    video_id: row.get(3)?,
                    liked: row.get::<_, i64>(4)? != 0,
                    commented: row.get::<_, i64>(5)? != 0,
                    ts: row.get(6)?,
                })
            },
        )
        .map_err(|err| format!("failed to query target_engagements: {}", err))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|err| format!("failed to read target_engagements row: {}", err))?);
    }
    Ok(result)
}

#[tauri::command]
pub fn query_target_follows(filter: TargetRecordFilter) -> Result<Vec<TargetFollowRecord>, String> {
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(vec![]);
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    if !table_exists(&conn, "target_follows")? {
        return Ok(vec![]);
    }

    let platform = normalized_platform_filter(filter.platform.as_deref())?;
    let account_id = optional_trim(filter.account_id.as_deref());
    let handle = optional_trim(filter.handle.as_deref()).map(|value| value.trim_start_matches('@'));
    let start_ts = optional_trim(filter.start_ts.as_deref());
    let end_ts = optional_trim(filter.end_ts.as_deref());
    let limit = normalized_limit(filter.limit) as i64;

    let platform_expr = platform_select_expr(&conn, "target_follows", "our_account")?;
    let query = format!(
        "SELECT {}, our_account, handle, followed, ts
             FROM target_follows
             WHERE (?1 IS NULL OR {} = ?1)
               AND (?2 IS NULL OR our_account = ?2)
               AND (?3 IS NULL OR handle = ?3)
               AND (?4 IS NULL OR ts >= ?4)
               AND (?5 IS NULL OR ts <= ?5)
             ORDER BY ts DESC
             LIMIT ?6",
        platform_expr, platform_expr,
    );
    let mut stmt = conn
        .prepare(&query)
        .map_err(|err| format!("failed to prepare target_follows query: {}", err))?;
    let rows = stmt
        .query_map(
            params![platform, account_id, handle, start_ts, end_ts, limit],
            |row| {
                Ok(TargetFollowRecord {
                    platform: row.get(0)?,
                    our_account: row.get(1)?,
                    handle: row.get(2)?,
                    followed: row.get::<_, i64>(3)? != 0,
                    ts: row.get(4)?,
                })
            },
        )
        .map_err(|err| format!("failed to query target_follows: {}", err))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|err| format!("failed to read target_follows row: {}", err))?);
    }
    Ok(result)
}

#[tauri::command]
pub fn query_target_watermarks(
    filter: Option<TargetRecordFilter>,
) -> Result<Vec<TargetWatermark>, String> {
    let filter = filter.unwrap_or_default();
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(vec![]);
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    if !table_exists(&conn, "target_engagements")? {
        return Ok(vec![]);
    }

    let platform = normalized_platform_filter(filter.platform.as_deref())?;
    let account_id = optional_trim(filter.account_id.as_deref());
    let handle = optional_trim(filter.handle.as_deref()).map(|value| value.trim_start_matches('@'));
    let start_ts = optional_trim(filter.start_ts.as_deref());
    let end_ts = optional_trim(filter.end_ts.as_deref());
    let limit = normalized_limit(filter.limit) as i64;

    let platform_expr = platform_select_expr(&conn, "target_engagements", "our_account")?;
    let query = format!(
        "SELECT {}, our_account, handle, video_id, liked, commented, ts
             FROM target_engagements
             WHERE (?1 IS NULL OR {} = ?1)
               AND (?2 IS NULL OR our_account = ?2)
               AND (?3 IS NULL OR handle = ?3)
               AND (?4 IS NULL OR ts >= ?4)
               AND (?5 IS NULL OR ts <= ?5)
             ORDER BY ts DESC
             LIMIT ?6",
        platform_expr, platform_expr,
    );
    let mut stmt = conn
        .prepare(&query)
        .map_err(|err| format!("failed to prepare target watermark query: {}", err))?;
    let rows = stmt
        .query_map(
            params![platform, account_id, handle, start_ts, end_ts, limit],
            |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, String>(3)?,
                    row.get::<_, i64>(4)?,
                    row.get::<_, i64>(5)?,
                    row.get::<_, String>(6)?,
                ))
            },
        )
        .map_err(|err| format!("failed to query target watermarks: {}", err))?;

    let mut watermarks: HashMap<(String, String, String), TargetWatermark> = HashMap::new();
    for row in rows {
        let (platform, our_account, handle, video_id, liked, commented, ts) =
            row.map_err(|err| format!("failed to read target watermark row: {}", err))?;
        let key = (platform.clone(), our_account.clone(), handle.clone());
        let entry = watermarks.entry(key).or_insert_with(|| TargetWatermark {
            platform,
            our_account,
            handle,
            max_video_id: None,
            latest_ts: None,
            videos: 0,
            likes: 0,
            comments: 0,
        });
        entry.videos += 1;
        entry.likes += liked.max(0) as usize;
        entry.comments += commented.max(0) as usize;
        if entry
            .latest_ts
            .as_deref()
            .map(|current| ts.as_str() > current)
            .unwrap_or(true)
        {
            entry.latest_ts = Some(ts);
        }
        if !video_id.trim().is_empty()
            && entry
                .max_video_id
                .as_deref()
                .map(|current| video_id_is_greater(&video_id, current))
                .unwrap_or(true)
        {
            entry.max_video_id = Some(video_id);
        }
    }

    let mut result = watermarks.into_values().collect::<Vec<_>>();
    result.sort_by(|left, right| {
        right
            .latest_ts
            .cmp(&left.latest_ts)
            .then_with(|| left.our_account.cmp(&right.our_account))
            .then_with(|| left.handle.cmp(&right.handle))
    });
    Ok(result)
}

#[tauri::command]
pub fn query_target_stats(filter: StatsScopeRequest) -> Result<TargetStatsSummary, String> {
    let (start_ts, end_ts, scope, label) = resolve_scope(&filter);
    let platform = normalized_platform_filter(filter.platform.as_deref())?;
    let account_id = optional_trim(filter.account_id.as_deref());
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(TargetStatsSummary {
            scope,
            label,
            by_account: vec![],
            by_handle: vec![],
        });
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    let watermarks = if table_exists(&conn, "target_engagements")? {
        query_target_engagement_rows(
            &conn,
            platform.as_deref(),
            account_id,
            start_ts.as_deref(),
            end_ts.as_deref(),
        )?
    } else {
        vec![]
    };
    let follows = if table_exists(&conn, "target_follows")? {
        query_target_follow_rows(
            &conn,
            platform.as_deref(),
            account_id,
            start_ts.as_deref(),
            end_ts.as_deref(),
        )?
    } else {
        vec![]
    };

    let mut by_account: HashMap<(String, String), AccountStatsAccumulator> = HashMap::new();
    let mut by_handle: HashMap<String, HandleStatsAccumulator> = HashMap::new();

    for row in watermarks {
        let account_entry = by_account
            .entry((row.platform.clone(), row.our_account.clone()))
            .or_default();
        account_entry.videos += 1;
        account_entry.likes += row.liked.max(0) as usize;
        account_entry.comments += row.commented.max(0) as usize;
        account_entry.handles.insert(row.handle.clone());

        let handle_entry = by_handle.entry(row.handle.clone()).or_default();
        handle_entry.videos += 1;
        handle_entry.likes += row.liked.max(0) as usize;
        handle_entry.comments += row.commented.max(0) as usize;
        handle_entry.accounts.insert(row.our_account);
    }

    for (platform, our_account, handle) in follows {
        let account_entry = by_account
            .entry((platform.clone(), our_account.clone()))
            .or_default();
        account_entry.follows += 1;
        account_entry.handles.insert(handle.clone());

        let handle_entry = by_handle.entry(handle).or_default();
        handle_entry.follows += 1;
        handle_entry.accounts.insert(our_account);
    }

    let mut account_rows = by_account
        .into_iter()
        .map(|((platform, account_id), stats)| TargetAccountStats {
            platform,
            account_id,
            videos: stats.videos,
            likes: stats.likes,
            comments: stats.comments,
            follows: stats.follows,
            handles: sorted_set(stats.handles),
        })
        .collect::<Vec<_>>();
    account_rows.sort_by(|left, right| left.account_id.cmp(&right.account_id));

    let mut handle_rows = by_handle
        .into_iter()
        .map(|(handle, stats)| TargetHandleStats {
            handle,
            videos: stats.videos,
            likes: stats.likes,
            comments: stats.comments,
            follows: stats.follows,
            accounts: sorted_set(stats.accounts),
        })
        .collect::<Vec<_>>();
    handle_rows.sort_by(|left, right| left.handle.cmp(&right.handle));

    Ok(TargetStatsSummary {
        scope,
        label,
        by_account: account_rows,
        by_handle: handle_rows,
    })
}

#[tauri::command]
pub fn reset_target_watermark(
    request: ResetTargetWatermarkRequest,
) -> Result<ResetTargetWatermarkResult, String> {
    let account_id = request
        .account_id
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty());
    let handle = request
        .handle
        .as_deref()
        .map(str::trim)
        .map(|value| value.trim_start_matches('@'))
        .filter(|value| !value.is_empty());

    if account_id.is_none() && handle.is_none() {
        return Err("reset requires accountId or handle".to_string());
    }

    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(ResetTargetWatermarkResult { deleted_rows: 0 });
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    if !table_exists(&conn, "target_engagements")? {
        return Ok(ResetTargetWatermarkResult { deleted_rows: 0 });
    }

    let deleted_rows = match (account_id, handle) {
        (Some(account_id), Some(handle)) => conn.execute(
            "DELETE FROM target_engagements WHERE our_account = ?1 AND handle = ?2",
            params![account_id, handle],
        ),
        (Some(account_id), None) => conn.execute(
            "DELETE FROM target_engagements WHERE our_account = ?1",
            params![account_id],
        ),
        (None, Some(handle)) => conn.execute(
            "DELETE FROM target_engagements WHERE handle = ?1",
            params![handle],
        ),
        (None, None) => unreachable!(),
    }
    .map_err(|err| format!("failed to reset target watermark: {}", err))?;

    Ok(ResetTargetWatermarkResult { deleted_rows })
}

#[derive(Default)]
struct TodayDbStats {
    completed_accounts: usize,
    failed_accounts: usize,
    target_interactions: usize,
}

#[derive(Default)]
struct AccountStatsAccumulator {
    videos: usize,
    likes: usize,
    comments: usize,
    follows: usize,
    handles: HashSet<String>,
}

#[derive(Default)]
struct ActionStatsAccumulator {
    ok: usize,
    err: usize,
    skip: usize,
    videos: usize,
    likes: usize,
    follows: usize,
    comments: usize,
}

#[derive(Default)]
struct HandleStatsAccumulator {
    videos: usize,
    likes: usize,
    comments: usize,
    follows: usize,
    accounts: HashSet<String>,
}

struct TargetEngagementRow {
    platform: String,
    our_account: String,
    handle: String,
    liked: i64,
    commented: i64,
}

fn read_today_db_stats(today: &str) -> Result<TodayDbStats, String> {
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(TodayDbStats::default());
    }

    let conn = Connection::open(&db_path)
        .map_err(|err| format!("failed to open {}: {}", paths.actions_db_path, err))?;
    let day_prefix = format!("{}%", today);

    let completed_accounts: usize = conn
        .query_row(
            "SELECT COUNT(DISTINCT account_id) FROM action_log WHERE action='fyp_browse' AND status='ok' AND ts LIKE ?1",
            params![day_prefix.as_str()],
            |row| row.get::<_, i64>(0),
        )
        .unwrap_or(0)
        .max(0) as usize;
    let failed_accounts: usize = conn
        .query_row(
            "SELECT COUNT(DISTINCT account_id) FROM action_log WHERE status='error' AND ts LIKE ?1",
            params![day_prefix.as_str()],
            |row| row.get::<_, i64>(0),
        )
        .unwrap_or(0)
        .max(0) as usize;
    let target_interactions: usize = conn
        .query_row(
            "SELECT COUNT(*) FROM target_engagements WHERE ts LIKE ?1 AND (liked=1 OR commented=1)",
            params![day_prefix.as_str()],
            |row| row.get::<_, i64>(0),
        )
        .unwrap_or(0)
        .max(0) as usize;

    Ok(TodayDbStats {
        completed_accounts,
        failed_accounts,
        target_interactions,
    })
}

fn query_target_engagement_rows(
    conn: &Connection,
    platform: Option<&str>,
    account_id: Option<&str>,
    start_ts: Option<&str>,
    end_ts: Option<&str>,
) -> Result<Vec<TargetEngagementRow>, String> {
    let platform_expr = platform_select_expr(conn, "target_engagements", "our_account")?;
    let query = format!(
        "SELECT {}, our_account, handle, liked, commented
             FROM target_engagements
             WHERE (?1 IS NULL OR {} = ?1)
               AND (?2 IS NULL OR our_account = ?2)
               AND (?3 IS NULL OR ts >= ?3)
               AND (?4 IS NULL OR ts <= ?4)",
        platform_expr, platform_expr,
    );
    let mut stmt = conn
        .prepare(&query)
        .map_err(|err| format!("failed to prepare target engagement stats query: {}", err))?;
    let rows = stmt
        .query_map(params![platform, account_id, start_ts, end_ts], |row| {
            Ok(TargetEngagementRow {
                platform: row.get(0)?,
                our_account: row.get(1)?,
                handle: row.get(2)?,
                liked: row.get(3)?,
                commented: row.get(4)?,
            })
        })
        .map_err(|err| format!("failed to query target engagement stats: {}", err))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|err| format!("failed to read target engagement row: {}", err))?);
    }
    Ok(result)
}

fn query_target_follow_rows(
    conn: &Connection,
    platform: Option<&str>,
    account_id: Option<&str>,
    start_ts: Option<&str>,
    end_ts: Option<&str>,
) -> Result<Vec<(String, String, String)>, String> {
    let platform_expr = platform_select_expr(conn, "target_follows", "our_account")?;
    let query = format!(
        "SELECT {}, our_account, handle
             FROM target_follows
             WHERE followed = 1
               AND (?1 IS NULL OR {} = ?1)
               AND (?2 IS NULL OR our_account = ?2)
               AND (?3 IS NULL OR ts >= ?3)
               AND (?4 IS NULL OR ts <= ?4)",
        platform_expr, platform_expr,
    );
    let mut stmt = conn
        .prepare(&query)
        .map_err(|err| format!("failed to prepare target follow stats query: {}", err))?;
    let rows = stmt
        .query_map(params![platform, account_id, start_ts, end_ts], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
            ))
        })
        .map_err(|err| format!("failed to query target follow stats: {}", err))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|err| format!("failed to read target follow row: {}", err))?);
    }
    Ok(result)
}

fn table_exists(conn: &Connection, table_name: &str) -> Result<bool, String> {
    conn.query_row(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?1",
        params![table_name],
        |row| row.get::<_, i64>(0),
    )
    .map(|count| count > 0)
    .map_err(|err| format!("failed to inspect SQLite schema: {}", err))
}

fn table_column_exists(
    conn: &Connection,
    table_name: &str,
    column_name: &str,
) -> Result<bool, String> {
    let mut stmt = conn
        .prepare(&format!("PRAGMA table_info({})", table_name))
        .map_err(|err| format!("failed to inspect SQLite table {}: {}", table_name, err))?;
    let rows = stmt
        .query_map([], |row| row.get::<_, String>(1))
        .map_err(|err| {
            format!(
                "failed to inspect SQLite columns for {}: {}",
                table_name, err
            )
        })?;
    for row in rows {
        if row.map_err(|err| format!("failed to read SQLite column metadata: {}", err))?
            == column_name
        {
            return Ok(true);
        }
    }
    Ok(false)
}

fn platform_select_expr(
    conn: &Connection,
    table_name: &str,
    _account_column: &str,
) -> Result<String, String> {
    if table_column_exists(conn, table_name, "platform")? {
        Ok("COALESCE(NULLIF(TRIM(platform), ''), 'tiktok')".to_string())
    } else {
        Ok("'tiktok'".to_string())
    }
}

fn normalized_platform_filter(value: Option<&str>) -> Result<Option<String>, String> {
    let Some(value) = optional_trim(value) else {
        return Ok(None);
    };
    if value == "all" {
        return Ok(None);
    }
    if matches!(value, "tiktok" | "instagram" | "whatsapp" | "douyin") {
        Ok(Some(value.to_string()))
    } else {
        Err(format!("unsupported platform filter '{}'", value))
    }
}

fn optional_trim(value: Option<&str>) -> Option<&str> {
    value.map(str::trim).filter(|value| !value.is_empty())
}

fn normalized_limit(limit: Option<usize>) -> usize {
    limit.unwrap_or(300).clamp(1, 1000)
}

fn resolve_scope(filter: &StatsScopeRequest) -> (Option<String>, Option<String>, String, String) {
    let scope = filter
        .scope
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or("all");
    match scope {
        "today" => {
            let start = Local::now()
                .date_naive()
                .and_hms_opt(0, 0, 0)
                .unwrap()
                .format("%Y-%m-%dT%H:%M:%S")
                .to_string();
            (
                Some(start.clone()),
                None,
                "today".to_string(),
                format!("今日（{}）", &start[..10]),
            )
        }
        "recent_days" => {
            let days = filter.days.unwrap_or(7).clamp(1, 365);
            let start = (Local::now() - Duration::days(days))
                .format("%Y-%m-%dT%H:%M:%S")
                .to_string();
            (
                Some(start),
                None,
                "recent_days".to_string(),
                format!("最近 {} 天", days),
            )
        }
        "custom" => (
            optional_trim(filter.start_ts.as_deref()).map(|value| value.to_string()),
            optional_trim(filter.end_ts.as_deref()).map(|value| value.to_string()),
            "custom".to_string(),
            "自定义范围".to_string(),
        ),
        _ => (None, None, "all".to_string(), "全部".to_string()),
    }
}

fn parse_detail_count(detail: &str, key: &str) -> usize {
    let needle = format!("{}=", key);
    detail
        .split_whitespace()
        .find_map(|part| {
            part.strip_prefix(&needle)
                .and_then(|value| value.parse::<i64>().ok())
                .map(|value| value.max(0) as usize)
        })
        .unwrap_or(0)
}

fn total_fyp_stats(rows: &[FypAccountStats]) -> FypStatsTotal {
    rows.iter().fold(
        FypStatsTotal {
            accounts: rows.len(),
            ..FypStatsTotal::default()
        },
        |mut total, row| {
            total.ok += row.ok;
            total.err += row.err;
            total.skip += row.skip;
            total.videos += row.videos;
            total.likes += row.likes;
            total.follows += row.follows;
            total.comments += row.comments;
            total
        },
    )
}

fn video_id_is_greater(candidate: &str, current: &str) -> bool {
    let candidate = candidate.trim();
    let current = current.trim();
    let candidate_numeric = candidate.chars().all(|ch| ch.is_ascii_digit());
    let current_numeric = current.chars().all(|ch| ch.is_ascii_digit());
    if candidate_numeric && current_numeric {
        return candidate
            .len()
            .cmp(&current.len())
            .then_with(|| candidate.cmp(current))
            .is_gt();
    }
    candidate > current
}

fn sorted_set(values: HashSet<String>) -> Vec<String> {
    let mut result = values.into_iter().collect::<Vec<_>>();
    result.sort();
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sqlite_helpers_query_target_tables() {
        let conn = Connection::open_in_memory().expect("in-memory sqlite should open");
        conn.execute_batch(
            "
            CREATE TABLE target_engagements (
                our_account TEXT,
                handle TEXT,
                video_id TEXT,
                liked INTEGER,
                commented INTEGER,
                ts TEXT
            );
            CREATE TABLE target_follows (
                our_account TEXT,
                handle TEXT,
                followed INTEGER,
                ts TEXT
            );
            INSERT INTO target_engagements VALUES ('acct_1', 'brand', '100', 1, 0, '2026-07-22T08:00:00');
            INSERT INTO target_engagements VALUES ('acct_2', 'brand', '101', 0, 1, '2026-07-21T08:00:00');
            INSERT INTO target_follows VALUES ('acct_1', 'brand', 1, '2026-07-22T09:00:00');
            INSERT INTO target_follows VALUES ('acct_2', 'brand', 0, '2026-07-22T09:00:00');
            ",
        )
        .expect("test schema should be created");

        assert!(table_exists(&conn, "target_engagements").expect("schema should be inspectable"));
        assert!(!table_exists(&conn, "missing_table").expect("schema should be inspectable"));

        let engagements = query_target_engagement_rows(
            &conn,
            Some("tiktok"),
            None,
            Some("2026-07-22T00:00:00"),
            Some("2026-07-22T23:59:59"),
        )
        .expect("target engagement rows should query");
        let follows = query_target_follow_rows(
            &conn,
            Some("tiktok"),
            None,
            Some("2026-07-22T00:00:00"),
            Some("2026-07-22T23:59:59"),
        )
        .expect("target follow rows should query");

        assert_eq!(engagements.len(), 1);
        assert_eq!(engagements[0].platform, "tiktok");
        assert_eq!(engagements[0].our_account, "acct_1");
        assert_eq!(engagements[0].liked, 1);
        assert_eq!(
            follows,
            vec![(
                "tiktok".to_string(),
                "acct_1".to_string(),
                "brand".to_string()
            )]
        );
    }

    #[test]
    fn sqlite_platform_filter_uses_explicit_platform_column() {
        let conn = Connection::open_in_memory().expect("in-memory sqlite should open");
        conn.execute_batch(
            "
            CREATE TABLE target_engagements (
                platform TEXT,
                our_account TEXT,
                handle TEXT,
                video_id TEXT,
                liked INTEGER,
                commented INTEGER,
                ts TEXT
            );
            CREATE TABLE target_follows (
                platform TEXT,
                our_account TEXT,
                handle TEXT,
                followed INTEGER,
                ts TEXT
            );
            INSERT INTO target_engagements VALUES ('tiktok', 'acct_1', 'brand', '100', 1, 0, '2026-07-22T08:00:00');
            INSERT INTO target_engagements VALUES ('instagram', 'ig_1', 'brand', '200', 1, 1, '2026-07-22T08:00:00');
            INSERT INTO target_engagements VALUES ('', 'legacy_1', 'brand', '300', 1, 0, '2026-07-22T08:00:00');
            INSERT INTO target_follows VALUES ('tiktok', 'acct_1', 'brand', 1, '2026-07-22T09:00:00');
            INSERT INTO target_follows VALUES ('instagram', 'ig_1', 'brand', 1, '2026-07-22T09:00:00');
            ",
        )
        .expect("test schema should be created");

        let instagram_rows =
            query_target_engagement_rows(&conn, Some("instagram"), None, None, None)
                .expect("instagram target engagement rows should query");
        let tiktok_rows = query_target_engagement_rows(&conn, Some("tiktok"), None, None, None)
            .expect("tiktok target engagement rows should query");
        let all_rows = query_target_engagement_rows(&conn, None, None, None, None)
            .expect("all target engagement rows should query");
        let instagram_follows =
            query_target_follow_rows(&conn, Some("instagram"), None, None, None)
                .expect("instagram target follow rows should query");

        assert_eq!(instagram_rows.len(), 1);
        assert_eq!(instagram_rows[0].platform, "instagram");
        assert_eq!(instagram_rows[0].our_account, "ig_1");
        assert_eq!(tiktok_rows.len(), 2);
        assert_eq!(all_rows.len(), 3);
        assert_eq!(
            instagram_follows,
            vec![(
                "instagram".to_string(),
                "ig_1".to_string(),
                "brand".to_string()
            )]
        );
    }

    #[test]
    fn detail_count_parser_matches_stats_cli_shape() {
        assert_eq!(parse_detail_count("videos=5 count=2", "videos"), 5);
        assert_eq!(parse_detail_count("videos=bad count=2", "videos"), 0);
        assert_eq!(parse_detail_count("", "videos"), 0);
    }
}
