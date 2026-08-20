import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
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
  saveInstagramWarmupSettings,
} from '../services/api'
import { getPlatformLabel, isExecutablePlatform } from '../services/platforms'
import type {
  Account,
  ConfigSnapshot,
  FypSettings,
  InstagramWarmupSettings,
  ProcessStatus,
  RunStatus,
} from '../services/types'

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

const DEFAULT_INSTAGRAM_WARMUP_SETTINGS: InstagramWarmupSettings = {
  duration: 15,
  likeProb: 0.06,
  saveProb: 0.02,
  commentProb: 0.5,
  activeHours: '7-9,12-14,18-23',
  sessionsPerDay: '1-3',
  restDayProb: 0.15,
  minSessionGapMinutes: 90,
  onePerWindow: false,
  durationJitter: '0.5-1.5',
  maxLikesPerDay: 20,
  maxSavesPerDay: 10,
  maxFollowsPerDay: 3,
  maxLikesPerSession: 0,
  maxCommentsPerDay: 5,
  maxCommentsPerSession: 1,
  blockCooldownHours: 24,
  roundSkipProb: 0.15,
  requireProxy: true,
  noLike: false,
  noSave: false,
  noComment: false,
  noFollow: false,
  noStories: false,
  noReels: false,
  noExplore: false,
}

