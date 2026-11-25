//! Seven-day detail retention. Never remove account state or browser data.
use chrono::{Duration as Days, Local, NaiveDateTime};
use rusqlite::{params, Connection};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use crate::paths::ProjectPaths;

const LOG_BYTES: u64 = 10 * 1024 * 1024;
const ARCHIVE_BYTES: u64 = 100 * 1024 * 1024;
const BACKUP_BYTES: u64 = 1024 * 1024 * 1024;
const BATCH: usize = 500;

// Numeric facts only; original timestamps preserve custom time-range statistics.
// kind: 0 presence, 1 FYP session, 2 error, 3 skip, 4 like, 5 follow,
//       6 comment, 7 failed like, 8 failed target like.
const ARCHIVE_SCHEMA: &str = "CREATE TABLE IF NOT EXISTS action_stats_archive (
    platform TEXT NOT NULL, account_id TEXT NOT NULL, ts TEXT NOT NULL,
    kind INTEGER NOT NULL, handle TEXT NOT NULL, events INTEGER NOT NULL,
    value INTEGER NOT NULL,
    PRIMARY KEY(platform, account_id, ts, kind, handle)
) WITHOUT ROWID";

pub fn start() {
    let _ = std::thread::Builder::new()
        .name("data-retention".into())
        .spawn(|| {
            let mut cleaned_day = None;
            loop {
                if let Ok(paths) = crate::paths::project_paths() {
                    // Files go first: do not create a full database backup on a full disk.
                    prune_files(&paths);
                    let key = (paths.actions_db_path.clone(), Local::now().date_naive());
                    if cleaned_day.as_ref() != Some(&key)
                        && !Path::new(&paths.lock_file_path).exists()
                    {
                        let cutoff = (Local::now() - Days::days(7))
                            .format("%Y-%m-%dT%H:%M:%S")
                            .to_string();
                        match clean_database(
                            Path::new(&paths.actions_db_path),
                            &cutoff,
                            Path::new(&paths.lock_file_path),
                        ) {
                            Ok(true) => cleaned_day = Some(key),
                            Ok(false) => {}
                            Err(error) => eprintln!("Data retention deferred: {}", error),
                        }
                    }
                }
                // Also handles desktops which stay open for weeks; busy work retries later.
                std::thread::sleep(Duration::from_secs(3600));
            }
        });
}

fn exists(conn: &Connection, table: &str) -> rusqlite::Result<bool> {
    conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name=?1)",
        [table],
        |row| row.get(0),
    )
}

pub(crate) fn clean_database(path: &Path, cutoff: &str, lock: &Path) -> Result<bool, String> {
    if !path.is_file() || lock.exists() {
        return Ok(false);
    }
    let mut conn = Connection::open(path).map_err(|e| e.to_string())?;
    conn.busy_timeout(Duration::from_millis(100))
        .map_err(|e| e.to_string())?;
    let mut complete = true;
    if exists(&conn, "action_log").map_err(|e| e.to_string())? {
        conn.execute_batch(ARCHIVE_SCHEMA)
            .map_err(|e| e.to_string())?;
        conn.execute_batch("CREATE TEMP TABLE retention_keep_actions(id INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO retention_keep_actions
            SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY ts DESC, id DESC) AS n
                FROM action_log WHERE platform='tiktok') WHERE n=1;
            INSERT OR IGNORE INTO retention_keep_actions
            SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY ts DESC, id DESC) AS n
                FROM action_log WHERE platform='tiktok' AND action IN ('login_check','register_auto_complete')) WHERE n=1;")
            .map_err(|e| e.to_string())?;
        let started = Instant::now();
        let mut finished = false;
        while !lock.exists() && started.elapsed() < Duration::from_secs(3) {
            if archive_actions(&mut conn, cutoff).map_err(|e| e.to_string())? < BATCH {
                finished = true;
                break;
            }
        }
        complete &= finished;
    }
    for (table, selection) in [
        (
            "fyp_video_views",
            "SELECT id FROM fyp_video_views v WHERE platform='tiktok'
            AND collected_at < ?1 AND updated_at < ?1
            AND julianday(collected_at) IS NOT NULL AND julianday(updated_at) IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM fyp_video_views recent
                WHERE recent.platform=v.platform AND recent.account_id=v.account_id
                AND recent.session_id=v.session_id AND recent.updated_at >= ?1) LIMIT 500",
        ),
        (
            "scheduler_job_runs",
            "SELECT rowid FROM scheduler_job_runs WHERE platform='tiktok'
            AND status IN ('success','failed','skipped') AND ended_at < ?1
            AND julianday(ended_at) IS NOT NULL LIMIT 500",
        ),
    ] {
        if !exists(&conn, table).map_err(|e| e.to_string())? {
            continue;
        }
        let started = Instant::now();
        let mut finished = false;
        while !lock.exists() && started.elapsed() < Duration::from_secs(3) {
            let count = conn
                .execute(
                    &format!("DELETE FROM {table} WHERE rowid IN ({selection})"),
                    [cutoff],
                )
                .map_err(|e| e.to_string())?;
            if count < BATCH {
                finished = true;
                break;
            }
        }
        complete &= finished;
    }
    let _ = conn.execute_batch("PRAGMA wal_checkpoint(PASSIVE)");
    if complete {
        reclaim_space(&conn, path, lock);
    }
    Ok(complete && !lock.exists())
}

