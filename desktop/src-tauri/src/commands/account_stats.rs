use std::collections::HashSet;

use rusqlite::{params, Connection, OptionalExtension};
use serde::Serialize;

use crate::commands::config::load_config;
use crate::paths::project_paths;

#[derive(Debug, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AccountCoverage {
    pub account_count: usize,
    pub success_count: usize,
    pub comment_evidence_count: usize,
    pub following_count: usize,
    pub followers_count: usize,
    pub liked_count: usize,
    pub likes_count: usize,
}

/// Read configured accounts (including disabled accounts, as in the results page).
#[tauri::command]
pub fn query_account_coverage(platform: Option<String>) -> Result<AccountCoverage, String> {
    let platform = platform.unwrap_or_else(|| "tiktok".to_string());
    let config = load_config()?;
    let ids: HashSet<String> = config.accounts().iter()
        .filter(|account| account.platform() == platform)
        .map(|account| account.id().to_string()).collect();
    let paths = project_paths()?;
    let db_path = std::path::PathBuf::from(&paths.actions_db_path);
    if !db_path.exists() {
        return Ok(AccountCoverage { account_count: ids.len(), ..Default::default() });
    }
    let conn = Connection::open_with_flags(db_path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|err| format!("failed to open profile statistics: {err}"))?;
    conn.busy_timeout(std::time::Duration::from_secs(5)).map_err(|err| err.to_string())?;
    read_account_coverage(&conn, &platform, &ids)
}

fn read_account_coverage(conn: &Connection, platform: &str, ids: &HashSet<String>) -> Result<AccountCoverage, String> {
    let mut result = AccountCoverage { account_count: ids.len(), ..Default::default() };
    let exists = conn.query_row("SELECT 1 FROM sqlite_master WHERE type='table' AND name='profile_stats_snapshots'",
        [], |row| row.get::<_, i32>(0)).optional().map_err(|err| err.to_string())?.is_some();
    if !exists || ids.is_empty() { return Ok(result); }
    let mut stmt = conn.prepare(
        "SELECT s.account_id, latest.has_success, s.following, s.followers, s.liked, s.likes,
                s.comment_publish_evidence, s.activity_has_liked_your_comment
         FROM profile_stats_snapshots s
         JOIN (SELECT account_id, MAX(id) AS id,
                      MAX(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS has_success
               FROM profile_stats_snapshots WHERE platform = ?1 GROUP BY account_id) latest ON latest.id = s.id"
    ).map_err(|err| err.to_string())?;
    let mut rows = stmt.query(params![platform]).map_err(|err| err.to_string())?;
    while let Some(row) = rows.next().map_err(|err| err.to_string())? {
        let id: String = row.get(0).map_err(|err| err.to_string())?;
        if ids.contains(&id) { add_coverage_row(&mut result, row).map_err(|err| err.to_string())?; }
    }
    Ok(result)
}

fn add_coverage_row(result: &mut AccountCoverage, row: &rusqlite::Row<'_>) -> rusqlite::Result<()> {
    result.success_count += usize::from(row.get::<_, i64>(1)? > 0);
    result.following_count += usize::from(row.get::<_, Option<i64>>(2)?.unwrap_or(0) > 0);
    result.followers_count += usize::from(row.get::<_, Option<i64>>(3)?.unwrap_or(0) > 0);
    result.liked_count += usize::from(row.get::<_, Option<i64>>(4)?.unwrap_or(0) > 0);
    result.likes_count += usize::from(row.get::<_, Option<i64>>(5)?.unwrap_or(0) > 0);
    let evidence: Option<String> = row.get(6)?;
    let liked_comment: Option<i64> = row.get(7)?;
    result.comment_evidence_count += usize::from(evidence.as_deref() == Some("observed") || liked_comment == Some(1));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts_current_accounts_with_historical_success_and_latest_coverage() {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("CREATE TABLE profile_stats_snapshots (
          id INTEGER PRIMARY KEY, platform TEXT, account_id TEXT, following INTEGER, followers INTEGER,
          liked INTEGER, likes INTEGER, comment_publish_evidence TEXT, activity_has_liked_your_comment INTEGER, status TEXT);
          INSERT INTO profile_stats_snapshots VALUES
          (1,'tiktok','a',10,20,30,40,NULL,0,'success'),
          (2,'tiktok','a',NULL,NULL,NULL,NULL,NULL,0,'failed'),
          (3,'tiktok','b',1,0,3000,2,'observed',0,'success'),
          (4,'tiktok','removed',9,9,9,9,NULL,1,'success'),
          (5,'instagram','c',9,9,9,9,NULL,1,'success'),
          (6,'tiktok','b',2,0,3807,3,NULL,1,'success');").unwrap();
        let ids = ["a", "b", "c"].into_iter().map(String::from).collect();
        let result = read_account_coverage(&conn, "tiktok", &ids).unwrap();
        assert_eq!(result.account_count, 3);
        assert_eq!(result.success_count, 2); // later failure doesn't erase success
        assert_eq!(result.following_count, 1);
        assert_eq!(result.followers_count, 0);
        assert_eq!(result.liked_count, 1); // 3807 is ONE account
        assert_eq!(result.likes_count, 1);
        assert_eq!(result.comment_evidence_count, 1);
    }

    #[test]
    fn uncollected_configuration_is_counted_and_missing_table_is_not_an_error() {
        let conn = Connection::open_in_memory().unwrap();
        let ids = ["uncollected"].into_iter().map(String::from).collect();
        let result = read_account_coverage(&conn, "tiktok", &ids).unwrap();
        assert_eq!(result.account_count, 1);
        assert_eq!(result.success_count, 0);
    }
}
