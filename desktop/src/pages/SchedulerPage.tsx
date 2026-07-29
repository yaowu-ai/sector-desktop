import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  InputNumber,
  Modal,
  Row,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { CalendarClock, PauseCircle, Play, RefreshCw, Save, TimerReset, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { confirmDanger } from '../components/ConfirmDanger'
import { PageHeader } from '../components/PageHeader'
import { StatusTag } from '../components/StatusTag'
import { usePlatformContext } from '../app/PlatformContext'
import {
  checkBitbrowserApi,
  clearRunLock,
  getSchedulerHealth,
  getSchedulerProcessStatus,
  loadConfig,
  saveSchedulerSettings,
  startScheduler,
  stopScheduler,
} from '../services/api'
import { getAutomaticExecutionDisabledReason, getPlatformLabel, isExecutablePlatform } from '../services/platforms'
import type {
  Account,
  ApiStatus,
  IpGroupConflict,
  Platform,
  SchedulerAccountSettings,
  SchedulerHealth,
  SchedulerJob,
  SchedulerProcessStatus,
} from '../services/types'

interface SchedulerRow {
  id: string
  enabled: boolean
  scheduled: boolean
  platform: Platform
  ipGroup?: number
  activeHours: [number, number][]
  notes?: string
}

interface ActiveHoursFormValues {
  activeHours: Array<{ start?: number; end?: number }>
}

const EMPTY_HEALTH: SchedulerHealth = {
  status: 'stopped',
  jobs: [],
  todayScheduleCount: 0,
  firesPerDay: 3,
  runLock: {
    path: 'data/run.lock',
    exists: false,
    active: false,
  },
  ipGroupConflicts: [],
}

const EMPTY_PROCESS: SchedulerProcessStatus = {
  status: 'stopped',
  command: ['py', '-3.13', 'src/scheduler.py'],
  healthUrl: 'http://127.0.0.1:9601/health',
}

export function SchedulerPage() {
  const { currentPlatform } = usePlatformContext()
  const [form] = Form.useForm<ActiveHoursFormValues>()
  const [bitbrowser, setBitbrowser] = useState<ApiStatus | null>(null)
  const [health, setHealth] = useState<SchedulerHealth>(EMPTY_HEALTH)
  const [processStatus, setProcessStatus] = useState<SchedulerProcessStatus>(EMPTY_PROCESS)
  const [rows, setRows] = useState<SchedulerRow[]>([])
  const [firesPerDay, setFiresPerDay] = useState(3)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editingRow, setEditingRow] = useState<SchedulerRow | null>(null)

  const schedulableRows = useMemo(
    () => rows.filter((row) => row.enabled && row.scheduled && isExecutablePlatform(row.platform)),
    [rows],
  )
  const schedulerStartDisabledReason =
    processStatus.status === 'running'
      ? '调度服务已在运行'
      : !isExecutablePlatform(currentPlatform)
        ? getAutomaticExecutionDisabledReason(currentPlatform, 'scheduler')
        : undefined
  const rowAccountIds = useMemo(() => new Set(rows.map((row) => row.id)), [rows])
  const scopedJobs = useMemo(
    () => health.jobs.filter((job) => !job.accountId || rowAccountIds.has(job.accountId)),
    [health.jobs, rowAccountIds],
  )
  const scopedConflicts = useMemo(
    () =>
      health.ipGroupConflicts.filter(
        (conflict) => rowAccountIds.has(conflict.leftAccountId) || rowAccountIds.has(conflict.rightAccountId),
      ),
    [health.ipGroupConflicts, rowAccountIds],
  )
  const plannedToday = schedulableRows.length * Math.max(0, firesPerDay)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [snapshot, nextProcess, nextHealth, nextBitbrowser] = await Promise.all([
        loadConfig(),
        getSchedulerProcessStatus(),
        getSchedulerHealth(),
        checkBitbrowserApi(),
      ])
      setRows(snapshot.accounts.filter((account) => account.platform === currentPlatform).map(accountToRow))
      setFiresPerDay(snapshot.schedulerSettings?.firesPerDay ?? nextHealth.firesPerDay ?? 3)
      setProcessStatus(nextProcess)
      setHealth(nextHealth)
      setBitbrowser(nextBitbrowser)
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setLoading(false)
    }
  }, [currentPlatform])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => {
      void refresh()
    }, 10000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const start = async () => {
    setStarting(true)
    try {
      const result = await startScheduler()
      message.success(`调度服务已启动，PID ${result.processId}`)
      await refresh()
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setStarting(false)
    }
  }

  const confirmStop = () => {
    confirmDanger({
      title: '停止调度服务',
      content: '停止 scheduler.py 只会停止后续排期，不等于立刻停止已经触发的账号任务。',
      onOk: () => {
        void stop()
      },
    })
  }

  const confirmClearRunLock = () => {
    confirmDanger({
      title: '清理 run.lock',
      content: '将清理本机任务锁。仅当确认没有养号脚本正在运行时执行；活跃任务锁会被后端拒绝。',
      onOk: () => {
        void clearLock()
      },
    })
  }

  const clearLock = async () => {
    try {
      const result = await clearRunLock()
      message.success(result.message)
      await refresh()
    } catch (error) {
      message.error(formatError(error))
    }
  }

  const stop = async () => {
    setStopping(true)
    try {
      const result = await stopScheduler()
      message.success(result.message)
      await refresh()
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setStopping(false)
    }
  }

  const save = async () => {
    setSaving(true)
    try {
      await saveSchedulerSettings({
        firesPerDay,
        accounts: rows.map(rowToSchedulerAccount),
      })
      message.success('调度配置已保存到 accounts.yaml')
      await refresh()
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setSaving(false)
    }
  }

  const updateIpGroup = (accountId: string, value: number | null) => {
    setRows((current) =>
      current.map((row) =>
        row.id === accountId
          ? {
              ...row,
              ipGroup: value === null ? undefined : Number(value),
            }
          : row,
      ),
    )
  }

  const updateScheduled = (accountId: string, scheduled: boolean) => {
    setRows((current) =>
      current.map((row) =>
        row.id === accountId
          ? {
              ...row,
              scheduled,
            }
          : row,
      ),
    )
  }

  const openActiveHoursEditor = (row: SchedulerRow) => {
    setEditingRow(row)
    form.setFieldsValue({
      activeHours: row.activeHours.map(([start, end]) => ({ start, end })),
    })
  }

  const saveActiveHours = async () => {
    const values = await form.validateFields()
    if (!editingRow) {
      return
    }
    const nextActiveHours = values.activeHours.map((range) => [Number(range.start), Number(range.end)] as [number, number])
    setRows((current) =>
      current.map((row) =>
        row.id === editingRow.id
          ? {
              ...row,
              activeHours: nextActiveHours,
            }
          : row,
      ),
    )
    setEditingRow(null)
  }

  return (
    <>
      <PageHeader
        title="调度计划"
        description="按平台和账号 active_hours 生成本机时间排期；当前只调度已适配自动执行的平台。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={() => void refresh()}>
              刷新
            </Button>
            <Button
              icon={<PauseCircle size={16} />}
              danger
              loading={stopping}
              disabled={processStatus.status !== 'running'}
              onClick={confirmStop}
            >
              停止调度
            </Button>
            <Tooltip title={schedulerStartDisabledReason}>
              <span>
                <Button
                  type="primary"
                  icon={<Play size={16} />}
                  loading={starting}
                  disabled={Boolean(schedulerStartDisabledReason)}
                  onClick={() => void start()}
                >
                  启动调度
                </Button>
              </span>
            </Tooltip>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Alert
            showIcon
            type="info"
            message="V1 调度使用运行机器本地时间"
            description="修改 fires_per_day、ip_group 或 active_hours 后，需要保存配置；已经启动的 scheduler.py 不会自动重载旧进程中的排期，建议停止后重新启动调度服务。"
          />
        </Col>

        <Col xs={24} md={8} xl={4}>
          <Card>
            <Space direction="vertical" size={8}>
              <Typography.Text type="secondary">调度服务</Typography.Text>
              <SchedulerStatusTag status={health.status} />
              <Typography.Text type="secondary">PID {health.processId ?? processStatus.processId ?? '-'}</Typography.Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Space direction="vertical" size={8}>
              <Typography.Text type="secondary">BitBrowser API</Typography.Text>
              <StatusTag
                status={bitbrowser?.available ? 'ok' : 'error'}
                label={bitbrowser?.available ? '可用' : '不可用'}
              />
              <Typography.Text type="secondary" ellipsis style={{ maxWidth: 180 }}>
                {bitbrowser?.apiUrl ?? '-'}
              </Typography.Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic
              title="今日排期"
              value={scopedJobs.length}
              suffix={`/ ${plannedToday}`}
              prefix={<CalendarClock size={16} />}
            />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic title="fires_per_day" value={firesPerDay} prefix={<TimerReset size={16} />} />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic title="下一账号" value={health.nextAccountId ?? '-'} />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic title="run.lock" value={health.runLock.active ? '活跃' : health.runLock.exists ? '存在' : '无'} />
          </Card>
        </Col>

        <Col span={24}>
          <Card>
            <Space direction="vertical" size={12} className="full-width">
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                  border: '1px solid #f0f0f0',
                  borderRadius: 6,
                  overflow: 'hidden',
                }}
              >
                <ScheduleSummaryItem label="下次执行" value={formatScheduleTime(health.nextRun)} />
                <ScheduleSummaryItem label="调度状态" value={formatSchedulerStatusText(health.status)} />
                <ScheduleSummaryItem label="服务状态" value={formatServiceStatus(health, processStatus)} />
                <ScheduleSummaryItem label="排班检查" value={formatConflictSummary(scopedConflicts)} />
              </div>
              {health.error ? <Alert type="warning" showIcon message={health.error} /> : null}
              {health.runLock.exists ? (
                <Alert
                  type={health.runLock.active ? 'warning' : 'info'}
                showIcon
                message={`任务锁${health.runLock.active ? '正在被运行任务占用' : '存在但任务已不活跃'}`}
                  description={health.runLock.pid ? `PID ${health.runLock.pid}` : undefined}
                  action={
                    <Button
                      size="small"
                      danger
                      icon={<Trash2 size={14} />}
                      onClick={confirmClearRunLock}
                    >
                      清理
                    </Button>
                  }
                />
              ) : null}
              <ConflictAlert conflicts={scopedConflicts} />
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card
            title="调度配置"
            extra={
              <Button type="primary" icon={<Save size={16} />} loading={saving} onClick={() => void save()}>
                保存配置
              </Button>
            }
          >
            <Space direction="vertical" size={16} className="full-width">
              <Space>
                <Typography.Text>每账号每日触发次数</Typography.Text>
                <InputNumber
                  min={0}
                  max={24}
                  precision={0}
                  value={firesPerDay}
                  onChange={(value) => setFiresPerDay(Number(value ?? 0))}
                />
              </Space>
              <Typography.Text type="secondary">
                今日预计排期 = 启用且参与调度账号数 {schedulableRows.length} × fires_per_day {firesPerDay}。
              </Typography.Text>
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card title={`当前 Jobs ${scopedJobs.length}`}>
            <Table
              rowKey="id"
              loading={loading}
              columns={jobColumns}
              dataSource={scopedJobs}
              pagination={{ pageSize: 6 }}
              scroll={{ x: 680 }}
            />
          </Card>
        </Col>

        <Col span={24}>
          <Card title="账号班次与 IP 分组">
            <Table
              rowKey="id"
              loading={loading}
              columns={accountColumns(updateIpGroup, updateScheduled, openActiveHoursEditor)}
              dataSource={rows}
              pagination={{ pageSize: 12, showSizeChanger: true }}
              scroll={{ x: 1100 }}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        title={editingRow ? `编辑 ${editingRow.id} 班次` : '编辑班次'}
        open={Boolean(editingRow)}
        okText="应用"
        cancelText="取消"
        onOk={() => void saveActiveHours()}
        onCancel={() => setEditingRow(null)}
      >
        <Form form={form} layout="vertical" requiredMark={false}>
          <Form.List name="activeHours">
            {(fields, { add, remove }) => (
              <Space direction="vertical" className="full-width">
                {fields.map((field) => (
                  <Space key={field.key} align="baseline">
                    <Form.Item
                      {...field}
                      name={[field.name, 'start']}
                      rules={[{ required: true, message: '开始小时必填' }]}
                    >
                      <InputNumber min={0} max={24} step={0.5} placeholder="开始" />
                    </Form.Item>
                    <Typography.Text>到</Typography.Text>
                    <Form.Item
                      {...field}
                      name={[field.name, 'end']}
                      rules={[
                        { required: true, message: '结束小时必填' },
                        {
                          validator: () => validateActiveHours(form),
                        },
                      ]}
                    >
                      <InputNumber min={0} max={24} step={0.5} placeholder="结束" />
                    </Form.Item>
                    <Button disabled={fields.length <= 1} onClick={() => remove(field.name)}>
                      删除
                    </Button>
                  </Space>
                ))}
                <Button onClick={() => add({ start: 19, end: 23 })}>新增班次</Button>
              </Space>
            )}
          </Form.List>
        </Form>
      </Modal>
    </>
  )
}

