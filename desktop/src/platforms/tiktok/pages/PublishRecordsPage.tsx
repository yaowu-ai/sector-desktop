import { Alert, Button, Card, DatePicker, Descriptions, Drawer, Empty, Input, Select, Space, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Dayjs } from 'dayjs';
import { usePlatformContext } from '../../../app/PlatformContext';
import { PageHeader } from '../../../components/PageHeader';
import { ProcessOutputPanel } from '../../../components/ProcessOutputPanel';
import { StatusTag } from '../../../components/StatusTag';
import { usePublishingRun } from '../../../hooks/usePublishingRun';
import { openExternalLink, queryPublishRecords, recheckTikTokPublish } from '../../../services/api';
import { PUBLISH_PHASE_LABELS, PUBLISH_STATUS_LABELS, formatPublishEvidence, publicationDateFilter, safeTikTokPostUrl } from '../../../services/publishing';
import type { PublishRecord, PublishRecordFilter, PublishRecordPage, PublishStatus } from '../../../services/types';

const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—';
const fileName = (value: string) => value.split(/[\\/]/).pop() || value;
const statusTag = (record: PublishRecord) => <StatusTag status={record.status === 'verified' ? 'ok' : record.status === 'failed' ? 'error' : record.status === 'pending_confirmation' || record.status === 'intervention_required' ? 'warning' : ['cancelled', 'skipped', 'queued'].includes(record.status) ? 'idle' : 'running'} label={PUBLISH_STATUS_LABELS[record.status] ?? record.status} />;

