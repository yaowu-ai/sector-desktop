import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Play, RefreshCw, RotateCcw, Save, Target, Upload, Users } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'

import { confirmDanger } from '../components/ConfirmDanger'
import { PageHeader } from '../components/PageHeader'
import { ProcessOutputPanel } from '../components/ProcessOutputPanel'
import { StatusTag } from '../components/StatusTag'
import { AccountBrowserEnvironment } from '../components/AccountBrowserEnvironment'
import { usePlatformContext } from '../app/PlatformContext'
import {
  loadConfig,
  loadCommentPools,
  queryTargetStats,
  queryTargetWatermarks,
  resetTargetWatermark,
  runPlatformTask,
  saveCommentPools,
  saveTargetEngagementSettings,
} from '../services/api'
import { getPlatformLabel, isExecutablePlatform } from '../services/platforms'
import type {
  Account,
  ConfigSnapshot,
  TargetAccountStats,
  TargetEngagementSettings,
  TargetHandleStats,
  TargetStatsSummary,
  TargetWatermark,
} from '../services/types'

const DEFAULT_TARGET_SETTINGS: TargetEngagementSettings = {
  enabled: false,
  handles: [],
  participants: [],
  firstRunLatestN: 1,
  maxVideosPerRun: 3,
  likeProbability: 0.8,
  commentProbability: 0.3,
  commentsFile: 'comments_brand.txt',
  follow: false,
  followProbability: 0.2,
}

interface TargetEngagementPageProps {
  hideProcessOutput?: boolean
  onDataChanged?: () => void | Promise<void>
}