fn archive_actions(conn: &mut Connection, cutoff: &str) -> rusqlite::Result<usize> {
    // Summary and deletion share one transaction: retries cannot lose or double count facts.
    let tx = conn.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    let rows = {
        let mut statement = tx.prepare(
            "SELECT id, account_id, action, status, COALESCE(detail,''), ts
            FROM action_log WHERE platform='tiktok' AND ts < ?1
            AND julianday(ts) IS NOT NULL
            AND id NOT IN (SELECT id FROM retention_keep_actions) ORDER BY id LIMIT 500",
        )?;
        let rows = statement.query_map([cutoff], |r| {
            Ok((
                r.get::<_, i64>(0)?,
                r.get::<_, Option<String>>(1)?.unwrap_or_default(),
                r.get::<_, String>(2)?,
                r.get::<_, String>(3)?,
                r.get::<_, String>(4)?,
                r.get::<_, String>(5)?,
            ))
        })?;
        rows.collect::<rusqlite::Result<Vec<_>>>()?
    };
    for (id, account, action, status, detail, ts) in &rows {
        let (kind, value) = match (action.as_str(), status.as_str()) {
            ("fyp_browse", "ok") => (1, detail_count(detail, "videos")),
            ("session", "error") => (2, 0),
            ("session", "skip") => (3, 0),
            ("like", "ok") => (4, detail_count(detail, "count")),
            ("follow", "ok") => (5, detail_count(detail, "count")),
            ("comment", "ok") => (6, detail_count(detail, "count")),
            ("like", "fail") => (7, detail_count(detail, "count")),
            ("target_like", "fail") => (8, 0),
            _ => (0, 0),
        };
        let handle = if kind == 8 {
            detail
                .split_whitespace()
                .find_map(|p| p.strip_prefix("handle="))
                .unwrap_or("")
        } else {
            ""
        };
        tx.execute(
            "INSERT INTO action_stats_archive(platform,account_id,ts,kind,handle,events,value)
            VALUES ('tiktok',?1,?2,?3,?4,1,?5)
            ON CONFLICT(platform,account_id,ts,kind,handle) DO UPDATE SET
            events=events+excluded.events, value=value+excluded.value",
            params![account, ts, kind, handle, value],
        )?;
        tx.execute("DELETE FROM action_log WHERE id=?1", [id])?;
    }
    tx.commit()?;
    Ok(rows.len())
}

fn detail_count(detail: &str, key: &str) -> i64 {
    let prefix = format!("{key}=");
    detail
        .split_whitespace()
        .find_map(|p| {
            p.strip_prefix(&prefix)
                .and_then(|value| value.parse::<i64>().ok())
        })
        .unwrap_or(0)
        .max(0)
}