export function PublishRecordsPage() {
  const { currentPlatform } = usePlatformContext();
  const [accountId, setAccountId] = useState('');
  const [status, setStatus] = useState<PublishStatus>();
  const [dates, setDates] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [filter, setFilter] = useState<PublishRecordFilter>({ platform: 'tiktok', page: 1, pageSize: 20 });
  const [data, setData] = useState<PublishRecordPage>({ items: [], total: 0, page: 1, pageSize: 20 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [detail, setDetail] = useState<PublishRecord>();
  const [rechecking, setRechecking] = useState<string>();
  const generation = useRef(0);
  const { busy, status: runStatus } = usePublishingRun();
  const refresh = useCallback(async () => {
    if (currentPlatform !== 'tiktok') return;
    const request = ++generation.current;
    setLoading(true);
    try {
      const page = await queryPublishRecords(filter);
      if (request !== generation.current) return;
      setData(page); setError(undefined);
      setDetail(current => current ? page.items.find(item => item.id === current.id) ?? current : undefined);
    } catch (value) { if (request === generation.current) setError(value instanceof Error ? value.message : String(value)); }
    finally { if (request === generation.current) setLoading(false); }
  }, [filter, currentPlatform]);
  useEffect(() => { void refresh(); return () => { generation.current++; }; }, [refresh]);
  useEffect(() => {
    if (!busy) { void refresh(); return; }
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => window.clearInterval(timer);
  }, [busy, refresh, runStatus?.status]);
  const search = () => {
    try {
      const dateFilter = publicationDateFilter(dates?.[0]?.format('YYYY-MM-DD') ?? '', dates?.[1]?.format('YYYY-MM-DD') ?? '');
      setFilter({ platform: 'tiktok', accountId: accountId || undefined, status, ...dateFilter, page: 1, pageSize: filter.pageSize });
    } catch (value) { message.error(String(value)); }
  };
  const recheck = async (record: PublishRecord) => {
    if (busy || rechecking || record.status !== 'pending_confirmation') return;
    setRechecking(record.id);
    try { await recheckTikTokPublish(record.id); message.success('已启动重新核验，只检查本人主页，不会重新上传或发布'); await refresh(); }
    catch (value) { message.error(value instanceof Error ? value.message : String(value)); }
    finally { setRechecking(undefined); }
  };
  const openPost = async (record: PublishRecord) => {
    if (!record.postUrl || !safeTikTokPostUrl(record.postUrl)) { message.error('作品链接无效'); return; }
    try { await openExternalLink(record.postUrl); } catch (value) { message.error(String(value)); }
  };
  const actions = (record: PublishRecord) => <Space wrap>
    {record.status === 'verified' && record.postUrl && safeTikTokPostUrl(record.postUrl) ? <Button type="link" size="small" onClick={() => void openPost(record)}>查看作品</Button> : null}
    <Button type="link" size="small" onClick={() => setDetail(record)}>详情</Button>
    {record.status === 'pending_confirmation' ? <Button size="small" disabled={busy || Boolean(rechecking)} loading={rechecking === record.id} onClick={() => void recheck(record)}>重新核验</Button> : null}
  </Space>;
  const columns: ColumnsType<PublishRecord> = [
    { title: '创建时间', dataIndex: 'createdAt', width: 175, render: formatTime },
    { title: '账号', dataIndex: 'accountId', width: 150, ellipsis: true },
    { title: '视频', dataIndex: 'videoPath', width: 160, ellipsis: true, render: fileName },
    { title: '文案摘要', dataIndex: 'caption', width: 200, ellipsis: true, render: (value: string) => value || '（空文案）' },
    { title: '状态', key: 'status', width: 150, render: (_, record) => statusTag(record) },
    { title: '提交时间', dataIndex: 'submittedAt', width: 175, render: formatTime },
    { title: '操作', key: 'actions', width: 240, render: (_, record) => actions(record) },
  ];
  if (currentPlatform !== 'tiktok') return <Alert type="info" message="当前平台不支持视频发布记录" />;
  return <>
    <PageHeader title="发布记录" description="逐账号保存发布事实。已确认成功表示本次视频在本人主页可见。" extra={<Button icon={<RefreshCw size={16} />} onClick={() => void refresh()} loading={loading}>刷新</Button>} />
    <Space direction="vertical" size={24} className="full-width">
      <Card title="筛选记录">
        <Space wrap size={12}>
          <Input aria-label="筛选账号" placeholder="账号 ID（精确匹配，含已删除账号）" value={accountId} onChange={event => setAccountId(event.target.value)} style={{ width: 280 }} allowClear onPressEnter={search} />
          <Select aria-label="筛选发布状态" placeholder="全部状态" allowClear value={status} onChange={setStatus} style={{ width: 160 }} options={Object.entries(PUBLISH_STATUS_LABELS).map(([value, label]) => ({ value, label }))} />
          <DatePicker.RangePicker value={dates} onChange={value => setDates(value)} />
          <Button type="primary" onClick={search}>查询</Button>
          <Button onClick={() => { setAccountId(''); setStatus(undefined); setDates(null); setFilter({ platform: 'tiktok', page: 1, pageSize: 20 }); }}>重置</Button>
        </Space>
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>按创建日期筛选，包含起止两天（本地时间）。</Typography.Paragraph>
      </Card>
      {error ? <Alert type="error" showIcon message="发布记录读取失败" description={error} action={<Button onClick={() => void refresh()}>重试</Button>} /> : null}
      <Card>
        <Table<PublishRecord> rowKey="id" columns={columns} dataSource={error ? [] : data.items} loading={loading} scroll={{ x: 1250 }} locale={{ emptyText: error ? '读取失败，请重试' : <Empty description={filter.accountId || filter.status || filter.from || filter.to ? '没有符合条件的发布记录' : '暂无发布记录'}><a href="#publish">去发布作品</a></Empty> }}
          pagination={{ current: filter.page, pageSize: filter.pageSize, total: data.total, showSizeChanger: true, pageSizeOptions: [20, 50, 100], onChange: (page, pageSize) => setFilter(current => ({ ...current, page: pageSize !== current.pageSize ? 1 : page, pageSize })) }} />
      </Card>
      <ProcessOutputPanel title="发布与重新核验进度" />
    </Space>
    <Drawer title="发布记录详情" open={Boolean(detail)} onClose={() => setDetail(undefined)} width={640}>
      {detail ? <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="账号">{detail.accountId}</Descriptions.Item>
        <Descriptions.Item label="批次">{detail.batchId}</Descriptions.Item>
        <Descriptions.Item label="浏览器">{({ bitbrowser: 'BitBrowser', ixbrowser: 'ixBrowser', builtin_chromium: '内置 Chromium' })[detail.provider] ?? detail.provider}</Descriptions.Item>
        <Descriptions.Item label="状态">{statusTag(detail)}</Descriptions.Item>
        <Descriptions.Item label="执行阶段">{PUBLISH_PHASE_LABELS[detail.phase] ?? detail.phase}</Descriptions.Item>
        <Descriptions.Item label="创建时间">{formatTime(detail.createdAt)}</Descriptions.Item>
        <Descriptions.Item label="提交时间">{formatTime(detail.submittedAt)}</Descriptions.Item>
        <Descriptions.Item label="更新时间">{formatTime(detail.updatedAt)}</Descriptions.Item>
        <Descriptions.Item label="视频路径"><Typography.Text copyable style={{ overflowWrap: 'anywhere' }}>{detail.videoPath}</Typography.Text></Descriptions.Item>
        <Descriptions.Item label="完整文案"><div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{detail.caption || '（空文案）'}</div></Descriptions.Item>
        <Descriptions.Item label="原因">{detail.errorDetail || '—'}{detail.errorCode ? `（${detail.errorCode}）` : ''}</Descriptions.Item>
        <Descriptions.Item label="核验证据"><div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{formatPublishEvidence(detail.evidenceJson)}</div></Descriptions.Item>
        <Descriptions.Item label="操作">{actions(detail)}</Descriptions.Item>
      </Descriptions> : null}
    </Drawer>
  </>;
}