export function TargetEngagementPage({ hideProcessOutput = false, onDataChanged }: TargetEngagementPageProps = {}) {
  const { currentPlatform } = usePlatformContext()
  const [form] = Form.useForm<TargetEngagementSettings>()
  const [snapshot, setSnapshot] = useState<ConfigSnapshot | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [watermarks, setWatermarks] = useState<TargetWatermark[]>([])
  const [targetStats, setTargetStats] = useState<TargetStatsSummary>({
    scope: 'all',
    label: '全部',
    byAccount: [],
    byHandle: [],
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [starting, setStarting] = useState(false)
  const [importingCommentsFile, setImportingCommentsFile] = useState(false)
  const [resettingKey, setResettingKey] = useState<string>()
  const commentsFileInputRef = useRef<HTMLInputElement>(null)

  const followEnabled = Form.useWatch('follow', form)
  const selectedParticipants = Form.useWatch('participants', form) ?? []

  const executableAccounts = useMemo(
    () => accounts.filter((account) => account.enabled && isExecutablePlatform(account.platform)),
    [accounts],
  )
  const participantOptions = useMemo(
    () =>
      accounts.map((account) => ({
        value: account.id,
        label: `${account.id} · ${getPlatformLabel(account.platform)}${account.enabled ? '' : '（停用）'}${
          isExecutablePlatform(account.platform) ? '' : '（未适配）'
        }`,
        disabled: !account.enabled || !isExecutablePlatform(account.platform),
      })),
    [accounts],
  )
  const executableParticipantAccounts = useMemo(() => {
    const selected = new Set(selectedParticipants)
    return executableAccounts.filter((account) => selected.has(account.id))
  }, [executableAccounts, selectedParticipants])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [nextSnapshot, nextWatermarks, nextStats] = await Promise.all([
        loadConfig(),
        queryTargetWatermarks({ platform: currentPlatform }),
        queryTargetStats({ scope: 'all', platform: currentPlatform }),
      ])
      const nextPlatformAccounts = nextSnapshot.accounts.filter((account) => account.platform === currentPlatform)
      const nextPlatformAccountIds = new Set(nextPlatformAccounts.map((account) => account.id))
      setSnapshot(nextSnapshot)
      setAccounts(nextPlatformAccounts)
      setWatermarks(nextWatermarks.filter((watermark) => nextPlatformAccountIds.has(watermark.ourAccount)))
      setTargetStats(filterTargetStats(nextStats, nextPlatformAccountIds))
      form.setFieldsValue(filterTargetParticipants(normalizeTargetSettings(nextSnapshot.targetEngagement), nextPlatformAccountIds))
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setLoading(false)
    }
  }, [currentPlatform, form])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const saveSettings = async () => {
    const values = normalizeTargetSettings(await form.validateFields())
    setSaving(true)
    try {
      await saveTargetEngagementSettings(values, currentPlatform)
      message.success('目标号互动配置已保存到 accounts.yaml')
      await refresh()
      await onDataChanged?.()
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setSaving(false)
    }
  }

  const confirmRunParticipants = () => {
    const settings = normalizeTargetSettings(form.getFieldsValue(true))
    if (!settings.enabled) {
      message.warning('请先启用目标号互动')
      return
    }
    if (executableParticipantAccounts.length === 0) {
      message.warning('没有可执行的参与账号')
      return
    }

    Modal.confirm({
      title: '确认立即执行目标号互动',
      okText: '确认执行',
      cancelText: '取消',
      width: 620,
      content: (
        <Descriptions size="small" column={1} bordered style={{ marginTop: 12 }}>
          <Descriptions.Item label="目标号">{settings.handles.map((handle) => `@${handle}`).join(', ')}</Descriptions.Item>
          <Descriptions.Item label="参与账号">
            {executableParticipantAccounts.map((account) => account.id).join(', ')}
          </Descriptions.Item>
          <Descriptions.Item label="浏览器环境">
            <AccountBrowserEnvironment accounts={executableParticipantAccounts} />
          </Descriptions.Item>
          <Descriptions.Item label="单目标最大视频">{settings.maxVideosPerRun}</Descriptions.Item>
          <Descriptions.Item label="点赞概率">{formatPercent(settings.likeProbability)}</Descriptions.Item>
          <Descriptions.Item label="评论概率">{formatPercent(settings.commentProbability)}</Descriptions.Item>
          <Descriptions.Item label="关注">
            {settings.follow ? `开启，概率 ${formatPercent(settings.followProbability)}` : '关闭'}
          </Descriptions.Item>
        </Descriptions>
      ),
      onOk: async () => {
        await runParticipants(executableParticipantAccounts)
      },
    })
  }

  const runParticipants = async (participants: Account[]) => {
    setStarting(true)
    try {
      const accountIds = participants.map((account) => account.id)
      const result = await runPlatformTask({
        platform: currentPlatform,
        taskType: 'target_engagement',
        accountIds,
        mode: accountIds.length === 1 ? 'single' : 'selected',
      })
      message.success(`参与账号队列已启动，PID ${result.processId ?? '-'}`)
      await refresh()
      await onDataChanged?.()
    } catch (error) {
      message.error(formatError(error))
      throw error
    } finally {
      setStarting(false)
    }
  }

  const selectCommentsFile = () => {
    commentsFileInputRef.current?.click()
  }

  const importCommentsFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) {
      return
    }

    setImportingCommentsFile(true)
    try {
      const [text, pools] = await Promise.all([file.text(), loadCommentPools()])
      const result = await saveCommentPools({
        generalText: pools.general.rawText,
        brandText: text,
      })
      form.setFieldValue('commentsFile', DEFAULT_TARGET_SETTINGS.commentsFile)
      message.success(`已导入 ${result.brand.comments.length} 条评论到品牌评论池`)
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setImportingCommentsFile(false)
    }
  }

  const confirmResetWatermark = (watermark: TargetWatermark) => {
    confirmDanger({
      title: `重置 ${watermark.ourAccount} / @${watermark.handle} 水位线`,
      content: `将删除该账号对该目标号的 ${watermark.videos} 条 target_engagements 记录，此操作不可撤销。`,
      onOk: () => {
        void resetWatermark(watermark)
      },
    })
  }

  const resetWatermark = async (watermark: TargetWatermark) => {
    const key = `${watermark.ourAccount}:${watermark.handle}`
    setResettingKey(key)
    try {
      const result = await resetTargetWatermark({
        accountId: watermark.ourAccount,
        handle: watermark.handle,
      })
      message.success(`已删除 ${result.deletedRows} 条水位线记录`)
      await refresh()
      await onDataChanged?.()
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setResettingKey(undefined)
    }
  }

  const settings = normalizeTargetSettings(snapshot?.targetEngagement)
  const runParticipantsDisabledReason = !settings.enabled
    ? '目标号互动配置未启用'
    : executableParticipantAccounts.length === 0
      ? '没有可执行的参与账号'
      : undefined

  return (
    <>
      <input
        ref={commentsFileInputRef}
        type="file"
        accept=".txt,text/plain"
        style={{ display: 'none' }}
        onChange={(event) => void importCommentsFile(event)}
      />
      <PageHeader
        title="目标号互动"
        description="按当前平台维护 target_accounts 配置，查看目标互动水位线和统计。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} onClick={() => void refresh()} loading={loading}>
              刷新
            </Button>
            <Button type="primary" icon={<Save size={16} />} onClick={() => void saveSettings()} loading={saving}>
              保存配置
            </Button>
          </Space>
        }
      />

      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={15}>
            <Card title="目标号配置">
              <Form form={form} layout="vertical" requiredMark={false} initialValues={DEFAULT_TARGET_SETTINGS}>
                <Row gutter={16}>
                  <Col xs={24} md={8}>
                    <Form.Item name="enabled" label="启用" valuePropName="checked">
                      <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={16}>
                    <Form.Item label="评论池文件">
                      <Space wrap>
                        <Typography.Text code>{DEFAULT_TARGET_SETTINGS.commentsFile}</Typography.Text>
                        <Button
                          icon={<Upload size={15} />}
                          loading={importingCommentsFile}
                          onClick={selectCommentsFile}
                        >
                          导入
                        </Button>
                        <Typography.Text type="secondary">
                          内容从评论素材页面维护；导入会覆盖品牌目标号评论池。
                        </Typography.Text>
                      </Space>
                    </Form.Item>
                  </Col>
                  <Col span={24}>
                    <Form.Item
                      name="handles"
                      label="目标号 handles"
                      rules={[
                        { required: true, message: '请至少配置一个目标号' },
                        { validator: (_, value?: string[]) => validateHandles(value) },
                      ]}
                    >
                      <Select mode="tags" tokenSeparators={[',', '\n', ' ']} placeholder="输入 handle，支持 @ 前缀" />
                    </Form.Item>
                  </Col>
                  <Col span={24}>
                    <Form.Item
                      name="participants"
                      label="参与账号"
                      rules={[{ required: true, message: '请至少选择一个参与账号' }]}
                    >
                      <Select mode="multiple" showSearch options={participantOptions} placeholder="选择可执行平台启用账号" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      name="firstRunLatestN"
                      label="首次运行处理最新视频数"
                      rules={[
                        { required: true, message: '请输入首次运行视频数' },
                        { type: 'number', min: 0, message: '必须大于等于 0' },
                      ]}
                    >
                      <InputNumber min={0} precision={0} className="full-width" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      name="maxVideosPerRun"
                      label="单次每目标最大视频数"
                      rules={[
                        { required: true, message: '请输入单次最大视频数' },
                        { type: 'number', min: 0, message: '必须大于等于 0' },
                      ]}
                    >
                      <InputNumber min={0} precision={0} className="full-width" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      name="likeProbability"
                      label="点赞概率"
                      rules={[
                        { required: true, message: '请输入点赞概率' },
                        { type: 'number', min: 0, max: 1, message: '概率必须在 0 到 1 之间' },
                      ]}
                    >
                      <InputNumber min={0} max={1} step={0.05} precision={2} className="full-width" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      name="commentProbability"
                      label="评论概率"
                      rules={[
                        { required: true, message: '请输入评论概率' },
                        { type: 'number', min: 0, max: 1, message: '概率必须在 0 到 1 之间' },
                      ]}
                    >
                      <InputNumber min={0} max={1} step={0.05} precision={2} className="full-width" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="follow" label="关注目标号" valuePropName="checked">
                      <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      name="followProbability"
                      label="关注概率"
                      rules={[
                        { required: true, message: '请输入关注概率' },
                        { type: 'number', min: 0, max: 1, message: '概率必须在 0 到 1 之间' },
                      ]}
                    >
                      <InputNumber
                        min={0}
                        max={1}
                        step={0.05}
                        precision={2}
                        className="full-width"
                        disabled={!followEnabled}
                      />
                    </Form.Item>
                  </Col>
                </Row>
              </Form>
            </Card>
          </Col>

          <Col xs={24} xl={9}>
            <Card title="立即执行" extra={<Target size={16} />}>
              <Space direction="vertical" size={14} className="full-width">
                <Descriptions size="small" column={1} bordered>
                  <Descriptions.Item label="配置状态">
                    <StatusTag status={settings.enabled ? 'ok' : 'warning'} label={settings.enabled ? '启用' : '关闭'} />
                  </Descriptions.Item>
                  <Descriptions.Item label="目标号">{settings.handles.length}</Descriptions.Item>
                  <Descriptions.Item label="参与账号">{settings.participants.length}</Descriptions.Item>
                  <Descriptions.Item label="可执行参与账号">{executableParticipantAccounts.length}</Descriptions.Item>
                  <Descriptions.Item label="参与账号浏览器">
                    <AccountBrowserEnvironment accounts={executableParticipantAccounts} emptyText="暂无可执行参与账号" />
                  </Descriptions.Item>
                  <Descriptions.Item label="评论池">
                    <Typography.Text code>{settings.commentsFile || '-'}</Typography.Text>
                  </Descriptions.Item>
                </Descriptions>
                <Tooltip title={runParticipantsDisabledReason}>
                  <span>
                    <Button
                      type="primary"
                      icon={<Play size={16} />}
                      block
                      loading={starting}
                      disabled={Boolean(runParticipantsDisabledReason)}
                      onClick={confirmRunParticipants}
                    >
                      立即执行参与账号
                    </Button>
                  </span>
                </Tooltip>
              </Space>
            </Card>
          </Col>

          <Col span={24}>
            <Card title="水位线">
              <Table
                rowKey={(row) => `${row.ourAccount}:${row.handle}`}
                columns={watermarkColumns(resettingKey, confirmResetWatermark)}
                dataSource={watermarks}
                pagination={{ pageSize: 10, showSizeChanger: true }}
              />
            </Card>
          </Col>

          <Col xs={24} xl={12}>
            <Card title="按账号统计" extra={<Users size={16} />}>
              <Table
                rowKey="accountId"
                columns={accountStatsColumns}
                dataSource={targetStats.byAccount}
                pagination={{ pageSize: 8 }}
                scroll={{ x: 760 }}
              />
            </Card>
          </Col>

          <Col xs={24} xl={12}>
            <Card title="按目标号统计" extra={<Target size={16} />}>
              <Table
                rowKey="handle"
                columns={handleStatsColumns}
                dataSource={targetStats.byHandle}
                pagination={{ pageSize: 8 }}
                scroll={{ x: 760 }}
              />
            </Card>
          </Col>
          {hideProcessOutput ? null : (
            <Col span={24}>
              <ProcessOutputPanel title="目标号任务输出" />
            </Col>
          )}
        </Row>
      </Spin>
    </>
  )
}

