import {
  Alert,
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
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { MessageCircle, MousePointerClick, Play, RefreshCw, Search } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageHeader } from '../components/PageHeader'
import { ProcessOutputPanel } from '../components/ProcessOutputPanel'
import { StatusTag } from '../components/StatusTag'
import { AccountBrowserEnvironment } from '../components/AccountBrowserEnvironment'
import {
  diagnoseAccountBrowser,
  getCurrentRunStatus,
  getStderrChunk,
  getStdoutChunk,
  loadConfig,
  runPythonScript,
} from '../services/api'
import { getAutomaticExecutionDisabledReason, getPlatformLabel, isExecutablePlatform, PLATFORMS } from '../services/platforms'
import type { Account, AccountBrowserDiagnosis, BrowserProviderId, Platform, ProcessStatus, ProviderDiagnosticCheck } from '../services/types'

interface LikeFormValues {
  accountId: string
}

interface CommentFormValues {
  accountId: string
  minComments: number
  maxScroll: number
  noPost: boolean
}

interface LikeAttempt {
  strategy: string
  before: string
  after: string
  changed: boolean
  click: string
}

interface CommentScanRow {
  index: number
  commentCount: string
}

const DEFAULT_COMMENT: CommentFormValues = {
  accountId: '',
  minComments: 1000,
  maxScroll: 20,
  noPost: true,
}