export function TaskPage() {
  const { currentPlatform, currentPlatformDefinition } = usePlatformContext()
  const [form] = Form.useForm()
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

  const isInstagram = currentPlatform === 'instagram'
  const commentEnabled = Form.useWatch(['comment', 'enabled'], form)
  const instagramNoComment = Form.useWatch('noComment', form)

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
        form.resetFields()
        form.setFieldsValue(
          currentPlatform === 'instagram'
            ? normalizeInstagramWarmupSettings(nextSnapshot.instagramWarmup)
            : normalizeFypSettings(nextSnapshot.fypSettings),
        )
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
      if (isInstagram) {
        await saveInstagramWarmupSettings(normalizeInstagramWarmupSettings(values), currentPlatform)
        message.success('Instagram 养号配置已保存到 accounts.yaml')
      } else {
        await saveFypSettings(normalizeFypSettings(values), currentPlatform)
        message.success('FYP 配置已保存到 accounts.yaml')
      }
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

    const taskName = isInstagram
      ? `${currentPlatformDefinition.localeName} 养号`
      : `${currentPlatformDefinition.localeName} FYP 养号`
    const fypSettings = normalizeFypSettings(form.getFieldsValue(true))
    const instagramSettings = normalizeInstagramWarmupSettings(form.getFieldsValue(true))
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
          {isInstagram ? (
            <>
              <Descriptions.Item label="会话时长">{instagramSettings.duration} 分钟</Descriptions.Item>
              <Descriptions.Item label="点赞 / 收藏 / 评论概率">
                {formatPercent(instagramSettings.likeProb)} / {formatPercent(instagramSettings.saveProb)} /{' '}
                {formatPercent(instagramSettings.commentProb)}
              </Descriptions.Item>
              <Descriptions.Item label="24h 预算">
                点赞 {instagramSettings.maxLikesPerDay}，收藏 {instagramSettings.maxSavesPerDay}，关注{' '}
                {instagramSettings.maxFollowsPerDay}，评论 {instagramSettings.maxCommentsPerDay}
              </Descriptions.Item>
              <Descriptions.Item label="禁用动作">
                {instagramDisabledActions(instagramSettings).join('、') || '无'}
              </Descriptions.Item>
            </>
          ) : (
            <>
              <Descriptions.Item label="FYP 时长">
                {fypSettings.fypBrowseMinutes[0]} - {fypSettings.fypBrowseMinutes[1]} 分钟
              </Descriptions.Item>
              <Descriptions.Item label="点赞概率">{formatPercent(fypSettings.likeProbability)}</Descriptions.Item>
              <Descriptions.Item label="关注数">
                {fypSettings.followsPerSession[0]} - {fypSettings.followsPerSession[1]} / session
              </Descriptions.Item>
              <Descriptions.Item label="评论">
                {fypSettings.comment.enabled
                  ? `${fypSettings.comment.commentsPerSession[0]} - ${
                      fypSettings.comment.commentsPerSession[1]
                    } 条，概率 ${formatPercent(fypSettings.comment.probability)}`
                  : '关闭'}
              </Descriptions.Item>
            </>
          )}
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
        taskType: isInstagram ? 'warmup' : 'fyp',
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
  const instagramSettings = normalizeInstagramWarmupSettings(snapshot?.instagramWarmup)
  const taskDisabledReason =
    selectedRunAccounts.length === 0
      ? `没有可执行的 ${currentPlatformDefinition.localeName} 养号账号`
      : undefined

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
              title={isInstagram ? 'Instagram 养号参数' : 'FYP 参数'}
              extra={
                <Button type="primary" icon={<Save size={16} />} loading={saving} onClick={() => void saveSettings()}>
                  保存配置
                </Button>
              }
            >
              <Form
                form={form}
                layout="vertical"
                requiredMark={false}
                initialValues={isInstagram ? DEFAULT_INSTAGRAM_WARMUP_SETTINGS : DEFAULT_FYP_SETTINGS}
              >
                {isInstagram ? (
                  <InstagramWarmupForm noComment={Boolean(instagramNoComment)} />
                ) : (
                  <TikTokFypForm form={form} commentEnabled={Boolean(commentEnabled)} />
                )}
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
                    { value: 'all', label: `全部可执行账号（${runnableAccounts.length}）` },
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
                  <Descriptions.Item label={isInstagram ? '当前养号配置' : '当前 FYP 配置'}>
                    {isInstagram
                      ? `${instagramSettings.duration} 分钟，点赞 ${formatPercent(
                          instagramSettings.likeProb,
                        )}，评论 ${formatPercent(instagramSettings.commentProb)}`
                      : `${fypSettings.fypBrowseMinutes[0]}-${
                          fypSettings.fypBrowseMinutes[1]
                        } 分钟，点赞 ${formatPercent(fypSettings.likeProbability)}`}
                  </Descriptions.Item>
                </Descriptions>
                <Space wrap>
                  <Tooltip title={taskDisabledReason}>
                    <span>
                      <Button
                        type="primary"
                        icon={<Play size={16} />}
                        disabled={Boolean(taskDisabledReason)}
                        loading={startingTask}
                        onClick={confirmStart}
                      >
                        {isInstagram ? '启动 Instagram 养号' : '启动 FYP 养号'}
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

function TikTokFypForm({
  form,
  commentEnabled,
}: {
  form: ReturnType<typeof Form.useForm>[0]
  commentEnabled: boolean
}) {
  return (
    <Row gutter={16}>
      <Col xs={24} md={12}>
        <Form.Item label="FYP 浏览时长范围（分钟）" required>
          <Space.Compact block>
            <Form.Item name={['fypBrowseMinutes', 0]} noStyle rules={[{ required: true, message: '请输入最小时长' }]}>
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
            <Form.Item name={['followsPerSession', 0]} noStyle rules={[{ required: true, message: '请输入最小关注数' }]}>
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
                { validator: () => validateFormRange(form, ['comment', 'commentsPerSession'], '评论数量范围') },
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
          <InputNumber min={0} max={1} step={0.05} precision={2} className="full-width" disabled={!commentEnabled} />
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
  )
}

function InstagramWarmupForm({ noComment }: { noComment: boolean }) {
  return (
    <Row gutter={16}>
      <Col xs={24} md={8}>
        <Form.Item
          name="duration"
          label="单次会话时长（分钟）"
          rules={[
            { required: true, message: '请输入会话时长' },
            { type: 'number', min: 1, message: '会话时长必须大于 0' },
          ]}
        >
          <InputNumber min={1} precision={0} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="likeProb" label="点赞概率" rules={probabilityRules('请输入点赞概率')}>
          <InputNumber min={0} max={1} step={0.01} precision={2} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="saveProb" label="收藏概率" rules={probabilityRules('请输入收藏概率')}>
          <InputNumber min={0} max={1} step={0.01} precision={2} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="commentProb" label="评论概率" rules={probabilityRules('请输入评论概率')}>
          <InputNumber min={0} max={1} step={0.05} precision={2} className="full-width" disabled={noComment} />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="activeHours" label="活跃时段" rules={[{ required: true, message: '请输入活跃时段' }]}>
          <Input placeholder="7-9,12-14,18-23" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="sessionsPerDay" label="每日会话次数" rules={[{ required: true, message: '请输入每日会话次数' }]}>
          <Input placeholder="1-3" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="restDayProb" label="休息日概率" rules={probabilityRules('请输入休息日概率')}>
          <InputNumber min={0} max={1} step={0.05} precision={2} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="minSessionGapMinutes" label="最小会话间隔（分钟）">
          <InputNumber min={0} precision={0} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="durationJitter" label="时长随机倍率" rules={[{ required: true, message: '请输入时长随机倍率' }]}>
          <Input placeholder="0.5-1.5" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="blockCooldownHours" label="风控冷却（小时）">
          <InputNumber min={0} precision={0} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="roundSkipProb" label="轮次随机跳过概率" rules={probabilityRules('请输入随机跳过概率')}>
          <InputNumber min={0} max={1} step={0.05} precision={2} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="maxLikesPerDay" label="24h 点赞上限">
          <InputNumber min={0} precision={0} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="maxSavesPerDay" label="24h 收藏上限">
          <InputNumber min={0} precision={0} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="maxFollowsPerDay" label="24h 关注上限">
          <InputNumber min={0} precision={0} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="maxLikesPerSession" label="单次点赞上限">
          <InputNumber min={0} precision={0} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="maxCommentsPerDay" label="24h 评论上限">
          <InputNumber min={0} precision={0} className="full-width" disabled={noComment} />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="maxCommentsPerSession" label="单次评论上限">
          <InputNumber min={0} precision={0} className="full-width" disabled={noComment} />
        </Form.Item>
      </Col>
      <Col xs={24}>
        <Space size={[16, 8]} wrap>
          <Form.Item name="requireProxy" valuePropName="checked" className="task-inline-switch">
            <Switch checkedChildren="要求代理" unCheckedChildren="不强制代理" />
          </Form.Item>
          <Form.Item name="onePerWindow" valuePropName="checked" className="task-inline-switch">
            <Switch checkedChildren="单窗口一次" unCheckedChildren="允许多次" />
          </Form.Item>
          <Form.Item name="noLike" valuePropName="checked" className="task-inline-switch">
            <Switch checkedChildren="禁赞" unCheckedChildren="点赞" />
          </Form.Item>
          <Form.Item name="noSave" valuePropName="checked" className="task-inline-switch">
            <Switch checkedChildren="禁收藏" unCheckedChildren="收藏" />
          </Form.Item>
          <Form.Item name="noComment" valuePropName="checked" className="task-inline-switch">
            <Switch checkedChildren="禁评论" unCheckedChildren="评论" />
          </Form.Item>
          <Form.Item name="noFollow" valuePropName="checked" className="task-inline-switch">
            <Switch checkedChildren="禁关注" unCheckedChildren="关注" />
          </Form.Item>
          <Form.Item name="noStories" valuePropName="checked" className="task-inline-switch">
            <Switch checkedChildren="禁快拍" unCheckedChildren="快拍" />
          </Form.Item>
          <Form.Item name="noReels" valuePropName="checked" className="task-inline-switch">
            <Switch checkedChildren="禁 Reels" unCheckedChildren="Reels" />
          </Form.Item>
          <Form.Item name="noExplore" valuePropName="checked" className="task-inline-switch">
            <Switch checkedChildren="禁发现页" unCheckedChildren="发现页" />
          </Form.Item>
        </Space>
      </Col>
    </Row>
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

function normalizeInstagramWarmupSettings(settings?: Partial<InstagramWarmupSettings>): InstagramWarmupSettings {
  return {
    duration: normalizeInteger(settings?.duration, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.duration),
    likeProb: normalizeProbability(settings?.likeProb, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.likeProb),
    saveProb: normalizeProbability(settings?.saveProb, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.saveProb),
    commentProb: normalizeProbability(settings?.commentProb, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.commentProb),
    activeHours: normalizeText(settings?.activeHours, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.activeHours),
    sessionsPerDay: normalizeText(settings?.sessionsPerDay, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.sessionsPerDay),
    restDayProb: normalizeProbability(settings?.restDayProb, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.restDayProb),
    minSessionGapMinutes: normalizeInteger(
      settings?.minSessionGapMinutes,
      DEFAULT_INSTAGRAM_WARMUP_SETTINGS.minSessionGapMinutes,
    ),
    onePerWindow: Boolean(settings?.onePerWindow ?? DEFAULT_INSTAGRAM_WARMUP_SETTINGS.onePerWindow),
    durationJitter: normalizeText(settings?.durationJitter, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.durationJitter),
    maxLikesPerDay: normalizeInteger(settings?.maxLikesPerDay, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.maxLikesPerDay),
    maxSavesPerDay: normalizeInteger(settings?.maxSavesPerDay, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.maxSavesPerDay),
    maxFollowsPerDay: normalizeInteger(settings?.maxFollowsPerDay, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.maxFollowsPerDay),
    maxLikesPerSession: normalizeInteger(
      settings?.maxLikesPerSession,
      DEFAULT_INSTAGRAM_WARMUP_SETTINGS.maxLikesPerSession,
    ),
    maxCommentsPerDay: normalizeInteger(
      settings?.maxCommentsPerDay,
      DEFAULT_INSTAGRAM_WARMUP_SETTINGS.maxCommentsPerDay,
    ),
    maxCommentsPerSession: normalizeInteger(
      settings?.maxCommentsPerSession,
      DEFAULT_INSTAGRAM_WARMUP_SETTINGS.maxCommentsPerSession,
    ),
    blockCooldownHours: normalizeInteger(
      settings?.blockCooldownHours,
      DEFAULT_INSTAGRAM_WARMUP_SETTINGS.blockCooldownHours,
    ),
    roundSkipProb: normalizeProbability(settings?.roundSkipProb, DEFAULT_INSTAGRAM_WARMUP_SETTINGS.roundSkipProb),
    requireProxy: Boolean(settings?.requireProxy ?? DEFAULT_INSTAGRAM_WARMUP_SETTINGS.requireProxy),
    noLike: Boolean(settings?.noLike ?? DEFAULT_INSTAGRAM_WARMUP_SETTINGS.noLike),
    noSave: Boolean(settings?.noSave ?? DEFAULT_INSTAGRAM_WARMUP_SETTINGS.noSave),
    noComment: Boolean(settings?.noComment ?? DEFAULT_INSTAGRAM_WARMUP_SETTINGS.noComment),
    noFollow: Boolean(settings?.noFollow ?? DEFAULT_INSTAGRAM_WARMUP_SETTINGS.noFollow),
    noStories: Boolean(settings?.noStories ?? DEFAULT_INSTAGRAM_WARMUP_SETTINGS.noStories),
    noReels: Boolean(settings?.noReels ?? DEFAULT_INSTAGRAM_WARMUP_SETTINGS.noReels),
    noExplore: Boolean(settings?.noExplore ?? DEFAULT_INSTAGRAM_WARMUP_SETTINGS.noExplore),
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

function normalizeInteger(value: unknown, fallback: number) {
  const next = Number(value ?? fallback)
  if (Number.isNaN(next)) {
    return fallback
  }
  return Math.max(0, Math.trunc(next))
}

function normalizeProbability(value: unknown, fallback: number) {
  const next = Number(value ?? fallback)
  if (Number.isNaN(next)) {
    return fallback
  }
  return Math.min(1, Math.max(0, next))
}

function normalizeText(value: unknown, fallback: string) {
  const next = String(value ?? '').trim()
  return next || fallback
}

function probabilityRules(messageText: string) {
  return [
    { required: true, message: messageText },
    { type: 'number' as const, min: 0, max: 1, message: '概率必须在 0 到 1 之间' },
  ]
}

function validateFormRange(
  form: ReturnType<typeof Form.useForm>[0],
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

function instagramDisabledActions(settings: InstagramWarmupSettings) {
  return [
    settings.noLike ? '点赞' : '',
    settings.noSave ? '收藏' : '',
    settings.noComment ? '评论' : '',
    settings.noFollow ? '关注' : '',
    settings.noStories ? '快拍' : '',
    settings.noReels ? 'Reels' : '',
    settings.noExplore ? '发现页' : '',
  ].filter(Boolean)
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