function watermarkColumns(
  resettingKey: string | undefined,
  onReset: (watermark: TargetWatermark) => void,
): ColumnsType<TargetWatermark> {
  return [
    { title: '执行账号', dataIndex: 'ourAccount', width: 140 },
    {
      title: '目标号',
      dataIndex: 'handle',
      width: 180,
      render: (handle: string) => <Typography.Text>@{handle}</Typography.Text>,
    },
    {
      title: '最大 video_id',
      dataIndex: 'maxVideoId',
      width: 220,
      render: (value?: string) => (value ? <Typography.Text code>{value}</Typography.Text> : '-'),
    },
    { title: '最新时间', dataIndex: 'latestTs', width: 190, render: (value?: string) => value ?? '-' },
    { title: '视频', dataIndex: 'videos', width: 80 },
    { title: '点赞', dataIndex: 'likes', width: 80 },
    { title: '评论', dataIndex: 'comments', width: 80 },
    {
      title: '操作',
      width: 120,
      render: (_, row) => (
        <Button
          danger
          icon={<RotateCcw size={15} />}
          loading={resettingKey === `${row.ourAccount}:${row.handle}`}
          onClick={() => onReset(row)}
        >
          重置
        </Button>
      ),
    },
  ]
}

const accountStatsColumns: ColumnsType<TargetAccountStats> = [
  { title: '账号', dataIndex: 'accountId', width: 140 },
  { title: '视频', dataIndex: 'videos', width: 80 },
  { title: '点赞', dataIndex: 'likes', width: 80 },
  { title: '评论', dataIndex: 'comments', width: 80 },
  { title: '关注', dataIndex: 'follows', width: 80 },
  {
    title: '目标号',
    dataIndex: 'handles',
    render: (handles: string[]) => renderTags(handles, '@'),
  },
]

