import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Dayjs } from 'dayjs'
import { Copy, Database, FilterX, PlayCircle, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { PageHeader } from '../components/PageHeader'
import { PlatformScopeFilter } from '../components/PlatformScopeFilter'
import {
  getSqliteStatus,
  loadConfig,
  queryActionLogs,
  queryFypVideoViews,
  queryTargetEngagements,
  queryTargetFollows,
} from '../services/api'
import type {
  Account,
  ActionLog,
  ActionLogFilter,
  FypVideoViewFilter,
  FypVideoViewRecord,
  Platform,
  TargetEngagementRecord,
  TargetFollowRecord,
  TargetRecordFilter,
  SqliteStatus,
} from '../services/types'
import type { PlatformFilterValue } from '../app/pageScope'

const { RangePicker } = DatePicker

type TimeRange = [Dayjs, Dayjs] | null

interface FilterState {
  platform: PlatformFilterValue
  accountId?: string
  action?: string
  status?: string
  hasVideoTitle?: 'true' | 'false'
  videoLiked?: 'true' | 'false'
  videoCommented?: 'true' | 'false'
  timeRange: TimeRange
}

const DEFAULT_FILTERS: FilterState = {
  platform: 'all',
  timeRange: null,
}

const COMMON_ACTIONS = [
  'fyp_browse',
  'like',
  'follow',
  'comment',
  'target_engagement',
  'target_follow',
  'skip',
]

const COMMON_STATUSES = ['ok', 'error', 'skip', 'failed', 'stopped']

export function ExecutionRecordPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [sqliteStatus, setSqliteStatus] = useState<SqliteStatus | null>(null)
  const [actionLogs, setActionLogs] = useState<ActionLog[]>([])
  const [fypVideoViews, setFypVideoViews] = useState<FypVideoViewRecord[]>([])
  const [targetEngagements, setTargetEngagements] = useState<TargetEngagementRecord[]>([])
  const [targetFollows, setTargetFollows] = useState<TargetFollowRecord[]>([])
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)
  const [loading, setLoading] = useState(true)

  const actionOptions = useMemo(
    () => toSelectOptions([...COMMON_ACTIONS, ...actionLogs.map((row) => row.action)]),
    [actionLogs],
  )
  const statusOptions = useMemo(
    () => toSelectOptions([...COMMON_STATUSES, ...actionLogs.map((row) => row.status)]),
    [actionLogs],
  )
  const accountPlatformMap = useMemo(
    () => new Map(accounts.map((account) => [account.id, account.platform])),
    [accounts],
  )
  const accountOptions = useMemo(
    () =>
      accounts.filter((account) => accountMatchesPlatform(account, filters.platform)).map((account) => ({
        value: account.id,
        label: account.id,
      })),
    [accounts, filters.platform],
  )
  const filteredActionLogs = useMemo(
    () =>
      actionLogs.filter((row) =>
        accountIdMatchesPlatform(row.accountId, filters.platform, accountPlatformMap),
      ),
    [accountPlatformMap, actionLogs, filters.platform],
  )
  const filteredTargetEngagements = useMemo(
    () =>
      targetEngagements.filter((row) =>
        accountIdMatchesPlatform(row.ourAccount, filters.platform, accountPlatformMap),
      ),
    [accountPlatformMap, filters.platform, targetEngagements],
  )
  const filteredTargetFollows = useMemo(
    () =>
      targetFollows.filter((row) =>
        accountIdMatchesPlatform(row.ourAccount, filters.platform, accountPlatformMap),
      ),
    [accountPlatformMap, filters.platform, targetFollows],
  )

  const refresh = async (sourceFilters = filters) => {
    setLoading(true)
    try {
      const snapshot = await loadConfig()
      const actionFilter = toActionFilter(sourceFilters)
      const fypVideoFilter = toFypVideoViewFilter(sourceFilters)
      const targetFilter = toTargetFilter(sourceFilters)
      const [sqlite, nextActionLogs, nextFypVideoViews, nextTargetEngagements, nextTargetFollows] = await Promise.all([
        getSqliteStatus(),
        queryActionLogs(actionFilter),
        queryFypVideoViews(fypVideoFilter),
        queryTargetEngagements(targetFilter),
        queryTargetFollows(targetFilter),
      ])
      setAccounts(snapshot.accounts)
      setSqliteStatus(sqlite)
      setActionLogs(nextActionLogs)
      setFypVideoViews(nextFypVideoViews)
      setTargetEngagements(nextTargetEngagements)
      setTargetFollows(nextTargetFollows)
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh(DEFAULT_FILTERS)
  }, [])

  const updateFilter = <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    setFilters((current) => ({
      ...current,
      [key]: value,
      ...(key === 'platform' ? { accountId: undefined } : {}),
    }))
  }

  const resetFilters = () => {
    setFilters(DEFAULT_FILTERS)
    void refresh(DEFAULT_FILTERS)
  }

  const recordStoreStatus = getRecordStoreStatus(sqliteStatus)
  const goToTasks = () => {
    window.location.hash = 'tasks'
  }
  const emptyText = (recordType: string) => (
    <RecordEmptyText
      recordType={recordType}
      initialized={sqliteStatus?.exists !== false}
      loading={loading}
      onRefresh={() => void refresh()}
      onGoToTasks={goToTasks}
    />
  )

  return (
    <>
      <PageHeader
        title="执行记录"
        description="查询养号动作、目标互动和目标关注记录。"
        extra={
          <Space>
            <Button icon={<FilterX size={16} />} onClick={resetFilters}>
              清空筛选
            </Button>
            <Button type="primary" icon={<RefreshCw size={16} />} loading={loading} onClick={() => void refresh()}>
              查询
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col span={24}>
          {sqliteStatus && !sqliteStatus.exists ? (
            <Alert
              showIcon
              type="info"
              message="未初始化"
              description="尚未生成执行记录，首次运行养号任务后会自动创建记录库。"
              action={
                <Space>
                  <Button size="small" icon={<PlayCircle size={14} />} onClick={goToTasks}>
                    去运行任务
                  </Button>
                  <Button size="small" icon={<RefreshCw size={14} />} loading={loading} onClick={() => void refresh()}>
                    刷新/检查数据源
                  </Button>
                </Space>
              }
              style={{ marginBottom: 16 }}
            />
          ) : null}
          <Card>
            <Space direction="vertical" size={14} className="full-width">
              <Space wrap size={12}>
                <PlatformScopeFilter
                  value={filters.platform}
                  onChange={(value) => updateFilter('platform', value)}
                />
                <Select
                  allowClear
                  showSearch
                  placeholder="账号"
                  value={filters.accountId}
                  options={accountOptions}
                  style={{ width: 180 }}
                  onChange={(value) => updateFilter('accountId', value)}
                />
                <Select
                  allowClear
                  showSearch
                  placeholder="任务类型 / 动作"
                  value={filters.action}
                  options={actionOptions}
                  style={{ width: 190 }}
                  onChange={(value) => updateFilter('action', value)}
                />
                <Select
                  allowClear
                  showSearch
                  placeholder="状态"
                  value={filters.status}
                  options={statusOptions}
                  style={{ width: 150 }}
                  onChange={(value) => updateFilter('status', value)}
                />
                <Select
                  allowClear
                  placeholder="视频标题"
                  value={filters.hasVideoTitle}
                  options={[
                    { value: 'true', label: '有标题' },
                    { value: 'false', label: '无标题' },
                  ]}
                  style={{ width: 130 }}
                  onChange={(value) => updateFilter('hasVideoTitle', value)}
                />
                <Select
                  allowClear
                  placeholder="视频点赞"
                  value={filters.videoLiked}
                  options={[
                    { value: 'true', label: '已点赞' },
                    { value: 'false', label: '未点赞' },
                  ]}
                  style={{ width: 130 }}
                  onChange={(value) => updateFilter('videoLiked', value)}
                />
                <Select
                  allowClear
                  placeholder="视频评论"
                  value={filters.videoCommented}
                  options={[
                    { value: 'true', label: '已评论' },
                    { value: 'false', label: '未评论' },
                  ]}
                  style={{ width: 130 }}
                  onChange={(value) => updateFilter('videoCommented', value)}
                />
                <RangePicker
                  showTime
                  value={filters.timeRange}
                  onChange={(value) => updateFilter('timeRange', value as TimeRange)}
                />
              </Space>
              <Space size={8}>
                <Database size={15} />
                <Typography.Text type="secondary">数据源</Typography.Text>
                <Typography.Text>本机记录库</Typography.Text>
                <Tag color={recordStoreStatus.color}>{recordStoreStatus.label}</Tag>
              </Space>
            </Space>
          </Card>
        </Col>

        <Col span={24}>
          <Card>
            <Tabs
              items={[
                {
                  key: 'action-log',
                  label: `动作记录 ${filteredActionLogs.length}`,
                  children: (
                    <Table
                      rowKey="id"
                      loading={loading}
                      columns={actionLogColumns}
                      dataSource={filteredActionLogs}
                      locale={{ emptyText: emptyText('执行记录') }}
                      pagination={{ pageSize: 12, showSizeChanger: true }}
                      scroll={{ x: 1120 }}
                    />
                  ),
                },
                {
                  key: 'fyp-video-views',
                  label: `FYP 视频明细 ${fypVideoViews.length}`,
                  children: (
                    <Table
                      rowKey="id"
                      loading={loading}
                      columns={fypVideoViewColumns}
                      dataSource={fypVideoViews}
                      locale={{ emptyText: emptyText('FYP 视频明细') }}
                      pagination={{ pageSize: 12, showSizeChanger: true }}
                      scroll={{ x: 1520 }}
                    />
                  ),
                },
                {
                  key: 'target-engagements',
                  label: `目标互动 ${filteredTargetEngagements.length}`,
                  children: (
                    <Table
                      rowKey={(row) => `${row.ourAccount}:${row.handle}:${row.videoId}:${row.ts}`}
                      loading={loading}
                      columns={targetEngagementColumns}
                      dataSource={filteredTargetEngagements}
                      locale={{ emptyText: emptyText('目标互动记录') }}
                      pagination={{ pageSize: 12, showSizeChanger: true }}
                      scroll={{ x: 980 }}
                    />
                  ),
                },
                {
                  key: 'target-follows',
                  label: `目标关注 ${filteredTargetFollows.length}`,
                  children: (
                    <Table
                      rowKey={(row) => `${row.ourAccount}:${row.handle}:${row.ts}`}
                      loading={loading}
                      columns={targetFollowColumns}
                      dataSource={filteredTargetFollows}
                      locale={{ emptyText: emptyText('目标关注记录') }}
                      pagination={{ pageSize: 12, showSizeChanger: true }}
                      scroll={{ x: 760 }}
                    />
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </>
  )
}

function RecordEmptyText({
  recordType,
  initialized,
  loading,
  onRefresh,
  onGoToTasks,
}: {
  recordType: string
  initialized: boolean
  loading: boolean
  onRefresh: () => void
  onGoToTasks: () => void
}) {
  const title = initialized ? `尚未生成${recordType}` : '未初始化'
  const description =
    recordType === 'FYP 视频明细'
      ? '首次运行开启视频信息采集后的养号任务后会生成记录。'
      : '首次运行养号任务后会自动创建记录库。'

  return (
    <Empty
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description={<EmptyDescription title={title} description={description} />}
    >
      <Space>
        <Button size="small" icon={<PlayCircle size={14} />} onClick={onGoToTasks}>
          去运行任务
        </Button>
        <Button size="small" icon={<RefreshCw size={14} />} loading={loading} onClick={onRefresh}>
          刷新/检查数据源
        </Button>
      </Space>
    </Empty>
  )
}

function EmptyDescription({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <Typography.Text strong>{title}</Typography.Text>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        {description}
      </Typography.Paragraph>
    </div>
  )
}

const actionLogColumns: ColumnsType<ActionLog> = [
  { title: '时间', dataIndex: 'ts', width: 190, sorter: (a, b) => a.ts.localeCompare(b.ts) },
  { title: '账号', dataIndex: 'accountId', width: 150 },
  {
    title: '动作',
    dataIndex: 'action',
    width: 170,
    render: (action: string) => <Typography.Text code>{action}</Typography.Text>,
  },
  {
    title: '状态',
    dataIndex: 'status',
    width: 110,
    render: (status: string) => <Tag color={statusColor(status)}>{status || '-'}</Tag>,
  },
  {
    title: '详情',
    dataIndex: 'detail',
    render: (detail: string) => (
      <Space size={8} align="start" className="full-width">
        <Typography.Paragraph
          style={{ marginBottom: 0, maxWidth: 620, whiteSpace: 'pre-wrap' }}
          ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
        >
          {detail || '-'}
        </Typography.Paragraph>
        <Tooltip title="复制详情">
          <Button
            size="small"
            icon={<Copy size={14} />}
            disabled={!detail}
            onClick={() => void copyText(detail)}
          />
        </Tooltip>
      </Space>
    ),
  },
]

const fypVideoViewColumns: ColumnsType<FypVideoViewRecord> = [
  {
    title: '时间',
    dataIndex: 'collectedAt',
    width: 190,
    sorter: (a, b) => a.collectedAt.localeCompare(b.collectedAt),
  },
  { title: '账号', dataIndex: 'accountId', width: 140 },
  { title: '序号', dataIndex: 'videoIndex', width: 80, sorter: (a, b) => a.videoIndex - b.videoIndex },
  {
    title: '作者',
    width: 180,
    render: (_, row) => {
      const handle = row.authorHandle ? `@${row.authorHandle}` : ''
      const label = row.authorName || handle
      return label ? (
        <Space direction="vertical" size={0}>
          <Typography.Text>{label}</Typography.Text>
          {row.authorName && handle ? <Typography.Text type="secondary">{handle}</Typography.Text> : null}
        </Space>
      ) : (
        '-'
      )
    },
  },
  {
    title: '标题 / 描述',
    width: 360,
    render: (_, row) => {
      const primary = row.title || row.description
      return (
        <Space size={8} align="start" className="full-width">
          <Typography.Paragraph
            style={{ marginBottom: 0, maxWidth: 300, whiteSpace: 'pre-wrap' }}
            ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
            type={primary ? undefined : 'secondary'}
          >
            {primary || '未采集到标题'}
          </Typography.Paragraph>
          <Tooltip title="复制标题">
            <Button
              size="small"
              icon={<Copy size={14} />}
              disabled={!primary}
              onClick={() => void copyText(primary, '标题已复制')}
            />
          </Tooltip>
        </Space>
      )
    },
  },
  {
    title: '视频ID',
    dataIndex: 'videoId',
    width: 230,
    render: (videoId: string) => (videoId ? <Typography.Text code>{videoId}</Typography.Text> : '-'),
  },
  {
    title: '观看',
    dataIndex: 'watchSeconds',
    width: 90,
    render: (value?: number) => (typeof value === 'number' ? `${value.toFixed(1)}s` : '-'),
  },
  {
    title: '点赞',
    dataIndex: 'liked',
    width: 90,
    render: (liked: boolean) => <BooleanTag value={liked} />,
  },
  {
    title: '关注',
    dataIndex: 'followed',
    width: 90,
    render: (followed: boolean) => <BooleanTag value={followed} />,
  },
  {
    title: '评论',
    dataIndex: 'commented',
    width: 90,
    render: (commented: boolean) => <BooleanTag value={commented} />,
  },
  {
    title: '采集',
    dataIndex: 'captureStatus',
    width: 130,
    render: (status: string, row) => (
      <Tooltip title={row.captureError || row.rawSource || status}>
        <Tag color={captureStatusColor(status)}>{captureStatusLabel(status)}</Tag>
      </Tooltip>
    ),
  },
  {
    title: '操作',
    width: 130,
    render: (_, row) => {
      const hasVideoUrl = Boolean(row.videoUrl)
      return (
        <Space size={8}>
          <Tooltip title={hasVideoUrl ? '复制视频链接' : '未获取链接'}>
            <Button
              size="small"
              icon={<Copy size={14} />}
              disabled={!hasVideoUrl}
              onClick={() => void copyText(row.videoUrl, '视频链接已复制')}
            />
          </Tooltip>
          {hasVideoUrl ? null : <Typography.Text type="secondary">未获取链接</Typography.Text>}
        </Space>
      )
    },
  },
]

const targetEngagementColumns: ColumnsType<TargetEngagementRecord> = [
  { title: '时间', dataIndex: 'ts', width: 190, sorter: (a, b) => a.ts.localeCompare(b.ts) },
  { title: '执行账号', dataIndex: 'ourAccount', width: 150 },
  {
    title: '目标号',
    dataIndex: 'handle',
    width: 180,
    render: (handle: string) => <Typography.Text>@{handle}</Typography.Text>,
  },
  {
    title: 'video_id',
    dataIndex: 'videoId',
    width: 260,
    render: (videoId: string) => (videoId ? <Typography.Text code>{videoId}</Typography.Text> : '-'),
  },
  {
    title: 'liked',
    dataIndex: 'liked',
    width: 100,
    render: (liked: boolean) => <BooleanTag value={liked} />,
  },
  {
    title: 'commented',
    dataIndex: 'commented',
    width: 120,
    render: (commented: boolean) => <BooleanTag value={commented} />,
  },
]

const targetFollowColumns: ColumnsType<TargetFollowRecord> = [
  { title: '时间', dataIndex: 'ts', width: 190, sorter: (a, b) => a.ts.localeCompare(b.ts) },
  { title: '执行账号', dataIndex: 'ourAccount', width: 150 },
  {
    title: '目标号',
    dataIndex: 'handle',
    width: 180,
    render: (handle: string) => <Typography.Text>@{handle}</Typography.Text>,
  },
  {
    title: 'followed',
    dataIndex: 'followed',
    width: 120,
    render: (followed: boolean) => <BooleanTag value={followed} />,
  },
]

function BooleanTag({ value }: { value: boolean }) {
  return <Tag color={value ? 'green' : 'default'}>{value ? '是' : '否'}</Tag>
}

function toActionFilter(filters: FilterState): ActionLogFilter {
  const [startTs, endTs] = toTimeBounds(filters.timeRange)
  return compactFilter({
    platform: filters.platform,
    accountId: filters.accountId,
    action: filters.action,
    status: filters.status,
    startTs,
    endTs,
    limit: 500,
  })
}

function toFypVideoViewFilter(filters: FilterState): FypVideoViewFilter {
  const [startTs, endTs] = toTimeBounds(filters.timeRange)
  return compactFilter({
    platform: filters.platform,
    accountId: filters.accountId,
    startTs,
    endTs,
    hasTitle: toOptionalBoolean(filters.hasVideoTitle),
    liked: toOptionalBoolean(filters.videoLiked),
    commented: toOptionalBoolean(filters.videoCommented),
    limit: 500,
  })
}

function toTargetFilter(filters: FilterState): TargetRecordFilter {
  const [startTs, endTs] = toTimeBounds(filters.timeRange)
  return compactFilter({
    platform: filters.platform,
    accountId: filters.accountId,
    startTs,
    endTs,
    limit: 500,
  })
}

function toOptionalBoolean(value?: 'true' | 'false') {
  if (value === 'true') {
    return true
  }
  if (value === 'false') {
    return false
  }
  return undefined
}

function toTimeBounds(timeRange: TimeRange) {
  if (!timeRange) {
    return [undefined, undefined] as const
  }
  return [
    timeRange[0].format('YYYY-MM-DDTHH:mm:ss'),
    timeRange[1].format('YYYY-MM-DDTHH:mm:ss'),
  ] as const
}

function compactFilter<T extends Record<string, unknown>>(filter: T): T {
  return Object.fromEntries(
    Object.entries(filter).filter(([, value]) => value !== undefined && value !== ''),
  ) as T
}

function toSelectOptions(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort().map((value) => ({
    value,
    label: value,
  }))
}

function accountMatchesPlatform(account: { platform: Platform }, platformFilter: PlatformFilterValue) {
  return platformFilter === 'all' || account.platform === platformFilter
}

function accountIdMatchesPlatform(
  accountId: string,
  platformFilter: PlatformFilterValue,
  accountPlatformMap: Map<string, Platform>,
) {
  if (platformFilter === 'all') {
    return true
  }
  return inferPlatform(accountId, accountPlatformMap) === platformFilter
}

function inferPlatform(accountId: string, accountPlatformMap: Map<string, Platform>) {
  return accountPlatformMap.get(accountId) ?? (accountId.split('_')[0] as Platform | undefined)
}

function getRecordStoreStatus(status: SqliteStatus | null) {
  if (!status) {
    return { label: '检测中', color: 'default' }
  }
  if (!status.exists) {
    return { label: '未初始化', color: 'gold' }
  }
  if (status.actionLog && status.targetEngagements && status.targetFollows) {
    return { label: '已就绪', color: 'green' }
  }
  return { label: '读取异常', color: 'red' }
}

function statusColor(status: string) {
  const normalized = status.toLowerCase()
  if (normalized === 'ok' || normalized === 'success') {
    return 'green'
  }
  if (normalized === 'error' || normalized === 'fail' || normalized === 'failed') {
    return 'red'
  }
  if (normalized === 'skip' || normalized === 'stopped') {
    return 'gold'
  }
  return 'default'
}

function captureStatusColor(status: string) {
  const normalized = status.toLowerCase()
  if (normalized === 'ok') {
    return 'green'
  }
  if (normalized === 'partial') {
    return 'gold'
  }
  if (normalized === 'failed' || normalized === 'error') {
    return 'red'
  }
  if (normalized === 'disabled') {
    return 'default'
  }
  return 'blue'
}

function captureStatusLabel(status: string) {
  const normalized = status.toLowerCase()
  if (normalized === 'ok') {
    return '已采集'
  }
  if (normalized === 'partial') {
    return '部分采集'
  }
  if (normalized === 'failed' || normalized === 'error') {
    return '采集失败'
  }
  if (normalized === 'disabled') {
    return '未开启'
  }
  return status || '-'
}

async function copyText(text: string, successMessage = '详情已复制') {
  try {
    await navigator.clipboard.writeText(text)
    message.success(successMessage)
  } catch (error) {
    message.error(formatError(error))
  }
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
