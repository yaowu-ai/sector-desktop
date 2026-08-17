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
  Tooltip,
  Typography,
  message,
} from 'antd'
import { Play, RefreshCw, Save, Users } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageHeader } from '../components/PageHeader'
import { ProcessOutputPanel } from '../components/ProcessOutputPanel'
import { AccountBrowserEnvironment } from '../components/AccountBrowserEnvironment'
import { usePlatformContext } from '../app/PlatformContext'
import {
  getCurrentRunStatus,
  loadConfig,
  runPlatformTask,
  saveFypSettings,
} from '../services/api'
import { getPlatformLabel, isExecutablePlatform } from '../services/platforms'
import type { Account, ConfigSnapshot, FypSettings, ProcessStatus, RunStatus } from '../services/types'

type AccountMode = 'all' | 'single' | 'selected'

const TERMINAL_STATUS: RunStatus[] = ['completed', 'partial_failed', 'failed', 'stopped', 'idle']
const FYP_COMMENTS_FILE = 'comments.txt'

const DEFAULT_FYP_SETTINGS: FypSettings = {
  fypBrowseMinutes: [2, 5],
  likeProbability: 0.35,
  followsPerSession: [0, 1],
  comment: {
    enabled: false,
    commentsPerSession: [0, 1],
    minVideoComments: 100,
    probability: 0.2,
  },
}