export function DiagnosticPage() {
  const [likeForm] = Form.useForm<LikeFormValues>()
  const [commentForm] = Form.useForm<CommentFormValues>()
  const [selectedPlatform, setSelectedPlatform] = useState<Platform>('tiktok')
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [diagnosingBrowser, setDiagnosingBrowser] = useState(false)
  const [browserDiagnosticAccountId, setBrowserDiagnosticAccountId] = useState<string>()
  const [browserDiagnosis, setBrowserDiagnosis] = useState<AccountBrowserDiagnosis | null>(null)

  const accountOptions = useMemo(
    () =>
      accounts.filter((account) => account.platform === selectedPlatform).map((account) => ({
        value: account.id,
        label: `${account.id} | ${formatBrowserProvider(resolveBrowserProvider(account))}${account.enabled ? '' : '（停用）'}`,
        disabled: Boolean(accountDiagnosticDisabledReason(account)),
      })),
    [accounts, selectedPlatform],
  )
  const browserDiagnosticAccount = useMemo(
    () => accounts.find((account) => account.id === browserDiagnosticAccountId),
    [accounts, browserDiagnosticAccountId],
  )
  const selectedPlatformExecutable = isExecutablePlatform(selectedPlatform)
  const diagnosticDisabledReason = selectedPlatformExecutable
    ? undefined
    : getAutomaticExecutionDisabledReason(selectedPlatform, 'diagnostics')

  const refreshConfig = useCallback(async () => {
    setLoading(true)
    try {
      const snapshot = await loadConfig()
      setAccounts(snapshot.accounts)
      const first = snapshot.accounts.find(
        (account) => account.platform === selectedPlatform && !accountDiagnosticDisabledReason(account),
      )
      if (first) {
        likeForm.setFieldsValue({
          accountId: accountCanRunDiagnostics(likeForm.getFieldValue('accountId'), snapshot.accounts, selectedPlatform)
            ? likeForm.getFieldValue('accountId')
            : first.id,
        })
        commentForm.setFieldsValue({
          ...DEFAULT_COMMENT,
          ...commentForm.getFieldsValue(),
          accountId: accountCanRunDiagnostics(commentForm.getFieldValue('accountId'), snapshot.accounts, selectedPlatform)
            ? commentForm.getFieldValue('accountId')
            : first.id,
        })
        setBrowserDiagnosticAccountId((current) =>
          accountCanRunDiagnostics(current, snapshot.accounts, selectedPlatform) ? current : first.id,
        )
      } else {
        likeForm.setFieldsValue({ accountId: undefined })
        commentForm.setFieldsValue({ ...DEFAULT_COMMENT, ...commentForm.getFieldsValue(), accountId: undefined })
        setBrowserDiagnosticAccountId(undefined)
      }
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setLoading(false)
    }
  }, [commentForm, likeForm, selectedPlatform])

  useEffect(() => {
    void refreshConfig()
  }, [refreshConfig])

  const updateSelectedPlatform = (platform: Platform) => {
    setSelectedPlatform(platform)
    likeForm.setFieldsValue({ accountId: undefined })
    commentForm.setFieldsValue({ accountId: undefined })
    setBrowserDiagnosticAccountId(undefined)
    setBrowserDiagnosis(null)
  }

  const runBrowserDiagnosis = async () => {
    if (!browserDiagnosticAccountId) {
      message.warning('请选择账号')
      return
    }
    setDiagnosingBrowser(true)
    try {
      const diagnosis = await diagnoseAccountBrowser(browserDiagnosticAccountId)
      setBrowserDiagnosis(diagnosis)
      message.success('浏览器环境诊断已完成')
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setDiagnosingBrowser(false)
    }
  }

  const runLike = async () => {
    const values = await likeForm.validateFields()
    setStarting(true)
    try {
      const result = await runPythonScript({
        scriptName: 'test_like.py',
        args: ['--account', values.accountId],
        mode: 'diagnostic',
      })
      message.success(`点赞诊断已启动，PID ${result.processId ?? '-'}`)
    } catch (error) {
      message.error(formatError(error))
    } finally {
      setStarting(false)
    }
  }

  const runComment = async () => {
    const values = await commentForm.validateFields()
    const args = [
      '--account',
      values.accountId,
      '--min',
      String(values.minComments),
      '--max-scroll',
      String(values.maxScroll),
    ]
    if (values.noPost) {
      args.push('--no-post')
    }

    const start = async () => {
      setStarting(true)
      try {
        const result = await runPythonScript({
          scriptName: 'test_comment.py',
          args,
          mode: 'diagnostic',
        })
        message.success(`评论诊断已启动，PID ${result.processId ?? '-'}`)
      } catch (error) {
        message.error(formatError(error))
        throw error
      } finally {
        setStarting(false)
      }
    }

    if (values.noPost) {
      await start()
      return
    }

    Modal.confirm({
      title: '确认发布测试评论',
      okText: '确认发布',
      cancelText: '取消',
      width: 560,
      content: (
        <Descriptions size="small" column={1} bordered style={{ marginTop: 12 }}>
          <Descriptions.Item label="账号">{values.accountId}</Descriptions.Item>
          <Descriptions.Item label="扫描阈值">评论数 &gt; {values.minComments}</Descriptions.Item>
          <Descriptions.Item label="最大滚动">{values.maxScroll}</Descriptions.Item>
          <Descriptions.Item label="行为">会尝试发布脚本内置测试评论</Descriptions.Item>
        </Descriptions>
      ),
      onOk: start,
    })
  }

  return (
    <>
      <PageHeader
        title="诊断工具"
        description="运行点赞和评论诊断脚本，辅助定位按钮状态、选择器和发布流程。"
        extra={
          <Button icon={<RefreshCw size={16} />} loading={loading} onClick={() => void refreshConfig()}>
            刷新账号
          </Button>
        }
      />

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Alert
            showIcon
            type="info"
            message="诊断脚本会打开或接管对应账号的浏览器环境"
            description="点赞诊断会测试三种点击策略；评论诊断默认只定位并输出 HTML，关闭 no_post 后才会发布脚本内置测试评论。内置 Chromium 账号会按账号配置启动并检测 CDP。"
          />
        </Col>

        <Col span={24}>
          <Card>
            <Space wrap size={12}>
              <Typography.Text type="secondary">诊断平台</Typography.Text>
              <Select<Platform>
                value={selectedPlatform}
                options={PLATFORMS.map((platform) => ({
                  value: platform.id,
                  label: `${platform.localeName}${isExecutablePlatform(platform.id) ? '' : '（自动执行未接入）'}`,
                }))}
                style={{ width: 220 }}
                onChange={updateSelectedPlatform}
              />
              <StatusTag
                status={selectedPlatformExecutable ? 'ok' : 'warning'}
                label={selectedPlatformExecutable ? '可运行诊断脚本' : '诊断脚本未接入'}
              />
              <Typography.Text type="secondary">
                当前账号选项只展示 {getPlatformLabel(selectedPlatform)}。
              </Typography.Text>
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Space direction="vertical" size={16} className="full-width">
            <Card
              title="浏览器环境诊断"
              extra={
                <Tooltip title={browserDiagnosticAccount ? accountDiagnosticDisabledReason(browserDiagnosticAccount) : diagnosticDisabledReason}>
                  <span>
                    <Button
                      icon={<Search size={16} />}
                      loading={diagnosingBrowser}
                      disabled={Boolean(diagnosticDisabledReason || (browserDiagnosticAccount && accountDiagnosticDisabledReason(browserDiagnosticAccount)))}
                      onClick={() => void runBrowserDiagnosis()}
                    >
                      运行环境诊断
                    </Button>
                  </span>
                </Tooltip>
              }
            >
              <Space direction="vertical" size={12} className="full-width">
                <Select
                  showSearch
                  value={browserDiagnosticAccountId}
                  options={accountOptions}
                  placeholder={`选择 ${getPlatformLabel(selectedPlatform)} 启用账号`}
                  onChange={(accountId) => {
                    setBrowserDiagnosticAccountId(accountId)
                    setBrowserDiagnosis(null)
                  }}
                />
                <Descriptions size="small" column={1} bordered>
                  <Descriptions.Item label="浏览器环境">
                    {browserDiagnosticAccount ? (
                      <AccountBrowserEnvironment accounts={[browserDiagnosticAccount]} />
                    ) : (
                      <Typography.Text type="secondary">请选择账号</Typography.Text>
                    )}
                  </Descriptions.Item>
                </Descriptions>
                <BrowserDiagnosisResult diagnosis={browserDiagnosis} />
              </Space>
            </Card>

            <Card
              title="点赞诊断"
              extra={
                <Tooltip title={diagnosticDisabledReason}>
                  <span>
                    <Button
                      type="primary"
                      icon={<MousePointerClick size={16} />}
                      loading={starting}
                      disabled={Boolean(diagnosticDisabledReason)}
                      onClick={() => void runLike()}
                    >
                      运行点赞诊断
                    </Button>
                  </span>
                </Tooltip>
              }
            >
              <Form form={likeForm} layout="vertical" requiredMark={false}>
                <Form.Item name="accountId" label="账号" rules={[{ required: true, message: '请选择账号' }]}>
                  <Select showSearch options={accountOptions} placeholder={`选择 ${getPlatformLabel(selectedPlatform)} 启用账号`} />
                </Form.Item>
              </Form>
            </Card>

            <Card
              title="评论诊断"
              extra={
                <Tooltip title={diagnosticDisabledReason}>
                  <span>
                    <Button
                      type="primary"
                      icon={<MessageCircle size={16} />}
                      loading={starting}
                      disabled={Boolean(diagnosticDisabledReason)}
                      onClick={() => void runComment()}
                    >
                      运行评论诊断
                    </Button>
                  </span>
                </Tooltip>
              }
            >
              <Form form={commentForm} layout="vertical" requiredMark={false} initialValues={DEFAULT_COMMENT}>
                <Form.Item name="accountId" label="账号" rules={[{ required: true, message: '请选择账号' }]}>
                  <Select showSearch options={accountOptions} placeholder={`选择 ${getPlatformLabel(selectedPlatform)} 启用账号`} />
                </Form.Item>
                <Row gutter={12}>
                  <Col xs={24} md={12}>
                    <Form.Item name="minComments" label="min_comments" rules={[{ required: true, message: '请输入阈值' }]}>
                      <InputNumber min={0} precision={0} className="full-width" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="maxScroll" label="max_scroll" rules={[{ required: true, message: '请输入最大滚动次数' }]}>
                      <InputNumber min={1} max={200} precision={0} className="full-width" />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item name="noPost" label="只定位不发布" valuePropName="checked">
                  <Switch checkedChildren="no_post" unCheckedChildren="发布测试评论" />
                </Form.Item>
              </Form>
            </Card>
          </Space>
        </Col>

        <Col xs={24} xl={14}>
          <DiagnosticSummary />
        </Col>

        <Col span={24}>
          <ProcessOutputPanel title="诊断脚本输出" />
        </Col>
      </Row>
    </>
  )
}