const jobColumns: ColumnsType<SchedulerJob> = [
  { title: 'Job ID', dataIndex: 'id', width: 260, render: (value: string) => <Typography.Text code>{value}</Typography.Text> },
  { title: '账号', dataIndex: 'accountId', width: 150, render: (value?: string) => value ?? '-' },
  { title: '下次执行', dataIndex: 'nextRun', width: 220, render: (value?: string) => formatScheduleTime(value) },
  {
    title: '状态',
    dataIndex: 'status',
    width: 120,
    render: (value?: string) => <Tag color="blue">{value ?? 'scheduled'}</Tag>,
  },
]

function accountColumns(
  onIpGroupChange: (accountId: string, value: number | null) => void,
  onScheduledChange: (accountId: string, scheduled: boolean) => void,
  onEditActiveHours: (row: SchedulerRow) => void,
): ColumnsType<SchedulerRow> {
  return [
    { title: '账号', dataIndex: 'id', width: 150 },
    {
      title: '平台',
      dataIndex: 'platform',
      width: 110,
      render: (platform: Platform) => (
        <Tag color={isExecutablePlatform(platform) ? 'green' : 'gold'}>
          {getPlatformLabel(platform)}
        </Tag>
      ),
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      width: 90,
      render: (enabled: boolean) => (
        <StatusTag status={enabled ? 'ok' : 'idle'} label={enabled ? '启用' : '停用'} />
      ),
    },
    {
      title: '参与调度',
      dataIndex: 'scheduled',
      width: 120,
      render: (scheduled: boolean, row) => (
        <Switch
          size="small"
          checked={scheduled}
          disabled={!row.enabled || !isExecutablePlatform(row.platform)}
          onChange={(checked) => onScheduledChange(row.id, checked)}
        />
      ),
    },
    {
      title: 'ip_group',
      dataIndex: 'ipGroup',
      width: 150,
      render: (value: number | undefined, row) => (
        <InputNumber
          min={0}
          precision={0}
          value={value}
          placeholder="未设置"
          onChange={(nextValue) => onIpGroupChange(row.id, nextValue)}
        />
      ),
    },
    {
      title: 'active_hours',
      dataIndex: 'activeHours',
      render: (ranges: [number, number][], row) => (
        <Space wrap>
          {ranges.length ? ranges.map(([start, end]) => <Tag key={`${start}-${end}`}>{start}-{end}</Tag>) : '-'}
          <Button size="small" onClick={() => onEditActiveHours(row)}>
            编辑
          </Button>
        </Space>
      ),
    },
    { title: '备注', dataIndex: 'notes', ellipsis: true },
  ]
}