fn reclaim_space(conn: &Connection, path: &Path, lock: &Path) {
    let Ok(size) = path.metadata().map(|m| m.len()) else {
        return;
    };
    let free_pages: i64 = conn
        .query_row("PRAGMA freelist_count", [], |r| r.get(0))
        .unwrap_or(0);
    let pages: i64 = conn
        .query_row("PRAGMA page_count", [], |r| r.get(0))
        .unwrap_or(0);
    if lock.exists() || size < 64 * 1024 * 1024 || free_pages < pages / 4 {
        return;
    }
    let mode: i64 = conn
        .query_row("PRAGMA auto_vacuum", [], |r| r.get(0))
        .unwrap_or(0);
    // Interrupt expensive work promptly when an account starts; SQLite rolls it back.
    let lock_path = lock.to_path_buf();
    conn.progress_handler(1000, Some(move || lock_path.exists()));
    if mode == 2 {
        let _ = conn.execute_batch("PRAGMA incremental_vacuum(4096)");
    } else if available_bytes(path)
        .map(|n| n > size.saturating_mul(2) + 64 * 1024 * 1024)
        .unwrap_or(false)
    {
        let _ = conn.execute_batch("PRAGMA auto_vacuum=INCREMENTAL; VACUUM");
    }
    conn.progress_handler(0, None::<fn() -> bool>);
}

#[cfg(windows)]
fn available_bytes(path: &Path) -> Option<u64> {
    use std::os::windows::ffi::OsStrExt;
    let parent = path.parent()?;
    let wide: Vec<u16> = parent.as_os_str().encode_wide().chain(Some(0)).collect();
    let mut available = 0;
    let ok = unsafe {
        windows_sys::Win32::Storage::FileSystem::GetDiskFreeSpaceExW(
            wide.as_ptr(),
            &mut available,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
        )
    };
    if ok != 0 {
        Some(available)
    } else {
        None
    }
}

#[cfg(not(windows))]
fn available_bytes(path: &Path) -> Option<u64> {
    let output = std::process::Command::new("df")
        .args(["-Pk"])
        .arg(path.parent()?)
        .output()
        .ok()?;
    let text = String::from_utf8(output.stdout).ok()?;
    text.lines()
        .last()?
        .split_whitespace()
        .nth(3)?
        .parse::<u64>()
        .ok()?
        .checked_mul(1024)
}

pub(crate) fn append_log(path: &Path, bytes: &[u8]) -> std::io::Result<()> {
    let metadata = fs::metadata(path).ok();
    let now = Local::now();
    if let Some(metadata) = metadata {
        let modified: chrono::DateTime<Local> = metadata.modified()?.into();
        if metadata.len() >= LOG_BYTES || modified.date_naive() < now.date_naive() {
            let name = format!(
                "{}.{}-{}.log",
                path.file_stem().unwrap().to_string_lossy(),
                modified.format("%Y%m%d-%H%M%S"),
                now.timestamp_nanos_opt().unwrap_or_default()
            );
            fs::rename(path, path.with_file_name(name))?;
            prune_logs(path);
        }
    }
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?
        .write_all(bytes)
}

fn timestamp(text: &str) -> Option<NaiveDateTime> {
    NaiveDateTime::parse_from_str(text, "%Y%m%d-%H%M%S").ok()
}

fn prune_logs(path: &Path) {
    let Some(directory) = path.parent() else {
        return;
    };
    let Some(stem) = path.file_stem().and_then(|s| s.to_str()) else {
        return;
    };
    let prefix = format!("{stem}.");
    let cutoff = (Local::now() - Days::days(7)).naive_local();
    let mut archives = Vec::new();
    for entry in fs::read_dir(directory).into_iter().flatten().flatten() {
        if !entry.file_type().map(|t| t.is_file()).unwrap_or(false) {
            continue;
        }
        let name = entry.file_name().to_string_lossy().into_owned();
        let Some(rest) = name
            .strip_prefix(&prefix)
            .and_then(|s| s.strip_suffix(".log"))
        else {
            continue;
        };
        let Some((stamp, serial)) = rest.rsplit_once('-') else {
            continue;
        };
        if serial.is_empty() || !serial.bytes().all(|b| b.is_ascii_digit()) {
            continue;
        }
        if let (Some(stamp), Ok(metadata)) = (timestamp(stamp), entry.metadata()) {
            archives.push((stamp, entry.path(), metadata.len()));
        }
    }
    archives.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| b.1.cmp(&a.1)));
    let mut used = 0;
    for (stamp, path, size) in archives {
        if (stamp < cutoff || used + size > ARCHIVE_BYTES) && fs::remove_file(&path).is_ok() {
            continue;
        }
        used += size;
    }
}

