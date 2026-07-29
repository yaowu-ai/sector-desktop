import { Button, Card, DatePicker, Empty, Input, Modal, Select, Space, Tag, Typography, message } from 'antd'
import type { Dayjs } from 'dayjs'
import { FilterX, PlayCircle, RefreshCw, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageHeader } from '../components/PageHeader'
import { PlatformScopeFilter } from '../components/PlatformScopeFilter'
import { LogBlock } from '../components/LogViewer'
import { clearSessionLog, loadConfig, tailSessionLog } from '../services/api'
import type { Account, Platform } from '../services/types'
import type { PlatformFilterValue } from '../app/pageScope'

const { RangePicker } = DatePicker

const LOG_POLL_MS = 3000
const MAX_LOG_LENGTH = 12000
const TASK_TYPE_OPTIONS = [
  { value: 'fyp', label: '养号' },
  { value: 'target', label: '目标互动' },
  { value: 'scheduler', label: '调度' },
  { value: 'gmail', label: 'Gmail' },
  { value: 'diagnostic', label: '诊断' },
]
const STATUS_OPTIONS = ['ok', 'error', 'failed', 'skip', 'running', 'completed', 'stopped'].map((value) => ({
  value,
  label: value,
}))

type TimeRange = [Dayjs, Dayjs] | null

export function SessionLogPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [platformFilter, setPlatformFilter] = useState<PlatformFilterValue>('all')
  const [accountId, setAccountId] = useState<string>()
  const [taskType, setTaskType] = useState<string>()
  const [status, setStatus] = useState<string>()
  const [keyword, setKeyword] = useState('')
  const [timeRange, setTimeRange] = useState<TimeRange>(null)
  const [logOffset, setLogOffset] = useState(0)
  const [sessionLog, setSessionLog] = useState('')
  const [logExists, setLogExists] = useState<boolean | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [clearing, setClearing] = useState(false)

  const accountPlatformMap = useMemo(
    () => new Map(accounts.map((account) => [account.id, account.platform])),
    [accounts],
  )
  const accountOptions = useMemo(
    () =>
      accounts.filter((account) => accountMatchesPlatform(account, platformFilter)).map((account) => ({
        value: account.id,
        label: account.id,
      })),
    [accounts, platformFilter],
  )
  const filteredSessionLog = useMemo(
    () =>
      sessionLog
        .split(/\r?\n/)
        .filter((line) =>
          sessionLogLineMatches(line, {
            platformFilter,
            accountId,
            taskType,
            status,
            keyword,
            timeRange,
            accountPlatformMap,
          }),
        )
        .join('\n'),
    [accountId, accountPlatformMap, keyword, platformFilter, sessionLog, status, taskType, timeRange],
  )

  const refreshLog = useCallback(async () => {
    const chunk = await tailSessionLog(logOffset)
    setLogExists(chunk.exists)
    setLogOffset(chunk.nextOffset)
    if (chunk.content) {
      setSessionLog((current) => `${current}${chunk.content}`.slice(-MAX_LOG_LENGTH))
    }
    return chunk
  }, [logOffset])

  const reloadLog = async () => {
    setRefreshing(true)
    try {
      const chunk = await tailSessionLog(0)
      const snapshot = await loadConfig()
      setAccounts(snapshot.accounts)
      setLogExists(chunk.exists)
      setLogOffset(chunk.nextOffset)
      setSessionLog((chunk.content ?? '').slice(-MAX_LOG_LENGTH))
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setRefreshing(false)
    }
  }

  const confirmClear = () => {
    Modal.confirm({
      title: '清空 sessions.log',
      content: '将清空当前 sessions.log 文件内容，此操作不会删除执行记录数据库。',
      okText: '清空',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        setClearing(true)
        try {
          const result = await clearSessionLog()
          setLogExists(result.cleared)
          setLogOffset(0)
          setSessionLog('')
          message.success('sessions.log 已清空')
        } catch (error) {
          message.error(formatError(error))
        } finally {
          setClearing(false)
        }
      },
    })
  }

  const resetFilters = () => {
    setPlatformFilter('all')
    setAccountId(undefined)
    setTaskType(undefined)
    setStatus(undefined)
    setKeyword('')
    setTimeRange(null)
  }

  const updatePlatformFilter = (value: PlatformFilterValue) => {
    setPlatformFilter(value)
    setAccountId(undefined)
  }

  const goToTasks = () => {
    window.location.hash = 'tasks'
  }
  const sessionLogStatus = getSessionLogStatus(logExists)

  useEffect(() => {
    void reloadLog()
  }, [])

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshLog().catch((error) => message.error(formatError(error)))
    }, LOG_POLL_MS)
    return () => window.clearInterval(id)
  }, [refreshLog])

  return (
    <div className="session-log-page">
      <PageHeader
        title="Session 日志"
        description="集中查看 sessions.log 原始运行日志。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} loading={refreshing} onClick={() => void reloadLog()}>
              重新读取
            </Button>
            <Button icon={<FilterX size={16} />} onClick={resetFilters}>
              清空筛选
            </Button>
            <Button danger icon={<Trash2 size={16} />} loading={clearing} onClick={confirmClear}>
              清空日志
            </Button>
          </Space>
        }
      />

      <Card className="shell-alert">
        <Space wrap size={12}>
          <PlatformScopeFilter value={platformFilter} onChange={updatePlatformFilter} />
          <Select
            allowClear
            showSearch
            placeholder="账号"
            value={accountId}
            options={accountOptions}
            style={{ width: 180 }}
            onChange={setAccountId}
          />
          <Select
            allowClear
            placeholder="任务类型"
            value={taskType}
            options={TASK_TYPE_OPTIONS}
            style={{ width: 150 }}
            onChange={setTaskType}
          />
          <Select
            allowClear
            placeholder="状态"
            value={status}
            options={STATUS_OPTIONS}
            style={{ width: 140 }}
            onChange={setStatus}
          />
          <Input.Search
            allowClear
            placeholder="关键词"
            value={keyword}
            style={{ width: 220 }}
            onChange={(event) => setKeyword(event.target.value)}
          />
          <RangePicker
            showTime
            value={timeRange}
            onChange={(value) => setTimeRange(value as TimeRange)}
          />
        </Space>
      </Card>

      <Card
        className="session-log-card"
        title="sessions.log"
        extra={
          <Space size={10}>
            <Typography.Text type="secondary">每 {Math.round(LOG_POLL_MS / 1000)} 秒增量读取</Typography.Text>
            <Tag color={sessionLogStatus.color}>{sessionLogStatus.label}</Tag>
          </Space>
        }
      >
        {filteredSessionLog ? (
          <LogBlock
            value={filteredSessionLog}
            filename="sessions.log"
            className="session-log-block"
            contentClassName="global-log-content session-log-content"
          />
        ) : (
          <SessionLogEmptyState
            initialized={logExists !== false}
            filtered={Boolean(sessionLog)}
            refreshing={refreshing}
            onRefresh={() => void reloadLog()}
            onGoToTasks={goToTasks}
          />
        )}
      </Card>
    </div>
  )
}

