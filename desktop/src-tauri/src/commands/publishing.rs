//! Local immutable publication snapshots and conservative recovery.
use chrono::{SecondsFormat, Utc};
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    fs,
    path::Path,
    time::{Duration, UNIX_EPOCH},
};

pub fn timestamp() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true)
}
pub fn connect(path: &str) -> Result<Connection, String> {
    if let Some(parent) = Path::new(path).parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let conn = Connection::open(path).map_err(|e| e.to_string())?;
    conn.busy_timeout(Duration::from_millis(5000))
        .map_err(|e| e.to_string())?;
    migrate(&conn)?;
    Ok(conn)
}
pub const PUBLISH_SCHEMA: &str = r#"BEGIN IMMEDIATE;
      CREATE TABLE IF NOT EXISTS publish_batches (
       id TEXT PRIMARY KEY NOT NULL, platform TEXT NOT NULL DEFAULT 'tiktok', video_path TEXT NOT NULL,
       video_size_bytes INTEGER NOT NULL, video_modified_ns TEXT NOT NULL, caption TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS publish_records (
       id TEXT PRIMARY KEY NOT NULL, batch_id TEXT NOT NULL, account_id TEXT NOT NULL, provider TEXT NOT NULL,
       profile_binding_json TEXT NOT NULL, ordinal INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'queued', phase TEXT NOT NULL DEFAULT 'queued',
       handle TEXT, baseline_json TEXT, submitted_at TEXT, post_id TEXT, post_url TEXT, error_code TEXT, error_detail TEXT, evidence_json TEXT,
       verified_at TEXT, updated_at TEXT NOT NULL, UNIQUE(batch_id,account_id), UNIQUE(batch_id,ordinal));
      CREATE INDEX IF NOT EXISTS idx_publish_record_account ON publish_records(account_id,batch_id);
      COMMIT;"#;
pub fn migrate(conn: &Connection) -> Result<(), String> {
    conn.execute_batch(PUBLISH_SCHEMA).map_err(|e| {
        let _ = conn.execute_batch("ROLLBACK");
        e.to_string()
    })
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct VideoSource {
    pub path: String,
    pub file_name: String,
    pub size_bytes: String,
    pub modified_ns: String,
}
pub fn video_source(path: &str) -> Result<VideoSource, String> {
    let source = Path::new(path);
    if !source.is_absolute() {
        return Err("请选择本地视频绝对路径".into());
    }
    let ext = source
        .extension()
        .and_then(|v| v.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if !matches!(ext.as_str(), "mp4" | "mov" | "webm") {
        return Err("仅支持 mp4、mov、webm 视频".into());
    }
    let canonical = fs::canonicalize(source).map_err(|e| format!("视频不存在或不可读：{e}"))?;
    let metadata = fs::metadata(&canonical).map_err(|e| e.to_string())?;
    if !metadata.is_file() || metadata.len() == 0 {
        return Err("视频必须是非空文件".into());
    }
    fs::File::open(&canonical).map_err(|e| format!("视频不可读：{e}"))?;
    let modified_ns = metadata
        .modified()
        .map_err(|e| e.to_string())?
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos()
        .to_string();
    Ok(VideoSource {
        path: canonical
            .to_string_lossy()
            .trim_start_matches(r"\\?\")
            .to_string(),
        file_name: source
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into(),
        size_bytes: metadata.len().to_string(),
        modified_ns,
    })
}
pub fn create_batch(
    conn: &mut Connection,
    id: &str,
    video: &VideoSource,
    caption: &str,
    accounts: &[(String, String, String)],
) -> Result<(), String> {
    let tx = conn.transaction().map_err(|e| e.to_string())?;
    let now = timestamp();
    tx.execute("INSERT INTO publish_batches(id,platform,video_path,video_size_bytes,video_modified_ns,caption,created_at) VALUES (?1,'tiktok',?2,?3,?4,?5,?6)",params![id,video.path,video.size_bytes,video.modified_ns,caption,now]).map_err(|e|e.to_string())?;
    for (ordinal, (account, provider, binding)) in accounts.iter().enumerate() {
        tx.execute("INSERT INTO publish_records(id,batch_id,account_id,provider,profile_binding_json,ordinal,updated_at) VALUES (?1,?2,?3,?4,?5,?6,?7)",params![format!("{id}_{ordinal}"),id,account,provider,binding,ordinal as i64,now]).map_err(|e|e.to_string())?;
    }
    tx.commit().map_err(|e| e.to_string())
}
pub fn record_for_account(conn: &Connection, batch: &str, account: &str) -> Result<String, String> {
    conn.query_row(
        "SELECT id FROM publish_records WHERE batch_id=?1 AND account_id=?2",
        params![batch, account],
        |r| r.get(0),
    )
    .map_err(|e| e.to_string())
}
pub fn cancel(conn: &Connection, batch: &str, queued_only: bool) -> Result<(), String> {
    let sql = if queued_only {
        "UPDATE publish_records SET status='cancelled',error_code='cancelled',error_detail='已取消排队',updated_at=?2 WHERE batch_id=?1 AND status='queued'"
    } else {
        "UPDATE publish_records SET status='cancelled',error_code='cancelled',error_detail='用户停止',updated_at=?2 WHERE batch_id=?1 AND status IN ('queued','running','intervention_required')"
    };
    conn.execute(sql, params![batch, timestamp()])
        .map_err(|e| e.to_string())?;
    Ok(())
}
pub fn finish_interrupted(
    conn: &Connection,
    batch: &str,
    account: Option<&str>,
) -> Result<(), String> {
    conn.execute("UPDATE publish_records SET status=CASE WHEN status IN ('committing','verifying') THEN 'pending_confirmation' ELSE 'failed' END,error_code=CASE WHEN status IN ('committing','verifying') THEN 'interrupted_after_submit' ELSE 'interrupted_before_submit' END,error_detail='进程已退出，执行中断；不会自动重新发布',updated_at=?3 WHERE batch_id=?1 AND (?2 IS NULL OR account_id=?2) AND status IN ('running','intervention_required','committing','verifying')",params![batch,account,timestamp()]).map_err(|e|e.to_string())?;
    Ok(())
}
pub fn fail_start(conn: &Connection, record: &str, error: &str) -> Result<(), String> {
    conn.execute("UPDATE publish_records SET status='failed',error_code='start_failed',error_detail=?2,updated_at=?3 WHERE id=?1 AND status='queued'",params![record,error,timestamp()]).map_err(|e|e.to_string())?;
    Ok(())
}
pub fn reconcile(conn: &Connection) -> Result<(), String> {
    let tx = conn.unchecked_transaction().map_err(|e| e.to_string())?;
    tx.execute("UPDATE publish_records SET status='cancelled',error_code='interrupted_before_start',error_detail='应用中断，未执行',updated_at=?1 WHERE status='queued'",[timestamp()]).map_err(|e|e.to_string())?;
    tx.execute("UPDATE publish_records SET status=CASE WHEN status IN ('committing','verifying') THEN 'pending_confirmation' ELSE 'failed' END,error_code=CASE WHEN status IN ('committing','verifying') THEN 'interrupted_after_submit' ELSE 'interrupted_before_submit' END,error_detail='应用中断；不会自动重新发布',updated_at=?1 WHERE status IN ('running','intervention_required','committing','verifying')",[timestamp()]).map_err(|e|e.to_string())?;
    tx.commit().map_err(|e| e.to_string())
}
pub fn replay(
    conn: &Connection,
    id: &str,
    path: &str,
    caption: &str,
    ids: Option<&[String]>,
) -> Result<Option<String>, String> {
    let row: Option<(String, String)> = conn
        .query_row(
            "SELECT video_path,caption FROM publish_batches WHERE id=?1",
            [id],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    let Some((old_path, old_caption)) = row else {
        return Ok(None);
    };
    if old_path != path || old_caption != caption {
        return Err("request_conflict：请求内容与原任务不一致".into());
    }
    if let Some(ids) = ids {
        let mut stmt = conn
            .prepare("SELECT account_id FROM publish_records WHERE batch_id=?1 ORDER BY ordinal")
            .map_err(|e| e.to_string())?;
        let old = stmt
            .query_map([id], |r| r.get::<_, String>(0))
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        if old != ids {
            return Err("request_conflict：账号名单与原任务不一致".into());
        }
    }
    let active:i64=conn.query_row("SELECT count(*) FROM publish_records WHERE batch_id=?1 AND status IN ('queued','running','intervention_required','committing','verifying')",[id],|r|r.get(0)).map_err(|e|e.to_string())?;
    Ok(Some(
        if active > 0 { "running" } else { "completed" }.into(),
    ))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PublishFilter {
    pub platform: String,
    pub account_id: Option<String>,
    pub status: Option<String>,
    pub from: Option<String>,
    pub to: Option<String>,
    pub page: Option<u32>,
    pub page_size: Option<u32>,
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublishPage {
    pub items: Vec<Value>,
    pub total: i64,
    pub page: u32,
    pub page_size: u32,
}
#[tauri::command]
pub fn query_publish_records(
    filter: PublishFilter,
    state: tauri::State<'_, crate::state::AppState>,
) -> Result<PublishPage, String> {
    if filter.platform != "tiktok" {
        return Err("当前平台不支持视频发布".into());
    }
    let paths = crate::paths::project_paths()?;
    let run = state.current_run.lock().map_err(|_| "运行状态锁失败")?;
    if run.child.is_none()
        && !matches!(
            run.status.as_str(),
            "starting" | "running" | "pause_pending" | "intervention_required" | "stopping"
        )
        && Path::new(&paths.actions_db_path).exists()
    {
        match super::process::ensure_publish_lock_released(
            &Path::new(&paths.data_dir).join("run.lock"),
        ) {
            Ok(()) => {}
            Err(error) if error == "旧任务进程仍在运行" => {
                return query(&paths.actions_db_path, filter)
            }
            Err(error) => return Err(error),
        }
        // Do not migrate a legacy database simply to display an empty page.
        let conn = Connection::open(&paths.actions_db_path).map_err(|e| e.to_string())?;
        let exists: i64 = conn
            .query_row(
                "SELECT count(*) FROM sqlite_master WHERE name='publish_records' AND type='table'",
                [],
                |r| r.get(0),
            )
            .map_err(|e| e.to_string())?;
        if exists > 0 {
            conn.busy_timeout(Duration::from_millis(5000))
                .map_err(|e| e.to_string())?;
            reconcile(&conn)?;
        }
    }
    query(&paths.actions_db_path, filter)
}

pub fn batch_status(conn: &Connection, batch: &str) -> Result<String, String> {
    let (total,verified,active):(i64,i64,i64)=conn.query_row("SELECT count(*),coalesce(sum(status='verified'),0),coalesce(sum(status IN ('queued','running','intervention_required','committing','verifying')),0) FROM publish_records WHERE batch_id=?1",[batch],|r|Ok((r.get(0)?,r.get(1)?,r.get(2)?))).map_err(|e|e.to_string())?;
    Ok(if active > 0 {
        "running"
    } else if total > 0 && total == verified {
        "completed"
    } else if verified > 0 {
        "partial_failed"
    } else {
        "failed"
    }
    .into())
}
pub fn query(path: &str, filter: PublishFilter) -> Result<PublishPage, String> {
    if filter.platform != "tiktok" {
        return Err("当前平台不支持视频发布".into());
    }
    let page = filter.page.unwrap_or(1);
    let size = filter.page_size.unwrap_or(20);
    if page == 0 || !(1..=100).contains(&size) {
        return Err("分页参数无效".into());
    }
    if let Some(status) = filter.status.as_deref() {
        if ![
            "queued",
            "running",
            "intervention_required",
            "committing",
            "verifying",
            "verified",
            "pending_confirmation",
            "failed",
            "skipped",
            "cancelled",
        ]
        .contains(&status)
        {
            return Err("发布状态无效".into());
        }
    }
    let parse = |v: Option<String>| -> Result<Option<String>, String> {
        v.map(|v| {
            chrono::DateTime::parse_from_rfc3339(&v)
                .map(|v| {
                    v.with_timezone(&Utc)
                        .to_rfc3339_opts(SecondsFormat::Millis, true)
                })
                .map_err(|_| "时间参数无效".into())
        })
        .transpose()
    };
    let from = parse(filter.from)?;
    let to = parse(filter.to)?;
    if matches!((&from,&to),(Some(a),Some(b)) if a>=b) {
        return Err("时间范围无效".into());
    }
    let empty = || PublishPage {
        items: vec![],
        total: 0,
        page,
        page_size: size,
    };
    if !Path::new(path).exists() {
        return Ok(empty());
    }
    let conn = Connection::open_with_flags(path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|e| e.to_string())?;
    conn.busy_timeout(Duration::from_millis(5000))
        .map_err(|e| e.to_string())?;
    let tables:i64=conn.query_row("SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('publish_records','publish_batches')",[],|r|r.get(0)).map_err(|e|e.to_string())?;
    if tables == 0 {
        return Ok(empty());
    }
    let clause=" FROM publish_records r JOIN publish_batches b ON b.id=r.batch_id WHERE b.platform=?1 AND (?2 IS NULL OR r.account_id=?2) AND (?3 IS NULL OR r.status=?3) AND (?4 IS NULL OR b.created_at>=?4) AND (?5 IS NULL OR b.created_at<?5)";
    let total = conn
        .query_row(
            &format!("SELECT count(*){clause}"),
            params![filter.platform, filter.account_id, filter.status, from, to],
            |r| r.get(0),
        )
        .map_err(|e| e.to_string())?;
    let mut stmt=conn.prepare(&format!("SELECT r.*,b.platform,b.video_path,b.caption,b.created_at{clause} ORDER BY b.created_at DESC,r.id DESC LIMIT ?6 OFFSET ?7")).map_err(|e|e.to_string())?;
    let rows = stmt
        .query_map(
            params![
                filter.platform,
                filter.account_id,
                filter.status,
                from,
                to,
                size,
                (page as i64 - 1) * size as i64
            ],
            |r| {
                let mut obj = serde_json::Map::new();
                for (index, name) in [
                    "id",
                    "batchId",
                    "accountId",
                    "provider",
                    "profileBindingJson",
                    "ordinal",
                    "status",
                    "phase",
                    "handle",
                    "baselineJson",
                    "submittedAt",
                    "postId",
                    "postUrl",
                    "errorCode",
                    "errorDetail",
                    "evidenceJson",
                    "verifiedAt",
                    "updatedAt",
                    "platform",
                    "videoPath",
                    "caption",
                    "createdAt",
                ]
                .iter()
                .enumerate()
                {
                    let value = match r.get_ref(index)? {
                        rusqlite::types::ValueRef::Null => Value::Null,
                        rusqlite::types::ValueRef::Integer(v) => json!(v),
                        rusqlite::types::ValueRef::Text(v) => json!(String::from_utf8_lossy(v)),
                        _ => Value::Null,
                    };
                    obj.insert(name.to_string(), value);
                }
                Ok(Value::Object(obj))
            },
        )
        .map_err(|e| e.to_string())?;
    let items = rows
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;
    Ok(PublishPage {
        items,
        total,
        page,
        page_size: size,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn seeded() -> Connection {
        let mut conn = Connection::open_in_memory().unwrap();
        migrate(&conn).unwrap();
        create_batch(
            &mut conn,
            "B1",
            &VideoSource {
                path: "D:/海边 视频.mp4".into(),
                file_name: "海边 视频.mp4".into(),
                size_bytes: "12".into(),
                modified_ns: "1700000000000000000".into(),
            },
            "海边\n#旅行",
            &[
                (
                    "tiktok_1".into(),
                    "bitbrowser".into(),
                    "{\"profile_id\":\"p1\"}".into(),
                ),
                (
                    "tiktok_2".into(),
                    "ixbrowser".into(),
                    "{\"profile_id\":\"2\"}".into(),
                ),
            ],
        )
        .unwrap();
        conn
    }
    #[test]
    fn migration_twice_preserves_legacy_and_rolls_back_failed_batch() {
        let mut conn = Connection::open_in_memory().unwrap();
        conn.execute("CREATE TABLE action_log(id INTEGER)", [])
            .unwrap();
        conn.execute("INSERT INTO action_log VALUES(9)", [])
            .unwrap();
        migrate(&conn).unwrap();
        migrate(&conn).unwrap();
        assert_eq!(
            conn.query_row("SELECT id FROM action_log", [], |r| r.get::<_, i64>(0))
                .unwrap(),
            9
        );
        let video = VideoSource {
            path: "C:/video.mp4".into(),
            file_name: "video.mp4".into(),
            size_bytes: "2".into(),
            modified_ns: "3".into(),
        };
        assert!(create_batch(
            &mut conn,
            "bad",
            &video,
            "",
            &[
                ("same".into(), "bitbrowser".into(), "{}".into()),
                ("same".into(), "ixbrowser".into(), "{}".into())
            ]
        )
        .is_err());
        assert_eq!(
            conn.query_row("SELECT count(*) FROM publish_batches", [], |r| r
                .get::<_, i64>(0))
                .unwrap(),
            0
        );
    }
    #[test]
    fn replay_retains_original_snapshot_and_checks_order() {
        let conn = seeded();
        let ids = vec!["tiktok_1".into(), "tiktok_2".into()];
        assert_eq!(
            replay(&conn, "B1", "D:/海边 视频.mp4", "海边\n#旅行", Some(&ids)).unwrap(),
            Some("running".into())
        );
        assert!(replay(&conn, "B1", "D:/海边 视频.mp4", "changed", Some(&ids)).is_err());
        assert!(replay(
            &conn,
            "B1",
            "D:/海边 视频.mp4",
            "海边\n#旅行",
            Some(&["tiktok_2".into(), "tiktok_1".into()])
        )
        .is_err());
        assert!(replay(&conn, "B1", "D:/海边 视频.mp4", "海边\n#旅行", None)
            .unwrap()
            .is_some());
    }
    #[test]
    fn cancellation_wins_before_submit_but_never_overwrites_committing_or_verified() {
        let conn = seeded();
        conn.execute("UPDATE publish_records SET status='running'", [])
            .unwrap();
        cancel(&conn, "B1", false).unwrap();
        assert_eq!(conn.execute("UPDATE publish_records SET status='committing' WHERE id='B1_0' AND status='running'",[]).unwrap(),0);
        conn.execute(
            "UPDATE publish_records SET status='committing' WHERE id='B1_0'",
            [],
        )
        .unwrap();
        conn.execute(
            "UPDATE publish_records SET status='verified' WHERE id='B1_1'",
            [],
        )
        .unwrap();
        cancel(&conn, "B1", false).unwrap();
        finish_interrupted(&conn, "B1", None).unwrap();
        assert_eq!(
            conn.query_row(
                "SELECT status FROM publish_records WHERE id='B1_0'",
                [],
                |r| r.get::<_, String>(0)
            )
            .unwrap(),
            "pending_confirmation"
        );
        assert_eq!(
            conn.query_row(
                "SELECT status FROM publish_records WHERE id='B1_1'",
                [],
                |r| r.get::<_, String>(0)
            )
            .unwrap(),
            "verified"
        );
    }
    #[test]
    fn graceful_stop_only_cancels_queued_and_recovery_never_requeues() {
        let conn = seeded();
        conn.execute(
            "UPDATE publish_records SET status='verifying' WHERE id='B1_0'",
            [],
        )
        .unwrap();
        cancel(&conn, "B1", true).unwrap();
        reconcile(&conn).unwrap();
        assert_eq!(
            conn.query_row(
                "SELECT status FROM publish_records WHERE id='B1_0'",
                [],
                |r| r.get::<_, String>(0)
            )
            .unwrap(),
            "pending_confirmation"
        );
        assert_eq!(
            conn.query_row(
                "SELECT status FROM publish_records WHERE id='B1_1'",
                [],
                |r| r.get::<_, String>(0)
            )
            .unwrap(),
            "cancelled"
        );
    }
    #[test]
    fn batch_summary_uses_business_records_not_process_exit_code() {
        let conn = seeded();
        assert_eq!(batch_status(&conn, "B1").unwrap(), "running");
        conn.execute(
            "UPDATE publish_records SET status='pending_confirmation'",
            [],
        )
        .unwrap();
        assert_eq!(batch_status(&conn, "B1").unwrap(), "failed");
        conn.execute(
            "UPDATE publish_records SET status='verified' WHERE id='B1_0'",
            [],
        )
        .unwrap();
        assert_eq!(batch_status(&conn, "B1").unwrap(), "partial_failed");
        conn.execute("UPDATE publish_records SET status='verified'", [])
            .unwrap();
        assert_eq!(batch_status(&conn, "B1").unwrap(), "completed");
        cancel(&conn, "B1", false).unwrap();
        reconcile(&conn).unwrap();
        assert_eq!(batch_status(&conn, "B1").unwrap(), "completed");
    }
    #[test]
    fn video_source_preserves_unicode_absolute_path_and_rejects_invalid_source() {
        let path = std::env::temp_dir().join(format!("海边 视频 {}.mp4", std::process::id()));
        fs::write(&path, b"fixture").unwrap();
        let video = video_source(path.to_str().unwrap()).unwrap();
        assert!(video.path.contains("海边 视频"));
        assert_eq!(video.size_bytes, "7");
        assert!(video.modified_ns.parse::<u128>().is_ok());
        assert!(video_source("relative.mp4").is_err());
        fs::write(&path, b"").unwrap();
        assert!(video_source(path.to_str().unwrap()).is_err());
        fs::remove_file(&path).unwrap();
        assert!(video_source(path.to_str().unwrap()).is_err());
    }
    fn filter() -> PublishFilter {
        PublishFilter {
            platform: "tiktok".into(),
            account_id: None,
            status: None,
            from: None,
            to: None,
            page: Some(1),
            page_size: Some(20),
        }
    }
    #[test]
    fn query_parameters_exact_and_combined_with_utc_boundaries() {
        let path = std::env::temp_dir().join(format!("publish-query-{}.db", std::process::id()));
        let conn = seeded();
        let target = Connection::open(&path).unwrap();
        migrate(&target).unwrap();
        drop(target);
        // Write through the production creation path to a local disposable database.
        let mut target = connect(path.to_str().unwrap()).unwrap();
        create_batch(
            &mut target,
            "query",
            &VideoSource {
                path: "D:/海边.mp4".into(),
                file_name: "海边.mp4".into(),
                size_bytes: "2".into(),
                modified_ns: "3".into(),
            },
            "完整\n文案",
            &[("deleted_account".into(), "bitbrowser".into(), "{}".into())],
        )
        .unwrap();
        target
            .execute(
                "UPDATE publish_batches SET created_at='2026-10-14T16:00:00.000Z'",
                [],
            )
            .unwrap();
        target
            .execute(
                "UPDATE publish_records SET status='pending_confirmation'",
                [],
            )
            .unwrap();
        drop(target);
        drop(conn);
        let mut f = filter();
        f.account_id = Some("deleted_account".into());
        f.status = Some("pending_confirmation".into());
        f.from = Some("2026-10-15T00:00:00+08:00".into());
        f.to = Some("2026-10-16T00:00:00+08:00".into());
        let page = query(path.to_str().unwrap(), f).unwrap();
        assert_eq!(page.total, 1);
        assert_eq!(page.items[0]["caption"], "完整\n文案");
        let mut injected = filter();
        injected.account_id = Some("' OR 1=1 --".into());
        assert_eq!(query(path.to_str().unwrap(), injected).unwrap().total, 0);
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn query_missing_is_empty_but_corrupt_is_error_and_invalid_filters_rejected() {
        let path = std::env::temp_dir().join(format!("publish-corrupt-{}.db", std::process::id()));
        assert_eq!(query(path.to_str().unwrap(), filter()).unwrap().total, 0);
        fs::write(&path, b"corrupt database").unwrap();
        assert!(query(path.to_str().unwrap(), filter()).is_err());
        fs::remove_file(path).unwrap();
        let mut f = filter();
        f.status = Some("success".into());
        assert!(query("missing", f).is_err());
        let mut f = filter();
        f.page_size = Some(101);
        assert!(query("missing", f).is_err());
    }
}
