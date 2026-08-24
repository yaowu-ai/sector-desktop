import { Button, Card, DatePicker, Empty, Input, Modal, Select, Space, Tabs, Tag, Typography, message } from 'antd'
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
const STATUS_OPTIONS = [
  { value: 'success', label: '正常' },
  { value: 'warning', label: '警告' },
  { value: 'error', label: '错误' },
  { value: 'ok', label: 'ok' },
  { value: 'failed', label: 'failed' },
  { value: 'skip', label: 'skip' },
  { value: 'running', label: 'running' },
  { value: 'completed', label: 'completed' },
  { value: 'stopped', label: 'stopped' },
]

type TimeRange = [Dayjs, Dayjs] | null
type SessionLogSeverity = 'success' | 'info' | 'warning' | 'error'

interface SessionLogEntry {
  id: string
  raw: string
  timestamp?: string
  platform?: string
  accountId?: string
  event?: string
  message: string
  details: string[]
  severity: SessionLogSeverity
}

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
  const filteredSessionLogEntries = useMemo(
    () =>
      parseSessionLogEntries(sessionLog).filter((entry) =>
        sessionLogEntryMatches(entry, {
          platformFilter,
          accountId,
          taskType,
          status,
          keyword,
          timeRange,
          accountPlatformMap,
        }),
      ),
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
        {filteredSessionLog || filteredSessionLogEntries.length ? (
          <Tabs
            className="session-log-tabs"
            items={[
              {
                key: 'structured',
                label: '结构化日志',
                children: filteredSessionLogEntries.length ? (
                  <SessionLogEntryList entries={filteredSessionLogEntries} />
                ) : (
                  <SessionLogEmptyState
                    initialized={logExists !== false}
                    filtered={Boolean(sessionLog)}
                    refreshing={refreshing}
                    onRefresh={() => void reloadLog()}
                    onGoToTasks={goToTasks}
                  />
                ),
              },
              {
                key: 'raw',
                label: '原始日志',
                children: (
                  <LogBlock
                    value={filteredSessionLog}
                    filename="sessions.log"
                    className="session-log-block"
                    contentClassName="global-log-content session-log-content"
                  />
                ),
              },
            ]}
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

function SessionLogEntryList({ entries }: { entries: SessionLogEntry[] }) {
  return (
    <div className="session-log-list">
      {entries.map((entry) => (
        <SessionLogEntryRow key={entry.id} entry={entry} />
      ))}
    </div>
  )
}

function SessionLogEntryRow({ entry }: { entry: SessionLogEntry }) {
  const severity = SESSION_LOG_SEVERITY_META[entry.severity]

  return (
    <article className={`session-log-entry session-log-entry-${entry.severity}`}>
      <div className="session-log-entry-header">
        <Tag color={severity.color}>{severity.label}</Tag>
        {entry.timestamp ? <Typography.Text className="session-log-entry-time">{entry.timestamp}</Typography.Text> : null}
        {entry.platform ? <Tag className="session-log-entry-platform">{entry.platform}</Tag> : null}
        {entry.accountId ? <Typography.Text code>{entry.accountId}</Typography.Text> : null}
        {entry.event ? <Tag color="default">{entry.event}</Tag> : null}
      </div>
      <Typography.Text className="session-log-entry-message">{entry.message || entry.raw}</Typography.Text>
      {entry.details.length ? (
        <details className="session-log-entry-details">
          <summary>查看详情（{entry.details.length} 行）</summary>
          <pre>{entry.details.join('\n')}</pre>
        </details>
      ) : null}
    </article>
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

const SESSION_LOG_ENTRY_RE = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| ([^|]+) \| (.*)$/
const SESSION_LOG_SEVERITY_META: Record<SessionLogSeverity, { label: string; color: string }> = {
  success: { label: '正常', color: 'green' },
  info: { label: '信息', color: 'blue' },
  warning: { label: '警告', color: 'gold' },
  error: { label: '错误', color: 'red' },
}

function parseSessionLogEntries(value: string): SessionLogEntry[] {
  const entries: SessionLogEntry[] = []
  let current: SessionLogEntry | undefined

  value.split(/\r?\n/).forEach((line, index) => {
    const match = line.match(SESSION_LOG_ENTRY_RE)
    if (match) {
      current = buildSessionLogEntry(match[1], match[2], match[3], index)
      entries.push(current)
      return
    }
    if (current && line.trim()) {
      current.details.push(line)
      current.raw = `${current.raw}\n${line}`
    }
  })

  return entries
}

function buildSessionLogEntry(timestamp: string, platform: string, content: string, index: number): SessionLogEntry {
  const segments = content.split('|').map((segment) => segment.trim())
  const hasAccount = segments.length >= 2 && looksLikeAccountId(segments[0])
  const accountId = hasAccount ? segments[0] : undefined
  const event = hasAccount ? segments[1] : segments[0]
  const message = hasAccount ? segments.slice(2).join(' | ') : segments.slice(1).join(' | ')

  return {
    id: `${timestamp}-${index}`,
    raw: `${timestamp} | ${platform} | ${content}`,
    timestamp,
    platform: platform.trim(),
    accountId,
    event,
    message,
    details: [],
    severity: classifySessionLogSeverity(content),
  }
}

function looksLikeAccountId(value: string) {
  return /^[a-z][a-z0-9_-]*_\d+$/i.test(value)
}

function classifySessionLogSeverity(value: string): SessionLogSeverity {
  const normalized = value.toLowerCase()
  if (
    /\|\s*error\s*\|/i.test(value) ||
    normalized.includes('[err]') ||
    normalized.includes(' failed') ||
    normalized.includes('exception') ||
    normalized.includes('traceback') ||
    normalized.includes('runtimeerror') ||
    normalized.includes('attributeerror')
  ) {
    return 'error'
  }
  if (
    /\|\s*skip\s*\|/i.test(value) ||
    normalized.includes('batch stop') ||
    normalized.includes('[warn]') ||
    normalized.includes(' warning') ||
    normalized.includes('logged_out') ||
    normalized.includes('captcha') ||
    normalized.includes('security_check') ||
    normalized.includes('intervention')
  ) {
    return 'warning'
  }
  if (
    /\|\s*ok\s*($|\|)/i.test(value) ||
    normalized.includes(' ok') ||
    normalized.includes('completed') ||
    normalized.includes('batch end | 星域 bot') ||
    normalized.includes('batch end | account matrix bot')
  ) {
    return 'success'
  }
  return 'info'
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
  if (filters.status && !lineMatchesStatus(line, filters.status)) {
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

function sessionLogEntryMatches(
  entry: SessionLogEntry,
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
  const raw = entry.raw
  const normalized = raw.toLowerCase()
  if (filters.accountId && entry.accountId !== filters.accountId && !raw.includes(filters.accountId)) {
    return false
  }
  if (filters.taskType && !normalized.includes(filters.taskType.toLowerCase())) {
    return false
  }
  if (filters.status && !entryMatchesStatus(entry, filters.status)) {
    return false
  }
  if (filters.keyword.trim() && !normalized.includes(filters.keyword.trim().toLowerCase())) {
    return false
  }
  if (filters.platformFilter !== 'all' && !lineMatchesPlatform(raw, filters.platformFilter, filters.accountPlatformMap)) {
    return false
  }
  if (filters.timeRange && !lineMatchesTimeRange(raw, filters.timeRange)) {
    return false
  }
  return true
}

function lineMatchesStatus(line: string, status: string) {
  const severity = classifySessionLogSeverity(line)
  if (status === 'success' || status === 'warning' || status === 'error') {
    return severity === status
  }
  return line.toLowerCase().includes(status.toLowerCase())
}

function entryMatchesStatus(entry: SessionLogEntry, status: string) {
  if (status === 'success' || status === 'warning' || status === 'error') {
    return entry.severity === status
  }
  return entry.raw.toLowerCase().includes(status.toLowerCase())
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