function SessionLogEmptyState({
  initialized,
  filtered,
  refreshing,
  onRefresh,
  onGoToTasks,
}: {
  initialized: boolean
  filtered: boolean
  refreshing: boolean
  onRefresh: () => void
  onGoToTasks: () => void
}) {
  const title = !initialized ? '未初始化' : filtered ? '当前筛选范围没有日志' : '暂无运行日志'
  const description =
    !initialized || !filtered
      ? '暂无运行日志，启动任务后这里会显示 sessions.log 内容。'
      : '调整筛选条件，或重新读取 sessions.log 后再查看。'

  return (
    <Empty
      className="global-log-empty session-log-empty"
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description={<EmptyDescription title={title} description={description} />}
    >
      <Space>
        <Button size="small" icon={<PlayCircle size={14} />} onClick={onGoToTasks}>
          去运行任务
        </Button>
        <Button size="small" icon={<RefreshCw size={14} />} loading={refreshing} onClick={onRefresh}>
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

function getSessionLogStatus(exists: boolean | null) {
  if (exists === null) {
    return { label: '检测中', color: 'default' }
  }
  return exists ? { label: '已生成', color: 'green' } : { label: '未初始化', color: 'gold' }
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

function accountMatchesPlatform(account: { platform: Platform }, platformFilter: PlatformFilterValue) {
  return platformFilter === 'all' || account.platform === platformFilter
}

function sessionLogLineMatches(
  line: string,
  filters: {
    platformFilter: PlatformFilterValue
    accountId?: string
    taskType?: string
    status?: string
    keyword: string
    timeRange: TimeRange
    accountPlatformMap: Map<string, Platform>
  },
) {
  if (!line) {
    return true
  }
  const normalized = line.toLowerCase()
  if (filters.accountId && !line.includes(filters.accountId)) {
    return false
  }
  if (filters.taskType && !normalized.includes(filters.taskType.toLowerCase())) {
    return false
  }
  if (filters.status && !normalized.includes(filters.status.toLowerCase())) {
    return false
  }
  if (filters.keyword.trim() && !normalized.includes(filters.keyword.trim().toLowerCase())) {
    return false
  }
  if (filters.platformFilter !== 'all' && !lineMatchesPlatform(line, filters.platformFilter, filters.accountPlatformMap)) {
    return false
  }
  if (filters.timeRange && !lineMatchesTimeRange(line, filters.timeRange)) {
    return false
  }
  return true
}

function lineMatchesPlatform(
  line: string,
  platformFilter: Platform,
  accountPlatformMap: Map<string, Platform>,
) {
  const normalized = line.toLowerCase()
  if (normalized.includes(platformFilter)) {
    return true
  }
  for (const [accountId, platform] of accountPlatformMap) {
    if (platform === platformFilter && line.includes(accountId)) {
      return true
    }
  }
  return false
}

function lineMatchesTimeRange(line: string, timeRange: [Dayjs, Dayjs]) {
  const timestamp = line.match(/\d{4}-\d{2}-\d{2}[ tT]\d{2}:\d{2}:\d{2}/)?.[0]
  if (!timestamp) {
    return true
  }
  const time = new Date(timestamp.replace(' ', 'T')).getTime()
  return time >= timeRange[0].valueOf() && time <= timeRange[1].valueOf()
}