fn prune_backups(source: &Path) {
    let Some(parent) = source.parent() else {
        return;
    };
    let Some(stem) = source.file_stem().and_then(|s| s.to_str()) else {
        return;
    };
    let Some(ext) = source.extension().and_then(|s| s.to_str()) else {
        return;
    };
    let prefix = format!("{stem}.");
    let suffix = format!(".{ext}");
    let now = Local::now().naive_local();
    let cutoff = now - Days::days(7);
    let mut backups = Vec::new();
    for entry in fs::read_dir(parent.join("backups"))
        .into_iter()
        .flatten()
        .flatten()
    {
        if !entry.file_type().map(|t| t.is_file()).unwrap_or(false) {
            continue;
        }
        let name = entry.file_name().to_string_lossy().into_owned();
        if let Some(stamp) = name
            .strip_prefix(&prefix)
            .and_then(|s| s.strip_suffix(&suffix))
            .and_then(timestamp)
        {
            if let Ok(metadata) = entry.metadata() {
                let writing = stamp > now - Days::minutes(15)
                    || metadata
                        .modified()
                        .ok()
                        .and_then(|t| t.elapsed().ok())
                        .is_some_and(|age| age < Duration::from_secs(900));
                backups.push((stamp, entry.path(), metadata.len(), writing));
            }
        }
    }
    backups.sort_by(|a, b| b.0.cmp(&a.0));
    let mut kept = 0;
    let mut used: u64 = 0;
    for (stamp, path, size, writing) in backups {
        if writing {
            continue;
        } // A backup may still be in the middle of a copy.
          // Never remove the latest nonempty backup, even for an inactive account.
        if size > 0
            && (kept == 0
                || (stamp >= cutoff && kept < 20 && used.saturating_add(size) <= BACKUP_BYTES))
        {
            kept += 1;
            used = used.saturating_add(size);
        } else {
            let _ = fs::remove_file(path);
        }
    }
}

