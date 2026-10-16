import { Alert, Button, Card, Descriptions, Form, Input, Modal, Select, Space, Typography, message } from 'antd';
import { FileText, FolderOpen, Play } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { usePlatformContext } from '../../../app/PlatformContext';
import { PageHeader } from '../../../components/PageHeader';
import { ProcessOutputPanel } from '../../../components/ProcessOutputPanel';
import { AccountBrowserEnvironment } from '../../../components/AccountBrowserEnvironment';
import { usePublishingRun } from '../../../hooks/usePublishingRun';
import { loadConfig, runTikTokPublish, selectPublishVideo } from '../../../services/api';
import { importCaptionFile } from '../../../services/captionImport';
import { buildPublishRequest } from '../../../services/publishing';
import type { Account, PublishMode, PublishVideoSelection } from '../../../services/types';

export function PublishPage() {
  const { currentPlatform } = usePlatformContext();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [video, setVideo] = useState<PublishVideoSelection | null>(null);
  const [caption, setCaption] = useState('');
  const [mode, setMode] = useState<PublishMode>('all');
  const [ids, setIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [choosingVideo, setChoosingVideo] = useState(false);
  const [starting, setStarting] = useState(false);
  const [batchId, setBatchId] = useState<string>();
  const [error, setError] = useState<string>();
  const fileInput = useRef<HTMLInputElement>(null);
  const mounted = useRef(true);
  const { busy } = usePublishingRun();
  useEffect(() => {
    mounted.current = true;
    let active = true;
    setLoading(true);
    void loadConfig().then(config => { if (active) setAccounts(config.accounts.filter(a => a.platform === 'tiktok' && a.enabled)); })
      .catch(value => { if (active) setError(String(value)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; mounted.current = false; };
  }, [currentPlatform]);
  const runAccounts = mode === 'all' ? accounts : ids.map(id => accounts.find(a => a.id === id)).filter((a): a is Account => Boolean(a));
  const invalidCaption = caption.length > 4000 || caption.includes('\0');
  const showError = (value: unknown) => { const text = value instanceof Error ? value.message : String(value); setError(text); message.error(text); };
  const chooseVideo = async () => {
    if (!('__TAURI_INTERNALS__' in window)) { showError('请在 Windows 桌面应用中选择本地视频'); return; }
    setChoosingVideo(true);
    try { const result = await selectPublishVideo(); if (result) setVideo(result); } catch (value) { showError(value); }
    finally { setChoosingVideo(false); }
  };
  const importFile = async (file: File) => {
    setImporting(true);
    try {
      const text = await importCaptionFile(file);
      if (!mounted.current) return;
      if (caption.length) {
        await new Promise<void>(resolve => {
          Modal.confirm({ title: '替换当前文案？', content: '文件内容将整体替换输入框中的文案，导入后仍可编辑。', okText: '替换', cancelText: '保留原文',
            onOk: () => { if (mounted.current) setCaption(text); resolve(); }, onCancel: () => resolve(), afterClose: () => resolve() });
        });
      } else setCaption(text);
    } catch (value) { showError(value); }
    finally { if (mounted.current) setImporting(false); }
  };
  const confirmStart = () => {
    if (busy || importing || starting) return;
    if (!runAccounts.length) { showError('没有可执行的启用账号'); return; }
    try {
      // Snapshot before the confirmation: subsequent form edits never mutate this request.
      const request = buildPublishRequest(crypto.randomUUID(), mode, ids, video?.path ?? '', caption);
      const accountSnapshot = [...runAccounts];
      Modal.confirm({ title: '确认发布视频', okText: '确认发布', cancelText: '取消', width: 620,
        content: <Descriptions column={1} bordered size="small" style={{ marginTop: 12 }}>
          <Descriptions.Item label="视频"><span style={{ overflowWrap: 'anywhere' }}>{request.videoPath}</span></Descriptions.Item>
          <Descriptions.Item label="文案"><div style={{ whiteSpace: 'pre-wrap', maxHeight: 180, overflow: 'auto' }}>{request.caption || '（空文案）'}</div></Descriptions.Item>
          <Descriptions.Item label="执行账号">{accountSnapshot.map(a => a.id).join('、')}</Descriptions.Item>
          <Descriptions.Item label="浏览器"><AccountBrowserEnvironment accounts={accountSnapshot} /></Descriptions.Item>
          <Descriptions.Item label="说明">将向上述账号真实发布同一视频，并逐账号进入本人主页核验。</Descriptions.Item>
        </Descriptions>,
        onOk: async () => {
          setStarting(true); setError(undefined);
          try { const result = await runTikTokPublish(request); setBatchId(result.batchId); message.success('发布任务已接受，可在发布记录中查看逐账号结果'); }
          catch (value) { showError(value); throw value; }
          finally { setStarting(false); }
        },
      });
    } catch (value) { showError(value); }
  };
  if (currentPlatform !== 'tiktok') return <Alert type="info" message="当前平台不支持视频发布" />;
  return <>
    <PageHeader title="发布作品" description="选择一次本地视频和文案，自动为选中账号上传、发布并在本人主页核验。" />
    <Space direction="vertical" size={24} className="full-width">
      {error ? <Alert type="error" showIcon message={error} closable onClose={() => setError(undefined)} /> : null}
      <Card title="本地视频">
        <Space direction="vertical" size={12} className="full-width">
          <Button icon={<FolderOpen size={16} />} loading={choosingVideo} onClick={() => void chooseVideo()}>{video ? '重新选择视频' : '选择本地视频'}</Button>
          {video ? <Descriptions column={1} size="small">
            <Descriptions.Item label="文件名">{video.fileName}</Descriptions.Item>
            <Descriptions.Item label="绝对路径"><Typography.Text copyable style={{ overflowWrap: 'anywhere' }}>{video.path}</Typography.Text></Descriptions.Item>
            <Descriptions.Item label="大小">{(Number(video.sizeBytes) / 1024 / 1024).toFixed(2)} MiB</Descriptions.Item>
          </Descriptions> : <Typography.Text type="secondary">支持 MP4、MOV、WebM；直接引用原文件，执行期间请勿移动、删除或修改。</Typography.Text>}
        </Space>
      </Card>
      <Card title="作品文案" extra={<Button icon={<FileText size={16} />} loading={importing} disabled={importing} onClick={() => fileInput.current?.click()}>导入 TXT / DOCX</Button>}>
        <input ref={fileInput} type="file" accept=".txt,.docx" hidden disabled={importing} onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file && !importing) void importFile(file); }} />
        <Form layout="vertical"><Form.Item label="文案" help={invalidCaption ? '文案最多 4000 个字符，且不能包含无效控制字符；已保留完整原文，请修改后发布。' : '可直接输入，或导入 UTF-8 TXT / DOCX（最大 2 MiB）后继续编辑；允许空文案。'} validateStatus={invalidCaption ? 'error' : undefined}>
          <Input.TextArea aria-label="作品文案" value={caption} onChange={event => setCaption(event.target.value)} disabled={importing} autoSize={{ minRows: 6, maxRows: 16 }} showCount={{ formatter: () => `${caption.length} / 4000` }} status={invalidCaption ? 'error' : undefined} />
        </Form.Item></Form>
      </Card>
      <Card title="执行账号" loading={loading}>
        <Space direction="vertical" size={16} className="full-width">
          <Select aria-label="账号执行范围" className="full-width" value={mode} onChange={value => { setMode(value); setIds([]); }} options={[{ value: 'all', label: `全部启用账号（${accounts.length}）` }, { value: 'single', label: '单账号' }, { value: 'selected', label: '多个账号' }]} />
          {mode !== 'all' ? <Select aria-label="选择执行账号" className="full-width" mode={mode === 'selected' ? 'multiple' : undefined} value={mode === 'single' ? ids[0] : ids} onChange={value => setIds(Array.isArray(value) ? value : [value])} options={accounts.map(a => ({ value: a.id, label: a.id }))} placeholder="选择执行账号" /> : null}
          <Typography.Text>本次执行 {runAccounts.length} 个账号，共用同一视频与文案。</Typography.Text>
          <AccountBrowserEnvironment accounts={runAccounts} />
          <Button type="primary" icon={<Play size={16} />} loading={starting} disabled={!video || invalidCaption || importing || loading || busy || !runAccounts.length} onClick={confirmStart}>开始发布</Button>
          {busy ? <Typography.Text type="secondary">已有任务正在执行或停止中，请等待结束。</Typography.Text> : null}
          {batchId ? <Typography.Text>当前批次：{batchId} · <a href="#publish-records">查看发布记录</a></Typography.Text> : null}
        </Space>
      </Card>
      <ProcessOutputPanel title="发布运行进度" />
    </Space>
  </>;
}