const handleStatsColumns: ColumnsType<TargetHandleStats> = [
  {
    title: '目标号',
    dataIndex: 'handle',
    width: 170,
    render: (handle: string) => <Typography.Text>@{handle}</Typography.Text>,
  },
  { title: '视频', dataIndex: 'videos', width: 80 },
  { title: '点赞', dataIndex: 'likes', width: 80 },
  { title: '评论', dataIndex: 'comments', width: 80 },
  { title: '关注', dataIndex: 'follows', width: 80 },
  {
    title: '执行账号',
    dataIndex: 'accounts',
    render: (accounts: string[]) => renderTags(accounts),
  },
]

function renderTags(values: string[], prefix = '') {
  if (!values.length) {
    return '-'
  }
  return (
    <Space wrap size={4}>
      {values.map((value) => (
        <Tag key={value}>{prefix}{value}</Tag>
      ))}
    </Space>
  )
}

function normalizeTargetSettings(settings?: Partial<TargetEngagementSettings>): TargetEngagementSettings {
  return {
    enabled: Boolean(settings?.enabled ?? DEFAULT_TARGET_SETTINGS.enabled),
    handles: normalizeList(settings?.handles).map(trimAtPrefix),
    participants: normalizeList(settings?.participants),
    firstRunLatestN: normalizeInteger(settings?.firstRunLatestN, DEFAULT_TARGET_SETTINGS.firstRunLatestN),
    maxVideosPerRun: normalizeInteger(settings?.maxVideosPerRun, DEFAULT_TARGET_SETTINGS.maxVideosPerRun),
    likeProbability: Number(settings?.likeProbability ?? DEFAULT_TARGET_SETTINGS.likeProbability),
    commentProbability: Number(settings?.commentProbability ?? DEFAULT_TARGET_SETTINGS.commentProbability),
    commentsFile: DEFAULT_TARGET_SETTINGS.commentsFile,
    follow: Boolean(settings?.follow ?? DEFAULT_TARGET_SETTINGS.follow),
    followProbability: Number(settings?.followProbability ?? DEFAULT_TARGET_SETTINGS.followProbability),
  }
}