fn prune_files(paths: &ProjectPaths) {
    for path in [
        &paths.comments_path,
        &paths.brand_comments_path,
        &paths.actions_db_path,
    ] {
        prune_backups(Path::new(path));
    }
    // Config backups are always named accounts.<timestamp>.yaml, even for a custom config path.
    prune_backups(&Path::new(&paths.config_path).with_file_name("accounts.yaml"));
    // Comment pools may use custom filenames under the config directory.
    if let (Some(parent), Ok(raw)) = (
        Path::new(&paths.config_path).parent(),
        fs::read_to_string(&paths.config_path),
    ) {
        for path in [&paths.comments_path, &paths.brand_comments_path] {
            if let Some(name) = Path::new(path).file_name() {
                prune_backups(&parent.join(name));
            }
        }
        if let Ok(config) = serde_yaml::from_str::<serde_yaml::Value>(&raw) {
            for key in ["general_file", "target_file"] {
                if let Some(name) = config
                    .get("platforms")
                    .and_then(|v| v.get("tiktok"))
                    .and_then(|v| v.get("comments"))
                    .and_then(|v| v.get(key))
                    .and_then(|v| v.as_str())
                {
                    if let Some(name) = Path::new(name).file_name() {
                        prune_backups(&parent.join(name));
                    }
                }
            }
        }
    }
    for path in [
        PathBuf::from(&paths.sessions_log_path),
        Path::new(&paths.logs_dir).join("scheduler.log"),
    ] {
        prune_logs(&path);
        // sessions.log is opened per write by Python; only rotate it while idle.
        if !Path::new(&paths.lock_file_path).exists()
            && path.file_name().is_some_and(|s| s == "sessions.log")
            && path.is_file()
        {
            let _ = append_log(&path, &[]);
        }
    }
    let cutoff = (Local::now() - Days::days(7)).naive_local();
    for entry in fs::read_dir(&paths.logs_dir)
        .into_iter()
        .flatten()
        .flatten()
    {
        if !entry.file_type().map(|t| t.is_file()).unwrap_or(false) {
            continue;
        }
        let name = entry.file_name().to_string_lossy().into_owned();
        if name
            .strip_prefix("support-bundle-")
            .and_then(|s| s.strip_suffix(".json"))
            .and_then(timestamp)
            .is_some_and(|stamp| stamp < cutoff)
        {
            let _ = fs::remove_file(entry.path());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn directory() -> PathBuf {
        let path = std::env::current_dir().unwrap().join(format!(
            "retention-test-{}-{}",
            std::process::id(),
            Local::now().timestamp_nanos_opt().unwrap()
        ));
        fs::create_dir(&path).unwrap();
        path
    }

    #[test]
    fn archive_is_atomic_repeatable_and_keeps_account_state_and_other_platforms() {
        let dir = directory();
        let db = dir.join("actions.db");
        let conn = Connection::open(&db).unwrap();
        conn.execute_batch("CREATE TABLE action_log(id INTEGER PRIMARY KEY,platform TEXT,account_id TEXT,action TEXT,status TEXT,detail TEXT,ts TEXT);
            INSERT INTO action_log VALUES
            (1,'tiktok','a','fyp_browse','ok','videos=12','2026-10-01T12:00:00'),
            (2,'tiktok','a','like','ok','count=4','2026-10-01T12:00:01'),
            (3,'tiktok','a','login_check','logged_in','keep login','2026-10-01T12:00:02'),
            (4,'tiktok','a','close','ok','keep latest','2026-10-01T12:00:03'),
            (5,'instagram','a','session','error','keep other platform','2026-10-01T12:00:00'),
            (6,'tiktok','b','like','ok','count=2','2026-11-18T12:00:00');
            CREATE TABLE fyp_video_views(id INTEGER PRIMARY KEY,platform TEXT,account_id TEXT,session_id TEXT,collected_at TEXT,updated_at TEXT);
            INSERT INTO fyp_video_views VALUES
            (1,'tiktok','a','old','2026-10-01','2026-10-01'),
            (2,'tiktok','a','active','2026-10-01','2026-10-01'),
            (3,'tiktok','a','active','2026-11-25','2026-11-25');
            CREATE TABLE scheduler_job_runs(job_id TEXT PRIMARY KEY,platform TEXT,status TEXT,ended_at TEXT);
            INSERT INTO scheduler_job_runs VALUES ('done','tiktok','success','2026-10-01'),('active','tiktok','running',NULL),('pending','tiktok','pending','2026-10-01'),('incomplete','tiktok','failed',NULL);
            CREATE TABLE target_follows(handle TEXT); INSERT INTO target_follows VALUES ('keep');").unwrap();
        for _ in 0..2 {
            clean_database(&db, "2026-11-18T12:00:00", &dir.join("run.lock")).unwrap();
        }
        assert_eq!(
            conn.query_row(
                "SELECT SUM(value) FROM action_stats_archive WHERE kind=1",
                [],
                |r| r.get::<_, i64>(0)
            )
            .unwrap(),
            12
        );
        assert_eq!(
            conn.query_row(
                "SELECT SUM(value) FROM action_stats_archive WHERE kind=4",
                [],
                |r| r.get::<_, i64>(0)
            )
            .unwrap(),
            4
        );
        assert_eq!(
            conn.query_row("SELECT COUNT(*) FROM action_log", [], |r| r
                .get::<_, i64>(0))
                .unwrap(),
            4
        );
        assert_eq!(
            conn.query_row("SELECT COUNT(*) FROM fyp_video_views", [], |r| r
                .get::<_, i64>(0))
                .unwrap(),
            2
        );
        assert_eq!(
            conn.query_row("SELECT COUNT(*) FROM scheduler_job_runs", [], |r| r
                .get::<_, i64>(0))
                .unwrap(),
            3
        );
        assert_eq!(
            conn.query_row("SELECT COUNT(*) FROM target_follows", [], |r| r
                .get::<_, i64>(0))
                .unwrap(),
            1
        );
        fs::write(dir.join("run.lock"), "active").unwrap();
        clean_database(&db, "2027-01-01", &dir.join("run.lock")).unwrap();
        assert_eq!(
            conn.query_row("SELECT COUNT(*) FROM action_log", [], |r| r
                .get::<_, i64>(0))
                .unwrap(),
            4
        );
        drop(conn);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn failed_archive_rolls_back_the_original_rows() {
        let mut conn = Connection::open_in_memory().unwrap();
        conn.execute_batch(ARCHIVE_SCHEMA).unwrap();
        conn.execute_batch("CREATE TABLE action_log(id INTEGER PRIMARY KEY,platform TEXT,account_id TEXT,action TEXT,status TEXT,detail TEXT,ts TEXT);
            CREATE TEMP TABLE retention_keep_actions(id INTEGER PRIMARY KEY);
            INSERT INTO action_log VALUES(1,'tiktok','a','like','ok','count=2','2026-01-01');
            CREATE TRIGGER reject_deletion BEFORE DELETE ON action_log BEGIN SELECT RAISE(ABORT,'test interruption'); END;").unwrap();
        assert!(archive_actions(&mut conn, "2026-11-18").is_err());
        assert_eq!(
            conn.query_row("SELECT COUNT(*) FROM action_stats_archive", [], |r| r
                .get::<_, i64>(0))
                .unwrap(),
            0
        );
        assert_eq!(
            conn.query_row("SELECT COUNT(*) FROM action_log", [], |r| r
                .get::<_, i64>(0))
                .unwrap(),
            1
        );
    }

    #[test]
    fn backup_cleanup_preserves_newest_backup_originals_and_unknown_files() {
        let dir = directory();
        fs::create_dir(dir.join("backups")).unwrap();
        let original = dir.join("accounts.yaml");
        fs::write(&original, "keep current").unwrap();
        for name in [
            "accounts.20260101-120000.yaml",
            "accounts.20260102-120000.yaml",
            "accounts.notes.yaml",
        ] {
            let path = dir.join("backups").join(name);
            fs::write(&path, "keep or prune").unwrap();
            fs::File::options()
                .write(true)
                .open(path)
                .unwrap()
                .set_times(
                    fs::FileTimes::new()
                        .set_modified(std::time::UNIX_EPOCH + Duration::from_secs(1_700_000_000)),
                )
                .unwrap();
        }
        prune_backups(&original);
        assert!(!dir.join("backups/accounts.20260101-120000.yaml").exists());
        assert!(dir.join("backups/accounts.20260102-120000.yaml").exists());
        assert!(dir.join("backups/accounts.notes.yaml").exists());
        assert_eq!(fs::read_to_string(&original).unwrap(), "keep current");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn log_rotation_bounds_archives_without_touching_unknown_files() {
        let dir = directory();
        let path = dir.join("scheduler.log");
        let file = fs::File::create(&path).unwrap();
        file.set_len(LOG_BYTES).unwrap();
        drop(file);
        fs::write(dir.join("scheduler.20200101-000000-1.log"), "expired").unwrap();
        fs::write(dir.join("scheduler.custom.log"), "keep").unwrap();
        append_log(&path, b"new\n").unwrap();
        assert_eq!(fs::read_to_string(&path).unwrap(), "new\n");
        assert!(!dir.join("scheduler.20200101-000000-1.log").exists());
        assert!(dir.join("scheduler.custom.log").exists());
        fs::remove_dir_all(dir).unwrap();
    }
}