export function TaskPage() {
  const { currentPlatform, currentPlatformDefinition } = usePlatformContext()
  const [form] = Form.useForm<FypSettings>()
  const [snapshot, setSnapshot] = useState<ConfigSnapshot | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountMode, setAccountMode] = useState<AccountMode>('all')
  const [singleAccountId, setSingleAccountId] = useState<string>()
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [startingTask, setStartingTask] = useState(false)
  const [watchingRun, setWatchingRun] = useState(false)
  const [runStatus, setRunStatus] = useState<ProcessStatus | null>(null)

  const commentEnabled = Form.useWatch(['comment', 'enabled'], form)

  const runnableAccounts = useMemo(
    () => accounts.filter((account) => account.enabled && isExecutablePlatform(account.platform)),
    [accounts],
  )
  const runnableAccountOptions = useMemo(
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
  const selectedRunAccounts = useMemo(
    () => resolveRunAccounts(accountMode, runnableAccounts, singleAccountId, selectedAccountIds),
    [accountMode, runnableAccounts, selectedAccountIds, singleAccountId],
  )

  const refresh = useCallback(
    async (showLoading = true) => {
      if (showLoading) {
        setLoading(true)
      }
      try {
        const nextSnapshot = await loadConfig()
        const nextPlatformAccounts = nextSnapshot.accounts.filter((account) => account.platform === currentPlatform)
        const nextRunnableAccounts = nextPlatformAccounts.filter(
          (account) => account.enabled && isExecutablePlatform(account.platform),
        )
        const nextRunnableIds = new Set(nextRunnableAccounts.map((account) => account.id))

        setSnapshot(nextSnapshot)
        setAccounts(nextPlatformAccounts)
        form.setFieldsValue(normalizeFypSettings(nextSnapshot.fypSettings))
        setSingleAccountId((current) => {
          if (current && nextRunnableIds.has(current)) {
            return current
          }
          return nextRunnableAccounts[0]?.id
        })
        setSelectedAccountIds((current) => current.filter((accountId) => nextRunnableIds.has(accountId)))
      } catch (error) {
        message.error(formatError(error))
      } finally {
        if (showLoading) {
          setLoading(false)
        }
      }
    },
    [currentPlatform, form],
  )

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (!watchingRun) {
      return undefined
    }

    const id = window.setInterval(() => {
      void getCurrentRunStatus()
        .then(async (status) => {
          setRunStatus(status)
          if (TERMINAL_STATUS.includes(status.status)) {
            setWatchingRun(false)
            await refresh(false)
            message.info(`任务已结束：${status.status}，账号快照已刷新`)
          }
        })
        .catch((error) => message.error(formatError(error)))
    }, 1500)

    return () => window.clearInterval(id)
  }, [refresh, watchingRun])

  const saveSettings = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      await saveFypSettings(normalizeFypSettings(values), currentPlatform)
      message.success('FYP 配置已保存到 accounts.yaml')
      await refresh(false)
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setSaving(false)
    }
  }

  const confirmStart = () => {
    const runAccounts = selectedRunAccounts
    if (runAccounts.length === 0) {
      message.warning('请选择可执行平台的启用账号')
      return
    }

    const taskName = `${currentPlatformDefinition.localeName} FYP 养号`
    const fypSettings = normalizeFypSettings(form.getFieldsValue(true))
    Modal.confirm({
      title: `确认启动 ${taskName}`,
      okText: '确认启动',
      cancelText: '取消',
      width: 620,
      content: (
        <Descriptions size="small" column={1} bordered style={{ marginTop: 12 }}>
          <Descriptions.Item label="任务类型">{taskName}</Descriptions.Item>
          <Descriptions.Item label="账号数量">{runAccounts.length}</Descriptions.Item>
          <Descriptions.Item label="执行账号">{runAccounts.map((account) => account.id).join(', ')}</Descriptions.Item>
          <Descriptions.Item label="浏览器环境">
            <AccountBrowserEnvironment accounts={runAccounts} />
          </Descriptions.Item>
          <Descriptions.Item label="FYP 时长">
            {fypSettings.fypBrowseMinutes[0]} - {fypSettings.fypBrowseMinutes[1]} 分钟
          </Descriptions.Item>
          <Descriptions.Item label="点赞概率">{formatPercent(fypSettings.likeProbability)}</Descriptions.Item>
          <Descriptions.Item label="关注数">
            {fypSettings.followsPerSession[0]} - {fypSettings.followsPerSession[1]} / session
          </Descriptions.Item>
          <Descriptions.Item label="评论">
            {fypSettings.comment.enabled
              ? `${fypSettings.comment.commentsPerSession[0]} - ${fypSettings.comment.commentsPerSession[1]} 条，概率 ${formatPercent(
                  fypSettings.comment.probability,
                )}`
              : '关闭'}
          </Descriptions.Item>
          <Descriptions.Item label="风险提示">
            将打开所选账号的浏览器环境并启动真实 Python 自动化任务。
          </Descriptions.Item>
        </Descriptions>
      ),
      onOk: async () => {
        await startTask(runAccounts)
      },
    })
  }

  const startTask = async (runAccounts: Account[]) => {
    setStartingTask(true)
    try {
      const accountIds = runAccounts.map((account) => account.id)
      const result = await runPlatformTask({
        platform: currentPlatform,
        taskType: 'fyp',
        accountIds,
        mode: accountMode === 'all' ? 'all' : accountIds.length === 1 ? 'single' : 'selected',
      })
      setWatchingRun(true)
      setRunStatus(null)
      message.success(`任务已启动，PID ${result.processId ?? '-'}`)
      await refresh(false)
    } catch (error) {
      message.error(formatError(error))
      throw error
    } finally {
      setStartingTask(false)
    }
  }

  const fypSettings = normalizeFypSettings(snapshot?.fypSettings)
  const fypDisabledReason = selectedRunAccounts.length === 0 ? '没有可执行的 FYP 账号' : undefined

  return (
    <>
      <PageHeader
        title="养号任务"
        description="按当前平台读取养号配置和账号；未支持平台会显示统一不支持状态。"
        extra={
          <Button icon={<RefreshCw size={16} />} onClick={() => void refresh()} loading={loading}>
            刷新
          </Button>
        }
      />

      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={14}>
            <Card
              title="FYP 参数"
              extra={
                <Button type="primary" icon={<Save size={16} />} loading={saving} onClick={() => void saveSettings()}>
                  保存配置
                </Button>
              }
            >
              <Form form={form} layout="vertical" requiredMark={false} initialValues={DEFAULT_FYP_SETTINGS}>
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item label="FYP 浏览时长范围（分钟）" required>
                      <Space.Compact block>
                        <Form.Item
                          name={['fypBrowseMinutes', 0]}
                          noStyle
                          rules={[{ required: true, message: '请输入最小时长' }]}
                        >
                          <InputNumber min={0} step={0.5} precision={1} className="full-width" placeholder="最小" />
                        </Form.Item>
                        <Form.Item
                          name={['fypBrowseMinutes', 1]}
                          noStyle
                          rules={[
                            { required: true, message: '请输入最大时长' },
                            { validator: () => validateFormRange(form, 'fypBrowseMinutes', 'FYP 浏览时长范围') },
                          ]}
                        >
                          <InputNumber min={0} step={0.5} precision={1} className="full-width" placeholder="最大" />
                        </Form.Item>
                      </Space.Compact>
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
                    <Form.Item label="每 session 关注数量范围" required>
                      <Space.Compact block>
                        <Form.Item
                          name={['followsPerSession', 0]}
                          noStyle
                          rules={[{ required: true, message: '请输入最小关注数' }]}
                        >
                          <InputNumber min={0} precision={0} className="full-width" placeholder="最小" />
                        </Form.Item>
                        <Form.Item
                          name={['followsPerSession', 1]}
                          noStyle
                          rules={[
                            { required: true, message: '请输入最大关注数' },
                            { validator: () => validateFormRange(form, 'followsPerSession', '关注数量范围') },
                          ]}
                        >
                          <InputNumber min={0} precision={0} className="full-width" placeholder="最大" />
                        </Form.Item>
                      </Space.Compact>
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name={['comment', 'enabled']} label="评论开关" valuePropName="checked">
                      <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item label="每 session 评论数量范围" required>
                      <Space.Compact block>
                        <Form.Item
                          name={['comment', 'commentsPerSession', 0]}
                          noStyle
                          rules={[{ required: true, message: '请输入最小评论数' }]}
                        >
                          <InputNumber
                            min={0}
                            precision={0}
                            className="full-width"
                            placeholder="最小"
                            disabled={!commentEnabled}
                          />
                        </Form.Item>
                        <Form.Item
                          name={['comment', 'commentsPerSession', 1]}
                          noStyle
                          rules={[
                            { required: true, message: '请输入最大评论数' },
                            {
                              validator: () =>
                                validateFormRange(form, ['comment', 'commentsPerSession'], '评论数量范围'),
                            },
                          ]}
                        >
                          <InputNumber
                            min={0}
                            precision={0}
                            className="full-width"
                            placeholder="最大"
                            disabled={!commentEnabled}
                          />
                        </Form.Item>
                      </Space.Compact>
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      name={['comment', 'probability']}
                      label="评论概率"
                      rules={[
                        { required: true, message: '请输入评论概率' },
                        { type: 'number', min: 0, max: 1, message: '概率必须在 0 到 1 之间' },
                      ]}
                    >
                      <InputNumber
                        min={0}
                        max={1}
                        step={0.05}
                        precision={2}
                        className="full-width"
                        disabled={!commentEnabled}
                      />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item
                      name={['comment', 'minVideoComments']}
                      label="评论数门槛"
                      rules={[
                        { required: true, message: '请输入评论数门槛' },
                        { type: 'number', min: 0, message: '评论数门槛必须大于等于 0' },
                      ]}
                    >
                      <InputNumber min={0} precision={0} className="full-width" disabled={!commentEnabled} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item label="评论池">
                      <Space wrap>
                        <Typography.Text code disabled={!commentEnabled}>
                          {FYP_COMMENTS_FILE}
                        </Typography.Text>
                        <Typography.Text type="secondary">内容从评论素材页面维护。</Typography.Text>
                      </Space>
                    </Form.Item>
                  </Col>
                </Row>
              </Form>
            </Card>
          </Col>

          <Col xs={24} xl={10}>
            <Card title="执行账号" extra={<Users size={16} />}>
              <Space direction="vertical" size={14} className="full-width">
                <Select
                  value={accountMode}
                  onChange={setAccountMode}
                  options={[
                    { value: 'all', label: `全部可执行平台账号（${runnableAccounts.length}）` },
                    { value: 'single', label: '单账号' },
                    { value: 'selected', label: '多账号' },
                  ]}
                />
                {accountMode === 'single' ? (
                  <Select
                    showSearch
                    value={singleAccountId}
                    onChange={setSingleAccountId}
                    options={runnableAccountOptions}
                    placeholder="选择单个账号"
                  />
                ) : null}
                {accountMode === 'selected' ? (
                  <Select
                    mode="multiple"
                    showSearch
                    value={selectedAccountIds}
                    onChange={setSelectedAccountIds}
                    options={runnableAccountOptions}
                    placeholder="选择多个账号"
                  />
                ) : null}
                <Descriptions size="small" column={1} bordered>
                  <Descriptions.Item label="可执行账号">{runnableAccounts.length}</Descriptions.Item>
                  <Descriptions.Item label="本次 FYP 账号">{selectedRunAccounts.length}</Descriptions.Item>
                  <Descriptions.Item label="本次 FYP 浏览器">
                    <div
                      className={
                        selectedRunAccounts.length > 3
                          ? 'task-fyp-browser-list task-fyp-browser-list-scrollable'
                          : 'task-fyp-browser-list'
                      }
                    >
                      <AccountBrowserEnvironment accounts={selectedRunAccounts} />
                    </div>
                  </Descriptions.Item>
                  <Descriptions.Item label="当前 FYP 配置">
                    {fypSettings.fypBrowseMinutes[0]}-{fypSettings.fypBrowseMinutes[1]} 分钟，点赞{' '}
                    {formatPercent(fypSettings.likeProbability)}
                  </Descriptions.Item>
                </Descriptions>
                <Space wrap>
                  <Tooltip title={fypDisabledReason}>
                    <span>
                      <Button
                        type="primary"
                        icon={<Play size={16} />}
                        disabled={Boolean(fypDisabledReason)}
                        loading={startingTask}
                        onClick={confirmStart}
                      >
                        启动 FYP 养号
                      </Button>
                    </span>
                  </Tooltip>
                </Space>
              </Space>
            </Card>
          </Col>

          <Col span={24}>
            <ProcessOutputPanel title="任务运行输出" />
          </Col>
        </Row>
      </Spin>
    </>
  )
}

