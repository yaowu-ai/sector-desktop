import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  InputNumber,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Dayjs } from 'dayjs'
import { BarChart3, Database, Download, RefreshCw, Target, Users } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { useDesktopAuth } from '../app/DesktopAuthContext'
import { PageHeader } from '../components/PageHeader'
import { PlatformScopeFilter } from '../components/PlatformScopeFilter'
import { getSqliteStatus, loadConfig, queryFypStats, queryTargetStats } from '../services/api'
import { readDesktopLicenseLimits } from '../services/desktopApi'
import type {
  Account,
  FypAccountStats,
  FypStatsSummary,
  Platform,
  StatsScope,
  StatsScopeRequest,
  SqliteStatus,
  TargetAccountStats,
  TargetHandleStats,
  TargetStatsSummary,
} from '../services/types'
import type { PlatformFilterValue } from '../app/pageScope'

const { RangePicker } = DatePicker

type TimeRange = [Dayjs, Dayjs] | null

interface FilterState {
  platform: PlatformFilterValue
  accountId?: string
  taskType?: 'fyp' | 'target'
  scope: StatsScope
  days: number
  timeRange: TimeRange
}

const DEFAULT_FILTERS: FilterState = {
  platform: 'all',
  scope: 'all',
  days: 7,
  timeRange: null,
}

const EMPTY_FYP_STATS: FypStatsSummary = {
  scope: 'all',
  label: '全部',
  byAccount: [],
  total: {
    accounts: 0,
    ok: 0,
    err: 0,
    skip: 0,
    videos: 0,
    likes: 0,
    follows: 0,
    comments: 0,
  },
}

const EMPTY_TARGET_STATS: TargetStatsSummary = {
  scope: 'all',
  label: '全部',
  byAccount: [],
  byHandle: [],
}