function filterTargetParticipants(settings: TargetEngagementSettings, accountIds: Set<string>) {
  return {
    ...settings,
    participants: settings.participants.filter((accountId) => accountIds.has(accountId)),
  }
}

function filterTargetStats(stats: TargetStatsSummary, accountIds: Set<string>): TargetStatsSummary {
  const byAccount = stats.byAccount.filter((row) => accountIds.has(row.accountId))
  return {
    ...stats,
    byAccount,
    byHandle: stats.byHandle
      .map((row) => ({
        ...row,
        accounts: row.accounts.filter((accountId) => accountIds.has(accountId)),
      }))
      .filter((row) => row.accounts.length > 0),
  }
}

function normalizeList(values?: string[]) {
  return Array.from(new Set((values ?? []).map((value) => value.trim()).filter(Boolean)))
}

function trimAtPrefix(value: string) {
  return value.trim().replace(/^@+/, '')
}

function normalizeInteger(value: unknown, fallback: number) {
  return Math.max(0, Math.trunc(Number(value ?? fallback)))
}

function validateHandles(values?: string[]) {
  const handles = normalizeList(values).map(trimAtPrefix)
  if (!handles.length) {
    return Promise.reject(new Error('请至少配置一个目标号'))
  }
  const invalid = handles.find(
    (handle) =>
      handle.length > 24 ||
      !handle
        .split('')
        .every((ch) => /[A-Za-z0-9_.]/.test(ch)),
  )
  return invalid
    ? Promise.reject(new Error(`目标号格式不合法：${invalid}`))
    : Promise.resolve()
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