function resolveRunAccounts(
  accountMode: AccountMode,
  runnableAccounts: Account[],
  singleAccountId?: string,
  selectedAccountIds: string[] = [],
) {
  if (accountMode === 'all') {
    return runnableAccounts
  }
  if (accountMode === 'single') {
    return runnableAccounts.filter((account) => account.id === singleAccountId)
  }
  const selectedSet = new Set(selectedAccountIds)
  return runnableAccounts.filter((account) => selectedSet.has(account.id))
}

function normalizeFypSettings(settings?: Partial<FypSettings>): FypSettings {
  return {
    fypBrowseMinutes: normalizeNumberRange(settings?.fypBrowseMinutes, DEFAULT_FYP_SETTINGS.fypBrowseMinutes),
    likeProbability: Number(settings?.likeProbability ?? DEFAULT_FYP_SETTINGS.likeProbability),
    followsPerSession: normalizeIntegerRange(settings?.followsPerSession, DEFAULT_FYP_SETTINGS.followsPerSession),
    comment: {
      enabled: Boolean(settings?.comment?.enabled ?? DEFAULT_FYP_SETTINGS.comment.enabled),
      commentsPerSession: normalizeIntegerRange(
        settings?.comment?.commentsPerSession,
        DEFAULT_FYP_SETTINGS.comment.commentsPerSession,
      ),
      minVideoComments: Math.max(
        0,
        Math.trunc(Number(settings?.comment?.minVideoComments ?? DEFAULT_FYP_SETTINGS.comment.minVideoComments)),
      ),
      probability: Number(settings?.comment?.probability ?? DEFAULT_FYP_SETTINGS.comment.probability),
    },
  }
}

function normalizeNumberRange(value: unknown, fallback: [number, number]): [number, number] {
  if (!Array.isArray(value)) {
    return fallback
  }
  return [Number(value[0] ?? fallback[0]), Number(value[1] ?? fallback[1])]
}

function normalizeIntegerRange(value: unknown, fallback: [number, number]): [number, number] {
  const range = normalizeNumberRange(value, fallback)
  return [Math.max(0, Math.trunc(range[0])), Math.max(0, Math.trunc(range[1]))]
}

function validateFormRange(
  form: ReturnType<typeof Form.useForm<FypSettings>>[0],
  field: 'fypBrowseMinutes' | 'followsPerSession' | ['comment', 'commentsPerSession'],
  label: string,
) {
  const range = form.getFieldValue(field) as [number | undefined, number | undefined] | undefined
  const min = Number(range?.[0])
  const max = Number(range?.[1])
  if (Number.isNaN(min) || Number.isNaN(max) || min < 0 || min > max) {
    return Promise.reject(new Error(`${label}必须满足 0 <= 最小值 <= 最大值`))
  }
  return Promise.resolve()
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