export function StatsPage() {
  const { license } = useDesktopAuth()
  const licenseLimits = readDesktopLicenseLimits(license)
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [sqliteStatus, setSqliteStatus] = useState<SqliteStatus | null>(null)
  const [fypStats, setFypStats] = useState<FypStatsSummary>(EMPTY_FYP_STATS)
  const [targetStats, setTargetStats] = useState<TargetStatsSummary>(EMPTY_TARGET_STATS)
  const [loading, setLoading] = useState(true)

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
  const displayedFypStats = useMemo(
    () => filterFypStats(fypStats, filters, accountPlatformMap),
    [accountPlatformMap, filters, fypStats],
  )
  const displayedTargetStats = useMemo(
    () => filterTargetStats(targetStats, filters, accountPlatformMap),
    [accountPlatformMap, filters, targetStats],
  )
  const targetTotal = useMemo(
    () => summarizeTargetAccounts(displayedTargetStats.byAccount),
    [displayedTargetStats.byAccount],
  )

  const refresh = async (sourceFilters = filters) => {
    const request = toScopeRequest(sourceFilters)
    if (sourceFilters.scope === 'custom' && (!request.startTs || !request.endTs)) {
      message.warning('请选择自定义时间范围')
      return
    }

    setLoading(true)
    try {
      const [snapshot, sqlite, nextFypStats, nextTargetStats] = await Promise.all([
        loadConfig(),
        getSqliteStatus(),
        queryFypStats(request),
        queryTargetStats(request),
      ])
      setAccounts(snapshot.accounts)
      setSqliteStatus(sqlite)
      setFypStats(nextFypStats)
      setTargetStats(nextTargetStats)
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

  const exportCsv = () => {
    if (!licenseLimits.exportCsv) {
      message.warning('当前套餐不支持 CSV 导出')
      return
    }
    const rows = buildCsvRows(displayedFypStats, displayedTargetStats)
    if (rows.length === 0) {
      message.warning('当前筛选范围没有可导出的统计')
      return
    }
    downloadCsv(`account-matrix-stats-${fypStats.scope}-${timestampForFile()}.csv`, rows)
  }

  return (
    <>
      <PageHeader
        title="统计报表"
        description="汇总普通养号和目标号互动统计。"
        extra={
          <Space>
            <Button icon={<Download size={16} />} onClick={exportCsv} disabled={loading || !licenseLimits.exportCsv}>
              导出 CSV
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
              message="统计记录库尚未初始化"
              description="首次运行养号任务后会自动生成统计记录；当前暂无数据。"
              style={{ marginBottom: 16 }}
            />
          ) : null}
          <Card>
            <Space direction="vertical" size={14} className="full-width">
              <Space wrap size={12}>
                <Segmented
                  value={filters.scope}
                  options={[
                    { label: '全部', value: 'all' },
                    { label: '今日', value: 'today' },
                    { label: '最近 N 天', value: 'recent_days' },
                    { label: '自定义', value: 'custom' },
                  ]}
                  onChange={(value) => updateFilter('scope', value as StatsScope)}
                />
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
                  placeholder="任务类型"
                  value={filters.taskType}
                  options={[
                    { value: 'fyp', label: '养号' },
                    { value: 'target', label: '目标互动' },
                  ]}
                  style={{ width: 150 }}
                  onChange={(value) => updateFilter('taskType', value)}
                />
                <InputNumber
                  min={1}
                  max={365}
                  precision={0}
                  addonBefore="最近"
                  addonAfter="天"
                  value={filters.days}
                  disabled={filters.scope !== 'recent_days'}
                  onChange={(value) => updateFilter('days', Number(value ?? 7))}
                />
                <RangePicker
                  showTime
                  value={filters.timeRange}
                  disabled={filters.scope !== 'custom'}
                  onChange={(value) => updateFilter('timeRange', value as TimeRange)}
                />
                <Tag color="blue">{displayedFypStats.label}</Tag>
              </Space>
              <Space size={8}>
                <Database size={15} />
                <Typography.Text type="secondary">数据源</Typography.Text>
                <Typography.Text>本机统计库</Typography.Text>
                <Tag color={getStatsStoreStatus(sqliteStatus).color}>{getStatsStoreStatus(sqliteStatus).label}</Tag>
              </Space>
            </Space>
          </Card>
        </Col>

        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic title="账号数" value={displayedFypStats.total.accounts} prefix={<Users size={16} />} />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic title="OK" value={displayedFypStats.total.ok} valueStyle={{ color: '#1677ff' }} />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic title="ERR" value={displayedFypStats.total.err} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic title="SKIP" value={displayedFypStats.total.skip} valueStyle={{ color: '#d48806' }} />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic title="普通视频" value={displayedFypStats.total.videos} prefix={<BarChart3 size={16} />} />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic title="目标视频" value={targetTotal.videos} prefix={<Target size={16} />} />
          </Card>
        </Col>

        <Col span={24}>
          <Card title="普通养号统计">
            <Table
              rowKey="accountId"
              loading={loading}
              columns={fypColumns}
              dataSource={displayedFypStats.byAccount}
              pagination={{ pageSize: 12, showSizeChanger: true }}
              scroll={{ x: 920 }}
              summary={() => (
                <Table.Summary fixed>
                  <Table.Summary.Row>
                    <Table.Summary.Cell index={0}>Total</Table.Summary.Cell>
                    <Table.Summary.Cell index={1}>{displayedFypStats.total.ok}</Table.Summary.Cell>
                    <Table.Summary.Cell index={2}>{displayedFypStats.total.err}</Table.Summary.Cell>
                    <Table.Summary.Cell index={3}>{displayedFypStats.total.skip}</Table.Summary.Cell>
                    <Table.Summary.Cell index={4}>{displayedFypStats.total.videos}</Table.Summary.Cell>
                    <Table.Summary.Cell index={5}>{displayedFypStats.total.likes}</Table.Summary.Cell>
                    <Table.Summary.Cell index={6}>{displayedFypStats.total.follows}</Table.Summary.Cell>
                    <Table.Summary.Cell index={7}>{displayedFypStats.total.comments}</Table.Summary.Cell>
                  </Table.Summary.Row>
                </Table.Summary>
              )}
            />
          </Card>
        </Col>

        <Col xs={24} xl={12}>
          <Card title="目标号按账号统计">
            <Table
              rowKey="accountId"
              loading={loading}
              columns={targetAccountColumns}
              dataSource={displayedTargetStats.byAccount}
              pagination={{ pageSize: 8, showSizeChanger: true }}
              scroll={{ x: 760 }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={12}>
          <Card title="目标号按目标号统计">
            <Table
              rowKey="handle"
              loading={loading}
              columns={targetHandleColumns}
              dataSource={displayedTargetStats.byHandle}
              pagination={{ pageSize: 8, showSizeChanger: true }}
              scroll={{ x: 760 }}
            />
          </Card>
        </Col>
      </Row>
    </>
  )
}

const fypColumns: ColumnsType<FypAccountStats> = [
  { title: '账号', dataIndex: 'accountId', width: 160 },
  { title: 'OK', dataIndex: 'ok', width: 90, sorter: (a, b) => a.ok - b.ok },
  { title: 'ERR', dataIndex: 'err', width: 90, sorter: (a, b) => a.err - b.err },
  { title: 'SKIP', dataIndex: 'skip', width: 90, sorter: (a, b) => a.skip - b.skip },
  { title: '视频', dataIndex: 'videos', width: 110, sorter: (a, b) => a.videos - b.videos },
  { title: '点赞', dataIndex: 'likes', width: 110, sorter: (a, b) => a.likes - b.likes },
  { title: '关注', dataIndex: 'follows', width: 110, sorter: (a, b) => a.follows - b.follows },
  { title: '评论', dataIndex: 'comments', width: 110, sorter: (a, b) => a.comments - b.comments },
]

const targetAccountColumns: ColumnsType<TargetAccountStats> = [
  { title: '执行账号', dataIndex: 'accountId', width: 150 },
  { title: '视频', dataIndex: 'videos', width: 90, sorter: (a, b) => a.videos - b.videos },
  { title: '点赞', dataIndex: 'likes', width: 90, sorter: (a, b) => a.likes - b.likes },
  { title: '评论', dataIndex: 'comments', width: 90, sorter: (a, b) => a.comments - b.comments },
  { title: '关注', dataIndex: 'follows', width: 90, sorter: (a, b) => a.follows - b.follows },
  {
    title: '目标号',
    dataIndex: 'handles',
    render: (handles: string[]) => renderTags(handles, '@'),
  },
]

const targetHandleColumns: ColumnsType<TargetHandleStats> = [
  {
    title: '目标号',
    dataIndex: 'handle',
    width: 160,
    render: (handle: string) => <Typography.Text>@{handle}</Typography.Text>,
  },
  { title: '视频', dataIndex: 'videos', width: 90, sorter: (a, b) => a.videos - b.videos },
  { title: '点赞', dataIndex: 'likes', width: 90, sorter: (a, b) => a.likes - b.likes },
  { title: '评论', dataIndex: 'comments', width: 90, sorter: (a, b) => a.comments - b.comments },
  { title: '关注', dataIndex: 'follows', width: 90, sorter: (a, b) => a.follows - b.follows },
  {
    title: '执行账号',
    dataIndex: 'accounts',
    render: (accounts: string[]) => renderTags(accounts),
  },
]

function toScopeRequest(filters: FilterState): StatsScopeRequest {
  if (filters.scope === 'recent_days') {
    return {
      scope: filters.scope,
      platform: filters.platform,
      accountId: filters.accountId,
      days: Math.trunc(filters.days || 7),
    }
  }
  if (filters.scope === 'custom') {
    const [startTs, endTs] = toTimeBounds(filters.timeRange)
    return {
      scope: filters.scope,
      platform: filters.platform,
      accountId: filters.accountId,
      startTs,
      endTs,
    }
  }
  return {
    scope: filters.scope,
    platform: filters.platform,
    accountId: filters.accountId,
  }
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

function summarizeTargetAccounts(rows: TargetAccountStats[]) {
  return rows.reduce(
    (total, row) => ({
      videos: total.videos + row.videos,
      likes: total.likes + row.likes,
      comments: total.comments + row.comments,
      follows: total.follows + row.follows,
    }),
    { videos: 0, likes: 0, comments: 0, follows: 0 },
  )
}

function filterFypStats(
  stats: FypStatsSummary,
  filters: FilterState,
  accountPlatformMap: Map<string, Platform>,
): FypStatsSummary {
  if (filters.taskType === 'target') {
    return { ...EMPTY_FYP_STATS, scope: stats.scope, label: stats.label }
  }

  const byAccount = stats.byAccount.filter(
    (row) =>
      accountIdMatchesPlatform(row.accountId, filters.platform, accountPlatformMap) &&
      (!filters.accountId || row.accountId === filters.accountId),
  )
  const total = byAccount.reduce(
    (sum, row) => ({
      accounts: sum.accounts + 1,
      ok: sum.ok + row.ok,
      err: sum.err + row.err,
      skip: sum.skip + row.skip,
      videos: sum.videos + row.videos,
      likes: sum.likes + row.likes,
      follows: sum.follows + row.follows,
      comments: sum.comments + row.comments,
    }),
    EMPTY_FYP_STATS.total,
  )

  return {
    ...stats,
    byAccount,
    total,
  }
}

function filterTargetStats(
  stats: TargetStatsSummary,
  filters: FilterState,
  accountPlatformMap: Map<string, Platform>,
): TargetStatsSummary {
  if (filters.taskType === 'fyp') {
    return { ...EMPTY_TARGET_STATS, scope: stats.scope, label: stats.label }
  }

  const byAccount = stats.byAccount.filter(
    (row) =>
      accountIdMatchesPlatform(row.accountId, filters.platform, accountPlatformMap) &&
      (!filters.accountId || row.accountId === filters.accountId),
  )
  const visibleAccountIds = new Set(byAccount.map((row) => row.accountId))
  const byHandle = stats.byHandle
    .map((row) => ({
      ...row,
      accounts: row.accounts.filter((accountId) => visibleAccountIds.has(accountId)),
    }))
    .filter((row) => row.accounts.length > 0)

  return {
    ...stats,
    byAccount,
    byHandle,
  }
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

function getStatsStoreStatus(status: SqliteStatus | null) {
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

function renderTags(values: string[], prefix = '') {
  if (!values.length) {
    return '-'
  }
  return (
    <Space wrap size={4}>
      {values.map((value) => (
        <Tag key={value}>
          {prefix}
          {value}
        </Tag>
      ))}
    </Space>
  )
}

function buildCsvRows(fypStats: FypStatsSummary, targetStats: TargetStatsSummary) {
  const rows: string[][] = [
    ['category', 'key', 'relatedCount', 'ok', 'err', 'skip', 'videos', 'likes', 'follows', 'comments', 'related'],
  ]

  for (const row of fypStats.byAccount) {
    rows.push([
      'fyp_by_account',
      row.accountId,
      '',
      String(row.ok),
      String(row.err),
      String(row.skip),
      String(row.videos),
      String(row.likes),
      String(row.follows),
      String(row.comments),
      '',
    ])
  }

  for (const row of targetStats.byAccount) {
    rows.push([
      'target_by_account',
      row.accountId,
      String(row.handles.length),
      '',
      '',
      '',
      String(row.videos),
      String(row.likes),
      String(row.follows),
      String(row.comments),
      row.handles.map((handle) => `@${handle}`).join(' '),
    ])
  }

  for (const row of targetStats.byHandle) {
    rows.push([
      'target_by_handle',
      `@${row.handle}`,
      String(row.accounts.length),
      '',
      '',
      '',
      String(row.videos),
      String(row.likes),
      String(row.follows),
      String(row.comments),
      row.accounts.join(' '),
    ])
  }

  return rows.length > 1 ? rows : []
}

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows.map((row) => row.map(escapeCsvCell).join(',')).join('\r\n')
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function escapeCsvCell(value: string) {
  if (/[",\r\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`
  }
  return value
}

function timestampForFile() {
  return new Date().toISOString().replace(/[:.]/g, '-')
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
