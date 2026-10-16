"""DB1 record state owner. Schema and immutable batches are owned by Rust."""
import json
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


TRANSITIONS = {
    'queued': {'running','failed','skipped','cancelled'},
    'running': {'running','intervention_required','committing','failed','skipped','cancelled'},
    'intervention_required': {'running','failed','skipped','cancelled'},
    'committing': {'verifying','failed','pending_confirmation'},
    'verifying': {'verified','pending_confirmation'},
    'pending_confirmation': {'pending_confirmation','verified'},
}
FIELDS = {'handle','baseline_json','submitted_at','post_id','post_url','error_code',
          'error_detail','evidence_json','verified_at'}


class PublishStore:
    def __init__(self, conn):
        self.conn = conn
        conn.execute('PRAGMA busy_timeout=5000')

    def record(self, record_id):
        cursor = self.conn.execute('SELECT r.*, b.video_path,b.video_size_bytes,b.video_modified_ns,b.caption '
                                   'FROM publish_records r JOIN publish_batches b ON b.id=r.batch_id WHERE r.id=?', (record_id,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError('发布记录不存在')
        return dict(zip((column[0] for column in cursor.description), row))

    def for_account(self, batch_id, account_id):
        row = self.conn.execute('SELECT id FROM publish_records WHERE batch_id=? AND account_id=?',
                                (batch_id,account_id)).fetchone()
        if row is None:
            raise ValueError('账号不属于本次发布批次')
        return self.record(row[0])

    def transition(self, record_id, expected, status, phase, **fields):
        if not expected or any(status not in TRANSITIONS.get(source,set()) for source in expected):
            raise ValueError('非法发布状态转换')
        if not fields.keys() <= FIELDS:
            raise ValueError('非法发布字段')
        values = {'status':status,'phase':phase,'updated_at':utc_now(),**fields}
        sql = 'UPDATE publish_records SET ' + ','.join(key+'=?' for key in values)
        sql += ' WHERE id=? AND status IN (' + ','.join('?' for _ in expected) + ')'
        with self.conn:
            cursor = self.conn.execute(sql, (*values.values(),record_id,*expected))
        changed = cursor.rowcount == 1
        if changed:
            self.emit(record_id)
        return changed

    def claim(self, record_id):
        return self.transition(record_id,('queued',),'running','opening')

    def phase(self, record_id, phase, **fields):
        if not self.transition(record_id,('running',),'running',phase,**fields):
            raise RuntimeError('发布任务已取消或已由其他进程执行')

    def emit(self, record_id):
        row = self.record(record_id)
        event = {key:row.get(column) for key,column in {
            'batchId':'batch_id','recordId':'id','accountId':'account_id',
            'status':'status','phase':'phase','errorCode':'error_code',
            'errorDetail':'error_detail','postId':'post_id','postUrl':'post_url'}.items()}
        print('AM_PUBLISH_EVENT ' + json.dumps(event,ensure_ascii=True),flush=True)