function DiagnosticSummary() {
  const [status, setStatus] = useState<ProcessStatus | null>(null)
  const [stdoutOffset, setStdoutOffset] = useState(0)
  const [stderrOffset, setStderrOffset] = useState(0)
  const [output, setOutput] = useState('')

  const refresh = useCallback(async () => {
    const nextStatus = await getCurrentRunStatus()
    setStatus((current) => {
      if (current?.processId !== nextStatus.processId) {
        setStdoutOffset(0)
        setStderrOffset(0)
        setOutput('')
      }
      return nextStatus
    })

    const [stdout, stderr] = await Promise.all([
      getStdoutChunk(stdoutOffset),
      getStderrChunk(stderrOffset),
    ])
    setStdoutOffset(stdout.nextOffset)
    setStderrOffset(stderr.nextOffset)
    if (stdout.content || stderr.content) {
      setOutput((current) => `${current}${stdout.content}${stderr.content}`.slice(-20000))
    }
  }, [stderrOffset, stdoutOffset])

  useEffect(() => {
    void refresh().catch(() => undefined)
    const timer = window.setInterval(() => {
      void refresh().catch(() => undefined)
    }, 1600)
    return () => window.clearInterval(timer)
  }, [refresh])

  const kind = detectDiagnosticKind(status, output)
  const likeAttempts = parseLikeAttempts(output)
  const commentRows = parseCommentScans(output)
  const commentSummary = parseCommentSummary(output)

  return (
    <Card
      title="诊断摘要"
      extra={
        <Button icon={<Search size={16} />} onClick={() => void refresh()}>
          刷新
        </Button>
      }
    >
      <Space direction="vertical" size={14} className="full-width">
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="任务">{kind}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <StatusTag status={statusTone(status)} label={status?.status ?? 'idle'} />
          </Descriptions.Item>
          <Descriptions.Item label="PID">{status?.processId ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="账号">{extractAccount(status) ?? '-'}</Descriptions.Item>
        </Descriptions>

        {status?.error ? <Alert type="error" showIcon message={status.error} /> : null}

        {kind === '点赞诊断' ? (
          <LikeSummary attempts={likeAttempts} output={output} />
        ) : (
          <CommentSummary rows={commentRows} summary={commentSummary} output={output} />
        )}
      </Space>
    </Card>
  )
}

function BrowserDiagnosisResult({ diagnosis }: { diagnosis: AccountBrowserDiagnosis | null }) {
  if (!diagnosis) {
    return (
      <Alert
        showIcon
        type="info"
        message="等待浏览器环境诊断"
        description="会检查账号 provider、可执行文件、代理、用户数据目录和已有 CDP 运行记录。"
      />
    )
  }

  return (
    <Space direction="vertical" size={12} className="full-width">
      <Descriptions size="small" column={2} bordered>
        <Descriptions.Item label="账号">{diagnosis.accountId}</Descriptions.Item>
        <Descriptions.Item label="provider">{formatBrowserProvider(diagnosis.provider)}</Descriptions.Item>
        <Descriptions.Item label="总体状态">
          <StatusTag status={diagnosis.status === 'error' ? 'error' : diagnosis.status === 'warning' ? 'warning' : 'ok'} label={diagnosis.status} />
        </Descriptions.Item>
      </Descriptions>
      <Table
        rowKey="name"
        size="small"
        columns={browserDiagnosisColumns}
        dataSource={diagnosis.checks}
        pagination={false}
        scroll={{ x: 820 }}
      />
    </Space>
  )
}

function LikeSummary({ attempts, output }: { attempts: LikeAttempt[]; output: string }) {
  const changed = attempts.filter((attempt) => attempt.changed).length
  return (
    <Space direction="vertical" size={12} className="full-width">
      <Alert
        showIcon
        type={changed ? 'success' : attempts.length ? 'warning' : 'info'}
        message={attempts.length ? `已识别 ${attempts.length} 个策略，${changed} 个发生状态变化` : '等待点赞诊断输出'}
        description={output.includes('no active like button') ? '当前可视视频没有找到 Like 按钮，请查看 stdout 定位页面状态。' : 'Before/After 状态来自 test_like.py 输出。'}
      />
      <Table
        rowKey="strategy"
        size="small"
        columns={likeColumns}
        dataSource={attempts}
        pagination={false}
        scroll={{ x: 760 }}
      />
    </Space>
  )
}

function CommentSummary({
  rows,
  summary,
  output,
}: {
  rows: CommentScanRow[]
  summary: ReturnType<typeof parseCommentSummary>
  output: string
}) {
  return (
    <Space direction="vertical" size={12} className="full-width">
      <Alert
        showIcon
        type={summary.posted ? 'success' : summary.failed ? 'error' : summary.located ? 'info' : 'warning'}
        message={summary.message}
        description={summary.description}
      />
      <Descriptions size="small" column={2} bordered>
        <Descriptions.Item label="扫描视频数">{rows.length || '-'}</Descriptions.Item>
        <Descriptions.Item label="最高评论数">{maxCommentCount(rows)}</Descriptions.Item>
        <Descriptions.Item label="comment-input">{output.includes('[comment-input wrapper]') ? '已输出' : '-'}</Descriptions.Item>
        <Descriptions.Item label="post button">{output.includes('[comment-post button]') ? '已输出' : '-'}</Descriptions.Item>
      </Descriptions>
      <Table
        rowKey="index"
        size="small"
        columns={commentScanColumns}
        dataSource={rows.slice(-8)}
        pagination={false}
      />
    </Space>
  )
}

const likeColumns: ColumnsType<LikeAttempt> = [
  { title: '策略', dataIndex: 'strategy', width: 220 },
  {
    title: '结果',
    dataIndex: 'changed',
    width: 120,
    render: (changed: boolean) => <Tag color={changed ? 'green' : 'gold'}>{changed ? 'STATE CHANGED' : 'NO CHANGE'}</Tag>,
  },
  { title: '点击', dataIndex: 'click', width: 180, ellipsis: true },
  { title: 'Before', dataIndex: 'before', ellipsis: true },
  { title: 'After', dataIndex: 'after', ellipsis: true },
]

const commentScanColumns: ColumnsType<CommentScanRow> = [
  { title: '视频序号', dataIndex: 'index', width: 110 },
  { title: 'comment_count', dataIndex: 'commentCount' },
]

const browserDiagnosisColumns: ColumnsType<ProviderDiagnosticCheck> = [
  { title: '检查项', dataIndex: 'name', width: 190 },
  {
    title: '状态',
    dataIndex: 'status',
    width: 120,
    render: (status: ProviderDiagnosticCheck['status']) => (
      <Tag color={status === 'ok' ? 'green' : status === 'warning' ? 'gold' : 'red'}>{status}</Tag>
    ),
  },
  { title: '详情', dataIndex: 'detail', ellipsis: true },
]

function parseLikeAttempts(output: string): LikeAttempt[] {
  const sections = output.split(/\n=== Strategy /).slice(1)
  return sections.map((section) => {
    const firstLine = section.split('\n', 1)[0]?.trim() ?? '-'
    return {
      strategy: firstLine.replace(/ ===$/, ''),
      before: matchLine(section, /^\s*Before:\s*(.+)$/m) ?? '-',
      after: matchLine(section, /^\s*After:\s*(.+)$/m) ?? '-',
      click: matchLine(section, /^\s*Click:\s*(.+)$/m) ?? '-',
      changed: section.includes('STATE CHANGED'),
    }
  })
}

function parseCommentScans(output: string): CommentScanRow[] {
  return Array.from(output.matchAll(/video\s+(\d+):\s+comment_count\s+=\s+([^\n]+)/g)).map((match) => ({
    index: Number(match[1]),
    commentCount: match[2].trim(),
  }))
}

function parseCommentSummary(output: string) {
  if (output.includes('LIKELY POSTED')) {
    return {
      posted: true,
      failed: false,
      located: true,
      message: '测试评论可能已发布',
      description: '脚本检测到输入框已清空，请在面板或账号资料页人工确认。',
    }
  }
  if (output.includes('--no-post set')) {
    return {
      posted: false,
      failed: false,
      located: true,
      message: '已完成定位，未发布评论',
      description: '已输出右侧栏、评论输入框和发布按钮 HTML。',
    }
  }
  if (output.includes('NOT POSTED') || output.includes('[FAIL]')) {
    return {
      posted: false,
      failed: true,
      located: output.includes('Comment panel HTML'),
      message: '评论诊断失败或未发布',
      description: '请查看 HTML 和 stderr，重点检查 comment-count、comment-input 和 comment-post 选择器。',
    }
  }
  if (output.includes('Comment panel HTML') || output.includes('Right-rail HTML')) {
    return {
      posted: false,
      failed: false,
      located: true,
      message: '已输出选择器 HTML',
      description: '页面已定位到诊断所需元素，继续查看输入框和发布按钮状态。',
    }
  }
  return {
    posted: false,
    failed: false,
    located: false,
    message: '等待评论诊断输出',
    description: '运行后会展示扫描视频数、评论数、选择器 HTML、输入框定位和发布结果。',
  }
}

function detectDiagnosticKind(status: ProcessStatus | null, output: string) {
  if (status?.command.includes('src/test_like.py') || output.includes('Strategy A:')) {
    return '点赞诊断'
  }
  if (status?.command.includes('src/test_comment.py') || output.includes('Scanning for a video')) {
    return '评论诊断'
  }
  return status?.taskType === 'diagnostic' ? '诊断任务' : '无诊断任务'
}

function extractAccount(status: ProcessStatus | null) {
  const command = status?.command ?? []
  const index = command.indexOf('--account')
  return index >= 0 ? command[index + 1] : status?.accountId
}

function matchLine(value: string, pattern: RegExp) {
  return value.match(pattern)?.[1]?.trim()
}

function maxCommentCount(rows: CommentScanRow[]) {
  const values = rows
    .map((row) => Number(row.commentCount))
    .filter((value) => Number.isFinite(value))
  return values.length ? Math.max(...values) : '-'
}

function statusTone(status: ProcessStatus | null) {
  if (!status || status.status === 'idle' || status.status === 'completed') {
    return 'idle'
  }
  if (status.status === 'running' || status.status === 'starting') {
    return 'running'
  }
  if (status.status === 'failed' || status.status === 'partial_failed') {
    return 'error'
  }
  return 'warning'
}

function accountCanRunDiagnostics(accountId: string | undefined, accounts: Account[], platform: Platform) {
  return Boolean(
    accountId &&
      accounts.some(
        (account) => account.id === accountId && account.platform === platform && !accountDiagnosticDisabledReason(account),
      ),
  )
}

function accountDiagnosticDisabledReason(account: Account) {
  if (!account.enabled) {
    return `${account.id} 已停用`
  }
  if (!isExecutablePlatform(account.platform)) {
    return getAutomaticExecutionDisabledReason(account.platform, 'diagnostics')
  }
  if (resolveBrowserProvider(account) === 'bitbrowser' && !account.bitbrowserProfileId && !account.browser?.profileId) {
    return `${account.id} 未绑定 BitBrowser profile`
  }
  return undefined
}

function resolveBrowserProvider(account: Account): BrowserProviderId {
  return account.browserProvider ?? account.browser?.provider ?? 'bitbrowser'
}

function formatBrowserProvider(provider: BrowserProviderId) {
  const labels: Record<BrowserProviderId, string> = {
    bitbrowser: 'BitBrowser',
    builtin_chromium: '内置 Chromium',
  }
  return labels[provider]
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