function SchedulerStatusTag({ status }: { status: SchedulerHealth['status'] }) {
  if (status === 'running') {
    return <StatusTag status="running" label="运行中" />
  }
  if (status === 'starting') {
    return <StatusTag status="warning" label="启动中" />
  }
  if (status === 'error') {
    return <StatusTag status="error" label="异常" />
  }
  return <StatusTag status="idle" label="未运行" />
}

function ScheduleSummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '96px minmax(0, 1fr)',
        minHeight: 40,
        borderRight: label === '排班检查' ? 0 : '1px solid #f0f0f0',
      }}
    >
      <div
        style={{
          padding: '8px 12px',
          background: '#fafafa',
          color: '#6b7280',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </div>
      <div
        style={{
          padding: '8px 12px',
          minWidth: 0,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={value}
      >
        {value}
      </div>
    </div>
  )
}

function ConflictAlert({ conflicts }: { conflicts: IpGroupConflict[] }) {
  if (!conflicts.length) {
    return <Alert type="success" showIcon message="IP 排班正常" />
  }
  return (
    <Alert
      type="error"
      showIcon
      message={`检测到 ${conflicts.length} 个 IP 排班冲突`}
      description={
        <Space direction="vertical" size={2}>
          {conflicts.slice(0, 6).map((conflict) => (
            <Typography.Text key={`${conflict.ipGroup}-${conflict.leftAccountId}-${conflict.rightAccountId}`}>
              IP 分组 {conflict.ipGroup}: {conflict.leftAccountId} {formatActiveHours(conflict.leftActiveHours)} 与{' '}
              {conflict.rightAccountId} {formatActiveHours(conflict.rightActiveHours)}
            </Typography.Text>
          ))}
          {conflicts.length > 6 ? <Typography.Text type="secondary">还有 {conflicts.length - 6} 条</Typography.Text> : null}
        </Space>
      }
    />
  )
}

function accountToRow(account: Account): SchedulerRow {
  return {
    id: account.id,
    enabled: account.enabled,
    scheduled: account.scheduled ?? true,
    platform: account.platform,
    ipGroup: account.ipGroup,
    activeHours: account.activeHours,
    notes: account.notes,
  }
}

function rowToSchedulerAccount(row: SchedulerRow): SchedulerAccountSettings {
  return {
    id: row.id,
    scheduled: row.scheduled,
    ipGroup: row.ipGroup,
    activeHours: row.activeHours,
  }
}

function validateActiveHours(form: ReturnType<typeof Form.useForm<ActiveHoursFormValues>>[0]) {
  const ranges = form.getFieldValue('activeHours') as ActiveHoursFormValues['activeHours'] | undefined
  const invalid = !ranges?.length || ranges.some((range) => {
    const start = Number(range?.start)
    const end = Number(range?.end)
    return Number.isNaN(start) || Number.isNaN(end) || start < 0 || end > 24 || start >= end
  })
  return invalid
    ? Promise.reject(new Error('班次必须满足 0 <= 开始 < 结束 <= 24'))
    : Promise.resolve()
}

function formatActiveHours(ranges: [number, number][]) {
  if (!ranges.length) {
    return '-'
  }
  return ranges.map(([start, end]) => `[${start}, ${end}]`).join(', ')
}

function formatScheduleTime(value?: string) {
  if (!value) {
    return '暂无排期'
  }
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm') : value
}

function formatSchedulerStatusText(status: SchedulerHealth['status']) {
  if (status === 'running') {
    return '运行中'
  }
  if (status === 'starting') {
    return '启动中'
  }
  if (status === 'error') {
    return '异常'
  }
  return '未运行'
}

function formatServiceStatus(health: SchedulerHealth, processStatus: SchedulerProcessStatus) {
  if (health.error || processStatus.error || health.status === 'error' || processStatus.status === 'error') {
    return '异常'
  }
  if (health.status === 'running' || processStatus.status === 'running') {
    return '正常'
  }
  if (health.status === 'starting' || processStatus.status === 'starting') {
    return '启动中'
  }
  return '未运行'
}

function formatConflictSummary(conflicts: IpGroupConflict[]) {
  return conflicts.length ? `发现 ${conflicts.length} 个 IP 排班冲突` : 'IP 排班正常'
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
