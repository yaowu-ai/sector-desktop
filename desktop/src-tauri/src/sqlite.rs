use std::path::Path;
use std::time::Duration;

use rusqlite::{Connection, DatabaseName, OpenFlags};

pub fn open_readonly(path: &Path) -> Result<Connection, String> {
    let conn = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|err| format!("failed to open {}: {}", path.display(), err))?;
    conn.busy_timeout(Duration::from_secs(2))
        .map_err(|err| err.to_string())?;
    Ok(conn)
}

/// Upgrade existing databases without changing or deleting any historical rows.
pub fn prepare_actions_db(path: &Path) -> Result<(), String> {
    if !path.is_file() {
        return Ok(());
    }
    let conn = Connection::open(path).map_err(|err| err.to_string())?;
    conn.busy_timeout(Duration::from_secs(2))
        .map_err(|err| err.to_string())?;
    conn.pragma_update(None, "journal_mode", "WAL")
        .map_err(|err| err.to_string())?;
    let has_runs: bool = conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='scheduler_job_runs')",
        [], |row| row.get(0),
    ).map_err(|err| err.to_string())?;
    if has_runs {
        conn.execute_batch("
            CREATE INDEX IF NOT EXISTS idx_scheduler_runs_platform_time
            ON scheduler_job_runs(platform, COALESCE(started_at, scheduled_run, created_at) DESC, job_id DESC);
            CREATE INDEX IF NOT EXISTS idx_scheduler_runs_time
            ON scheduler_job_runs(COALESCE(started_at, scheduled_run, created_at) DESC, job_id DESC);
        ").map_err(|err| err.to_string())?;
    }
    Ok(())
}

/// File copying would miss committed pages still in the WAL.
pub fn backup_database(source: &Path, target: &Path) -> Result<(), String> {
    open_readonly(source)?
        .backup(DatabaseName::Main, target, None)
        .map_err(|err| format!("failed to backup {}: {}", source.display(), err))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wal_backup_contains_committed_pages_and_readers_cannot_write() {
        let dir = std::env::temp_dir().join(format!(
            "scheduler-sqlite-{}-{}",
            std::process::id(),
            chrono::Utc::now().timestamp_nanos_opt().unwrap()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("actions.db");
        let backup = dir.join("backup.db");
        let conn = Connection::open(&path).unwrap();
        conn.execute_batch("CREATE TABLE scheduler_job_runs (job_id TEXT PRIMARY KEY, platform TEXT, account_id TEXT, status TEXT, started_at TEXT, scheduled_run TEXT, created_at TEXT);
            INSERT INTO scheduler_job_runs VALUES ('old','tiktok','a','success',NULL,NULL,'2026-01-01');").unwrap();
        drop(conn);
        prepare_actions_db(&path).unwrap();
        prepare_actions_db(&path).unwrap();
        let conn = Connection::open(&path).unwrap();
        assert_eq!(
            conn.query_row("PRAGMA journal_mode", [], |r| r.get::<_, String>(0))
                .unwrap(),
            "wal"
        );
        conn.execute_batch("PRAGMA wal_autocheckpoint=0; INSERT INTO scheduler_job_runs VALUES ('in-wal','tiktok','a','success',NULL,NULL,'2026-01-02');").unwrap();
        let reader = open_readonly(&path).unwrap();
        assert_eq!(
            reader
                .query_row("PRAGMA busy_timeout", [], |r| r.get::<_, i64>(0))
                .unwrap(),
            2000
        );
        assert!(reader
            .execute("DELETE FROM scheduler_job_runs", [])
            .is_err());
        backup_database(&path, &backup).unwrap();
        let copy = open_readonly(&backup).unwrap();
        assert_eq!(
            copy.query_row("SELECT COUNT(*) FROM scheduler_job_runs", [], |r| r
                .get::<_, i64>(0))
                .unwrap(),
            2
        );
        let plan: String = reader.query_row("EXPLAIN QUERY PLAN SELECT * FROM scheduler_job_runs WHERE platform='tiktok' AND COALESCE(started_at,scheduled_run,created_at)>='2026-01-01' ORDER BY COALESCE(started_at,scheduled_run,created_at) DESC, job_id DESC LIMIT 120", [], |r| r.get(3)).unwrap();
        assert!(
            plan.contains("idx_scheduler_runs_platform_time"),
            "{}",
            plan
        );
        drop((copy, reader, conn));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn absent_database_is_not_created_by_reader_or_setup() {
        let path = std::env::temp_dir().join(format!(
            "absent-scheduler-{}.db",
            chrono::Utc::now().timestamp_nanos_opt().unwrap()
        ));
        assert!(open_readonly(&path).is_err());
        prepare_actions_db(&path).unwrap();
        assert!(!path.exists());
    }
}
