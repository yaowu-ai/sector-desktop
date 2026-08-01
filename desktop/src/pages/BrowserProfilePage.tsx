import {
  Alert,
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
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  CheckCircle2,
  Copy,
  FolderSync,
  PlugZap,
  Power,
  PowerOff,
  RefreshCw,
  ShieldCheck,
  Stethoscope,
  Trash2,
  Upload,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'

import { BrowserPreviewModal } from '../components/BrowserPreviewModal'
import { confirmDanger } from '../components/ConfirmDanger'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { StatusTag } from '../components/StatusTag'
import { usePlatformContext } from '../app/PlatformContext'
import { useBrowserPreview } from '../hooks/useBrowserPreview'
import {
  checkBitbrowserApi,
  checkProxy,
  closeProfile,
  createBatchBrowserProfiles,
  cleanupBuiltinChromiumData,
  createSingleBrowserProfile,
  diagnoseAccountBrowser,
  getBuiltinChromiumStatus,
  listBrowserProfiles,
  loadAccounts,
  openBitbrowserDownloadPage,
  openProfile,
  syncAccountsApply,
  syncAccountsDryRun,
} from '../services/api'
import { getPlatformLabel, PLATFORMS } from '../services/platforms'
import type {
  AccountSummary,
  AccountBrowserDiagnosis,
  ApiStatus,
  BatchCreateProfileResult,
  BrowserProfile,
  BrowserProviderId,
  BuiltinChromiumCleanupResult,
  BuiltinChromiumStatus,
  CreateProfileRequest,
  Platform,
  ProxyCheckRequest,
  ProxyCheckResult,
  SyncAccountsRequest,
  SyncPreview,
} from '../services/types'

type ProxyType = 'http' | 'https' | 'socks5'

interface SingleCreateForm {
  name: string
  proxyType: ProxyType
  proxy: string
  groupId?: string
  skipProxyCheck: boolean
  allowUsedProxy: boolean
}

interface BatchCreateForm {
  platform: Platform
  prefix: string
  proxyType: ProxyType
  proxiesText: string
  groupId?: string
  skipProxyCheck: boolean
  skipUsed: boolean
}

interface SyncForm {
  platform: Platform
  prefix: string
  start: number
  end: number
  morningStart: number
  morningEnd: number
  eveningStart: number
  eveningEnd: number
  firstIpGroup: number
}

export function BrowserProfilePage() {
  const { currentPlatform } = usePlatformContext()
  const [singleForm] = Form.useForm<SingleCreateForm>()
  const [batchForm] = Form.useForm<BatchCreateForm>()
  const [syncForm] = Form.useForm<SyncForm>()
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null)
  const [chromiumStatus, setChromiumStatus] = useState<BuiltinChromiumStatus | null>(null)
  const [accounts, setAccounts] = useState<AccountSummary[]>([])
  const [profiles, setProfiles] = useState<BrowserProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [operatingProfileId, setOperatingProfileId] = useState<string>()
  const [proxyChecking, setProxyChecking] = useState(false)
  const [proxyResult, setProxyResult] = useState<ProxyCheckResult | null>(null)
  const [singleCreating, setSingleCreating] = useState(false)
  const [batchCreating, setBatchCreating] = useState(false)
  const [batchResult, setBatchResult] = useState<BatchCreateProfileResult | null>(null)
  const [syncLoading, setSyncLoading] = useState(false)
  const [syncPreview, setSyncPreview] = useState<SyncPreview | null>(null)
  const [diagnosingAccountId, setDiagnosingAccountId] = useState<string>()
  const [diagnosisResult, setDiagnosisResult] = useState<AccountBrowserDiagnosis | null>(null)
  const [cleaningAccountId, setCleaningAccountId] = useState<string>()
  const browserPreview = useBrowserPreview()

  const scopedProfiles = useMemo(
    () => profiles.filter((profile) => profileMatchesPlatform(profile, currentPlatform)),
    [currentPlatform, profiles],
  )
  const boundCount = useMemo(
    () => scopedProfiles.filter((profile) => profile.boundAccountId).length,
    [scopedProfiles],
  )
  const openedCount = useMemo(
    () => scopedProfiles.filter((profile) => profile.opened).length,
    [scopedProfiles],
  )
  const bitbrowserAccountCount = useMemo(
    () => accounts.filter((account) => effectiveProvider(account) === 'bitbrowser').length,
    [accounts],
  )
  const chromiumAccountCount = useMemo(
    () => accounts.filter((account) => effectiveProvider(account) === 'builtin_chromium').length,
    [accounts],
  )
  const pendingAccountCount = useMemo(() => {
    return accounts.filter((account) => {
      const provider = effectiveProvider(account)
      if (provider === 'bitbrowser' && !account.bitbrowserProfileId && !account.browser?.profileId) {
        return true
      }
      if (provider === 'builtin_chromium' && !chromiumStatus?.available) {
        return true
      }
      return false
    }).length
  }, [accounts, chromiumStatus])
  const chromiumAccounts = useMemo(
    () => accounts.filter((account) => effectiveProvider(account) === 'builtin_chromium'),
    [accounts],
  )

  const refresh = async () => {
    setLoading(true)
    try {
      const [status, chromium] = await Promise.all([
        checkBitbrowserApi(),
        getBuiltinChromiumStatus(),
      ])
      setApiStatus(status)
      setChromiumStatus(chromium)
      const allAccounts = await loadAccounts(currentPlatform).catch(() => [])
      setAccounts(allAccounts)
      if (status.available) {
        setProfiles(await listBrowserProfiles())
      } else {
        setProfiles([])
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    } finally {
      setLoading(false)
    }
  }

  const openBitbrowserDownload = async () => {
    try {
      await openBitbrowserDownloadPage()
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    }
  }

  useEffect(() => {
    singleForm.setFieldsValue({
      proxyType: 'socks5',
      skipProxyCheck: false,
      allowUsedProxy: false,
    })
    batchForm.setFieldsValue({
      platform: currentPlatform,
      prefix: currentPlatform,
      proxyType: 'socks5',
      skipProxyCheck: false,
      skipUsed: true,
    })
    syncForm.setFieldsValue({
      platform: currentPlatform,
      prefix: currentPlatform,
      start: 21,
      end: 50,
      morningStart: 21,
      morningEnd: 35,
      eveningStart: 36,
      eveningEnd: 50,
      firstIpGroup: 11,
    })
    void refresh()
  }, [batchForm, currentPlatform, singleForm, syncForm])

  useEffect(() => {
    batchForm.setFieldsValue({
      platform: currentPlatform,
      prefix: currentPlatform,
    })
    syncForm.setFieldsValue({
      platform: currentPlatform,
      prefix: currentPlatform,
    })
  }, [batchForm, currentPlatform, syncForm])

  const toggleProfile = async (profile: BrowserProfile) => {
    setOperatingProfileId(profile.id)
    try {
      const result = profile.opened ? await closeProfile(profile.id) : await openProfile(profile.id)
      if (!profile.opened && result.opened && result.cdpEndpoint) {
        browserPreview.openBrowserPreview({
          accountId: profile.boundAccountId ?? profile.name,
          profileId: result.profileId,
          cdpEndpoint: result.cdpEndpoint,
          openedAt: new Date().toISOString(),
        })
      }
      message.success(`${profile.name} ${result.opened ? '已打开' : '已关闭'}`)
      await refresh()
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    } finally {
      setOperatingProfileId(undefined)
    }
  }

  const runProxyCheck = async () => {
    const values = await singleForm.validateFields(['proxyType', 'proxy'])
    setProxyChecking(true)
    setProxyResult(null)
    try {
      const request: ProxyCheckRequest = {
        proxyType: values.proxyType,
        proxy: values.proxy,
        checkExists: true,
      }
      setProxyResult(await checkProxy(request))
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    } finally {
      setProxyChecking(false)
    }
  }

  const createSingle = async () => {
    const values = await singleForm.validateFields()
    setSingleCreating(true)
    try {
      const request: CreateProfileRequest = {
        name: values.name,
        proxyType: values.proxyType,
        proxy: values.proxy,
        groupId: values.groupId,
        skipProxyCheck: values.skipProxyCheck,
        allowUsedProxy: values.allowUsedProxy,
      }
      const result = await createSingleBrowserProfile(request)
      message.success(`创建成功：${result.name} -> ${result.profileId}`)
      singleForm.setFieldValue('name', '')
      await refresh()
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    } finally {
      setSingleCreating(false)
    }
  }

  const createBatch = async () => {
    const values = await batchForm.validateFields()
    setBatchCreating(true)
    setBatchResult(null)
    try {
      const { platform: _platform, ...request } = values
      const result = await createBatchBrowserProfiles(request)
      setBatchResult(result)
      message.success(
        `批量完成：成功 ${result.created.length}，跳过 ${result.skipped.length}，失败 ${result.failed.length}`,
      )
      await refresh()
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    } finally {
      setBatchCreating(false)
    }
  }

  const runSyncDryRun = async () => {
    const values = await syncForm.validateFields()
    setSyncLoading(true)
    setSyncPreview(null)
    try {
      const { platform: _platform, ...request } = values
      setSyncPreview(await syncAccountsDryRun(request))
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    } finally {
      setSyncLoading(false)
    }
  }

  const applySync = async () => {
    const values = await syncForm.validateFields()
    confirmDanger({
      title: '写入账号配置',
      content: '将把 dry-run 中可追加的账号写入 accounts.yaml，保存前会自动备份。',
      onOk: () => {
        void (async () => {
    setSyncLoading(true)
    try {
      const { platform: _platform, ...request } = values
      const result = await syncAccountsApply(request)
            setSyncPreview(result.preview)
            message.success(`同步完成，备份：${result.saveResult.backupPath}`)
            await refresh()
          } catch (error) {
            message.error(error instanceof Error ? error.message : String(error))
          } finally {
            setSyncLoading(false)
          }
        })()
      },
    })
  }

  const diagnoseChromiumAccount = async (accountId: string) => {
    setDiagnosingAccountId(accountId)
    setDiagnosisResult(null)
    try {
      const result = await diagnoseAccountBrowser(accountId)
      setDiagnosisResult(result)
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    } finally {
      setDiagnosingAccountId(undefined)
    }
  }

  const cleanupChromiumAccount = (accountId: string) => {
    confirmDanger({
      title: '清理内置 Chromium 数据',
      content: '只会删除该账号在 Account Matrix 内置 Chromium 下的本地用户数据，不会删除 BitBrowser profile。如该账号浏览器正在运行，将先终止进程。',
      onOk: () => {
        void (async () => {
          setCleaningAccountId(accountId)
          try {
            const result = await cleanupBuiltinChromiumData(accountId)
            if (result.removed) {
              message.success(`已清理：${result.userDataDir}`)
            } else {
              message.warning(result.message)
            }
          } catch (error) {
            message.error(error instanceof Error ? error.message : String(error))
          } finally {
            setCleaningAccountId(undefined)
          }
        })()
      },
    })
  }

  const toggleProfileById = async (profileId: string) => {
    const profile = profiles.find((item) => item.id === profileId)
    if (!profile) {
      message.warning('未找到该 BitBrowser profile')
      return
    }
    await toggleProfile(profile)
  }

  const profileColumns: ColumnsType<BrowserProfile> = [
    {
      title: '窗口名称',
      dataIndex: 'name',
      key: 'name',
      fixed: 'left',
      width: 170,
      sorter: (a, b) => a.name.localeCompare(b.name),
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: '窗口 ID',
      dataIndex: 'id',
      key: 'id',
      width: 260,
      render: (id: string) => (
        <Typography.Text copyable={{ text: id }} type="secondary">
          {id}
        </Typography.Text>
      ),
    },
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
      width: 110,
      render: (platform?: BrowserProfile['platform']) =>
        platform ? <Tag>{getPlatformLabel(platform)}</Tag> : '-',
    },
    {
      title: '状态',
      dataIndex: 'opened',
      key: 'opened',
      width: 100,
      filters: [
        { text: '已打开', value: 'true' },
        { text: '未打开', value: 'false' },
      ],
      onFilter: (value, record) => String(record.opened) === value,
      render: (opened: boolean) => (
        <StatusTag status={opened ? 'running' : 'idle'} label={opened ? '已打开' : '未打开'} />
      ),
    },
    {
      title: '绑定账号',
      dataIndex: 'boundAccountId',
      key: 'boundAccountId',
      width: 150,
      render: (value?: string) => (value ? <Tag color="blue">{value}</Tag> : <Tag>未绑定</Tag>),
    },
    {
      title: '代理',
      dataIndex: 'proxy',
      key: 'proxy',
      width: 220,
      ellipsis: true,
      render: (value?: string) => value || '-',
    },
    {
      title: '分组',
      dataIndex: 'groupId',
      key: 'groupId',
      width: 120,
      render: (value?: string) => value || '-',
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 150,
      render: (_, profile) => (
        <Button
          icon={profile.opened ? <PowerOff size={15} /> : <Power size={15} />}
          loading={operatingProfileId === profile.id}
          onClick={() => void toggleProfile(profile)}
        >
          {profile.opened ? '关闭' : '打开'}
        </Button>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title="浏览器环境"
        description="管理 BitBrowser 与内置 Chromium 浏览器环境、账号绑定、代理检测和运行状态。"
        extra={
          <Button icon={<RefreshCw size={16} />} onClick={refresh} loading={loading}>
            刷新
          </Button>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card size="small" title="BitBrowser" extra={<Tag color="green">生产默认推荐</Tag>}>
            <Statistic
              title="API 状态"
              value={apiStatus?.available ? '在线' : '不可用'}
              valueStyle={{ color: apiStatus?.available ? '#16a34a' : '#dc2626', fontSize: 20 }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {apiStatus?.apiUrl ?? '未检测'}
            </Typography.Text>
            <Row gutter={16} style={{ marginTop: 12 }}>
              <Col span={8}>
                <Statistic title="Profile" value={scopedProfiles.length} />
              </Col>
              <Col span={8}>
                <Statistic title="已绑定" value={boundCount} />
              </Col>
              <Col span={8}>
                <Statistic title="已打开" value={openedCount} />
              </Col>
            </Row>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small" title="内置 Chromium" extra={<Tag color="gold">生产可选</Tag>}>
            <Statistic
              title="可用状态"
              value={
                chromiumStatus === null
                  ? '待检测'
                  : chromiumStatus.available
                    ? '可用'
                    : '未检测到'
              }
              valueStyle={{
                color: chromiumStatus?.available ? '#16a34a' : '#d97706',
                fontSize: 20,
              }}
            />
            {chromiumStatus?.available ? (
              <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis copyable={{ text: chromiumStatus.executablePath ?? '' }}>
                {chromiumStatus.executablePath ?? '未知'}
              </Typography.Text>
            ) : (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {chromiumStatus?.error ??
                  '未检测到可用 Chromium，请安装 Chrome/Edge 或手动指定可执行文件。'}
              </Typography.Text>
            )}
            <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
              数据根目录：{chromiumStatus?.dataRoot ?? '-'}
            </Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small" title="账号环境">
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="BitBrowser" value={bitbrowserAccountCount} />
              </Col>
              <Col span={8}>
                <Statistic title="Chromium" value={chromiumAccountCount} />
              </Col>
              <Col span={8}>
                <Statistic
                  title="待处理"
                  value={pendingAccountCount}
                  valueStyle={pendingAccountCount > 0 ? { color: '#d97706' } : undefined}
                />
              </Col>
            </Row>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              待处理含未绑定 profile 或 Chromium 不可用
            </Typography.Text>
          </Card>
        </Col>

        <Col span={24}>
          <Tabs
            items={[
              {
                key: 'profiles',
                label: 'BitBrowser Profile',
                children: (
                  <>
                    {!apiStatus?.available ? (
                      <Alert
                        type="warning"
                        showIcon
                        message="BitBrowser Local API 不可用"
                        description={apiStatus?.error ?? '请确认 BitBrowser 客户端和 Local API 已启动。其他 Tab 不受影响。'}
                        action={
                          <Button type="link" size="small" onClick={() => void openBitbrowserDownload()}>
                            下载 BitBrowser
                          </Button>
                        }
                        style={{ marginBottom: 16 }}
                      />
                    ) : null}
                    <Table
                      rowKey="id"
                      loading={loading}
                      columns={profileColumns}
                      dataSource={scopedProfiles}
                      scroll={{ x: 1380 }}
                      pagination={{ pageSize: 10, showSizeChanger: true }}
                      locale={{
                        emptyText: (
                          <EmptyState
                            title="暂无 BitBrowser Profile"
                            description="可通过批量工具创建并绑定账号。"
                          />
                        ),
                      }}
                    />
                  </>
                ),
              },

              {
                key: 'chromium',
                label: '内置 Chromium',
                children: (
                  <BuiltinChromiumPanel
                    chromiumStatus={chromiumStatus}
                    accounts={chromiumAccounts}
                    diagnosingAccountId={diagnosingAccountId}
                    cleaningAccountId={cleaningAccountId}
                    diagnosisResult={diagnosisResult}
                    onDiagnose={(accountId) => void diagnoseChromiumAccount(accountId)}
                    onCleanup={(accountId) => cleanupChromiumAccount(accountId)}
                    onCloseDiagnosis={() => setDiagnosisResult(null)}
                  />
                ),
              },
              {
                key: 'binding',
                label: '账号绑定',
                children: (
                  <AccountBindingPanel
                    accounts={accounts}
                    chromiumStatus={chromiumStatus}
                    apiStatus={apiStatus}
                    diagnosingAccountId={diagnosingAccountId}
                    cleaningAccountId={cleaningAccountId}
                    diagnosisResult={diagnosisResult}
                    onDiagnose={(accountId) => void diagnoseChromiumAccount(accountId)}
                    onCleanup={(accountId) => cleanupChromiumAccount(accountId)}
                    onCloseDiagnosis={() => setDiagnosisResult(null)}
                    onToggleProfile={(profileId) => void toggleProfileById(profileId)}
                    operatingProfileId={operatingProfileId}
                    profiles={profiles}
                  />
                ),
              },
              {
                key: 'tools',
                label: '批量工具',
                children: (
                  <Space direction="vertical" size={16} className="full-width">
                    <Card title="BitBrowser 单个创建">
                      <SingleCreatePanel
                        form={singleForm}
                        proxyResult={proxyResult}
                        proxyChecking={proxyChecking}
                        creating={singleCreating}
                        onProxyCheck={() => void runProxyCheck()}
                        onCreate={() => void createSingle()}
                      />
                    </Card>
                    <Card title="BitBrowser 批量创建">
                      <BatchCreatePanel
                        form={batchForm}
                        result={batchResult}
                        creating={batchCreating}
                        onCreate={() => void createBatch()}
                      />
                    </Card>
                    <Card title="账号环境同步">
                      <SyncPanel
                        form={syncForm}
                        preview={syncPreview}
                        loading={syncLoading}
                        onDryRun={() => void runSyncDryRun()}
                        onApply={() => void applySync()}
                      />
                    </Card>
                  </Space>
                ),
              },
            ]}
          />
        </Col>
      </Row>
      <BrowserPreviewModal
        open={browserPreview.previewOpen}
        preview={browserPreview.preview}
        onClose={browserPreview.closePreview}
      />
    </>
  )
}

function SingleCreatePanel({
  form,
  proxyResult,
  proxyChecking,
  creating,
  onProxyCheck,
  onCreate,
}: {
  form: ReturnType<typeof Form.useForm<SingleCreateForm>>[0]
  proxyResult: ProxyCheckResult | null
  proxyChecking: boolean
  creating: boolean
  onProxyCheck: () => void
  onCreate: () => void
}) {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={12}>
        <Form form={form} layout="vertical" requiredMark={false}>
          <Form.Item name="name" label="窗口名称" rules={[{ required: true, message: '请输入窗口名称' }]}>
            <Input placeholder="例如 tiktok_26、instagram_26、whatsapp_26、douyin_26" />
          </Form.Item>
          <Form.Item name="proxyType" label="代理协议" rules={[{ required: true }]}>
            <Select options={proxyTypeOptions()} />
          </Form.Item>
          <Form.Item
            name="proxy"
            label="代理"
            rules={[{ required: true, message: '请输入代理' }, { validator: validateProxyFormat }]}
          >
            <Input.Password placeholder="host:port:用户名:密码" />
          </Form.Item>
          <Form.Item name="groupId" label="BitBrowser 分组 ID">
            <Input placeholder="可选" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="skipProxyCheck" valuePropName="checked">
                <Switch checkedChildren="跳过检测" unCheckedChildren="检测代理" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="allowUsedProxy" valuePropName="checked">
                <Switch checkedChildren="允许复用" unCheckedChildren="阻止复用" />
              </Form.Item>
            </Col>
          </Row>
          <Space>
            <Button icon={<ShieldCheck size={16} />} loading={proxyChecking} onClick={onProxyCheck}>
              检测代理
            </Button>
            <Button type="primary" icon={<CheckCircle2 size={16} />} loading={creating} onClick={onCreate}>
              BitBrowser 创建 profile
            </Button>
          </Space>
        </Form>
      </Col>
      <Col xs={24} xl={12}>
        <ResultBox proxyResult={proxyResult} />
      </Col>
    </Row>
  )
}

function BatchCreatePanel({
  form,
  result,
  creating,
  onCreate,
}: {
  form: ReturnType<typeof Form.useForm<BatchCreateForm>>[0]
  result: BatchCreateProfileResult | null
  creating: boolean
  onCreate: () => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const importProxyFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) {
      return
    }

    try {
      const content = await readProxyImportFile(file)
      form.setFieldValue('proxiesText', content)
      const proxyLines = content
        .split(/\r?\n/)
        .filter((line) => {
          const trimmed = line.trim()
          return trimmed && !trimmed.startsWith('#')
        }).length
      message.success(`已导入 ${file.name}，有效代理行 ${proxyLines} 条`)
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Space direction="vertical" size={16} className="full-width">
      <Form form={form} layout="vertical" requiredMark={false}>
        <Row gutter={12}>
          <Col xs={24} md={6}>
            <Form.Item name="platform" label="平台模板" rules={[{ required: true }]}>
              <Select
                disabled
                options={platformOptions()}
                onChange={(platform: Platform) => {
                  form.setFieldValue('prefix', platform)
                }}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item name="prefix" label="窗口前缀" rules={[{ required: true }]}>
              <Input placeholder="tiktok" />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item name="proxyType" label="代理协议" rules={[{ required: true }]}>
              <Select options={proxyTypeOptions()} />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item name="groupId" label="BitBrowser 分组 ID">
              <Input placeholder="可选" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item
          name="proxiesText"
          label={
            <div className="proxy-list-label-block">
              <div>代理列表</div>
              <Space className="proxy-file-import-label" wrap>
                <Button
                  size="small"
                  icon={<Upload size={14} />}
                  onClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    fileInputRef.current?.click()
                  }}
                >
                  导入文件
                </Button>
                <Typography.Text type="secondary">
                  支持 .txt、.csv、.tsv、.log、.docx、.xlsx。
                </Typography.Text>
              </Space>
            </div>
          }
          rules={[{ required: true, message: '请粘贴代理列表' }]}
        >
          <Input.TextArea rows={8} placeholder={'每行一个 host:port:用户名:密码\n空行和 # 注释会被忽略'} />
        </Form.Item>
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.csv,.tsv,.log,.docx,.xlsx,text/plain,text/csv,text/tab-separated-values,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          style={{ display: 'none' }}
          tabIndex={-1}
          onChange={(event) => void importProxyFile(event)}
        />
        <Space wrap>
          <Form.Item name="skipProxyCheck" valuePropName="checked" noStyle>
            <Switch checkedChildren="跳过代理检测" unCheckedChildren="创建前检测代理" />
          </Form.Item>
          <Form.Item name="skipUsed" valuePropName="checked" noStyle>
            <Switch checkedChildren="跳过已使用代理" unCheckedChildren="允许复用代理" />
          </Form.Item>
          <Button type="primary" icon={<PlugZap size={16} />} loading={creating} onClick={onCreate}>
            BitBrowser 批量创建
          </Button>
        </Space>
      </Form>

      {result ? <BatchResult result={result} /> : null}
    </Space>
  )
}

function SyncPanel({
  form,
  preview,
  loading,
  onDryRun,
  onApply,
}: {
  form: ReturnType<typeof Form.useForm<SyncForm>>[0]
  preview: SyncPreview | null
  loading: boolean
  onDryRun: () => void
  onApply: () => void
}) {
  return (
    <Space direction="vertical" size={16} className="full-width">
      <Alert
        type="info"
        showIcon
        message="先 dry-run，再 apply"
        description="同步会按 BitBrowser 精确窗口名生成缺失账号，例如 tiktok_21、instagram_21。apply 写入前会备份 accounts.yaml。"
      />
      <Form form={form} layout="vertical" requiredMark={false}>
        <Row gutter={12}>
          <Col xs={24} md={5}>
            <Form.Item name="platform" label="平台模板" rules={[{ required: true }]}>
              <Select
                disabled
                options={platformOptions()}
                onChange={(platform: Platform) => {
                  form.setFieldValue('prefix', platform)
                }}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={5}>
            <Form.Item name="prefix" label="窗口前缀" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={12} md={2}>
            <Form.Item name="start" label="起始" rules={[{ required: true }]}>
              <InputNumber precision={0} min={1} className="full-width" />
            </Form.Item>
          </Col>
          <Col xs={12} md={2}>
            <Form.Item name="end" label="结束" rules={[{ required: true }]}>
              <InputNumber precision={0} min={1} className="full-width" />
            </Form.Item>
          </Col>
          <Col xs={12} md={2}>
            <Form.Item name="morningStart" label="上午起" rules={[{ required: true }]}>
              <InputNumber precision={0} min={1} className="full-width" />
            </Form.Item>
          </Col>
          <Col xs={12} md={2}>
            <Form.Item name="morningEnd" label="上午止" rules={[{ required: true }]}>
              <InputNumber precision={0} min={1} className="full-width" />
            </Form.Item>
          </Col>
          <Col xs={12} md={2}>
            <Form.Item name="eveningStart" label="晚上起" rules={[{ required: true }]}>
              <InputNumber precision={0} min={1} className="full-width" />
            </Form.Item>
          </Col>
          <Col xs={12} md={2}>
            <Form.Item name="eveningEnd" label="晚上止" rules={[{ required: true }]}>
              <InputNumber precision={0} min={1} className="full-width" />
            </Form.Item>
          </Col>
          <Col xs={24} md={2}>
            <Form.Item name="firstIpGroup" label="首个 IP 组" rules={[{ required: true }]}>
              <InputNumber precision={0} min={1} className="full-width" />
            </Form.Item>
          </Col>
        </Row>
        <Space>
          <Button icon={<FolderSync size={16} />} loading={loading} onClick={onDryRun}>
            dry-run
          </Button>
          <Button
            type="primary"
            disabled={!preview?.canApply || !preview.accountsToAdd.length}
            loading={loading}
            onClick={onApply}
          >
            apply
          </Button>
        </Space>
      </Form>

      {preview ? <SyncPreviewView preview={preview} /> : null}
    </Space>
  )
}

function AccountBindingPanel({
  accounts,
  chromiumStatus,
  apiStatus,
  diagnosingAccountId,
  cleaningAccountId,
  diagnosisResult,
  onDiagnose,
  onCleanup,
  onCloseDiagnosis,
  onToggleProfile,
  operatingProfileId,
  profiles,
}: {
  accounts: AccountSummary[]
  chromiumStatus: BuiltinChromiumStatus | null
  apiStatus: ApiStatus | null
  diagnosingAccountId?: string
  cleaningAccountId?: string
  diagnosisResult: AccountBrowserDiagnosis | null
  onDiagnose: (accountId: string) => void
  onCleanup: (accountId: string) => void
  onCloseDiagnosis: () => void
  onToggleProfile: (profileId: string) => void
  operatingProfileId?: string
  profiles: BrowserProfile[]
}) {
  const profileById = useMemo(() => {
    const map = new Map<string, BrowserProfile>()
    for (const profile of profiles) {
      map.set(profile.id, profile)
    }
    return map
  }, [profiles])

  const columns: ColumnsType<AccountSummary> = [
    {
      title: '账号',
      dataIndex: 'id',
      key: 'id',
      fixed: 'left',
      width: 150,
      render: (id: string) => <Typography.Text strong>{id}</Typography.Text>,
    },
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
      width: 100,
      render: (platform: Platform) => <Tag>{getPlatformLabel(platform)}</Tag>,
    },
    {
      title: '浏览器提供方',
      key: 'provider',
      width: 130,
      render: (_, account) => {
        const provider = effectiveProvider(account)
        return provider === 'bitbrowser' ? (
          <Tag color="green">BitBrowser</Tag>
        ) : (
          <Tag color="gold">内置 Chromium</Tag>
        )
      },
    },
    {
      title: '环境标识',
      key: 'envId',
      width: 220,
      ellipsis: true,
      render: (_, account) => {
        const provider = effectiveProvider(account)
        if (provider === 'bitbrowser') {
          const profileId = account.bitbrowserProfileId ?? account.browser?.profileId
          if (profileId) {
            return (
              <Typography.Text copyable={{ text: profileId }} type="secondary">
                {profileId}
              </Typography.Text>
            )
          }
          return <Tag color="orange">待绑定</Tag>
        }
        // 内置 Chromium: show user-data-dir, do NOT show missing profile_id error
        const dir = account.browser?.userDataDir
        return dir ? (
          <Typography.Text copyable={{ text: dir }} type="secondary">
            {dir}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary">默认（自动生成）</Typography.Text>
        )
      },
    },
    {
      title: '登录邮箱',
      key: 'loginEmail',
      width: 160,
      ellipsis: true,
      render: (_, account) => account.login?.username || '-',
    },
    {
      title: '代理',
      key: 'proxy',
      width: 180,
      ellipsis: true,
      render: (_, account) => account.browser?.proxy || '-',
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_, account) => {
        if (!account.lastRunAt) {
          return <StatusTag status="idle" label="未运行" />
        }
        if (account.lastStatus === 'ok') {
          return <StatusTag status="running" label="正常" />
        }
        if (account.lastStatus === 'error') {
          return <StatusTag status="error" label="异常" />
        }
        return <StatusTag status="idle" label={account.lastStatus ?? '未知'} />
      },
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 200,
      render: (_, account) => {
        const provider = effectiveProvider(account)
        if (provider === 'bitbrowser') {
          const profileId = account.bitbrowserProfileId ?? account.browser?.profileId
          if (!profileId) {
            return <Typography.Text type="secondary">待绑定 profile</Typography.Text>
          }
          const profile = profileById.get(profileId)
          return (
            <Button
              size="small"
              icon={profile?.opened ? <PowerOff size={14} /> : <Power size={14} />}
              loading={operatingProfileId === profileId}
              disabled={!apiStatus?.available}
              onClick={() => onToggleProfile(profileId)}
            >
              {profile?.opened ? '关闭' : '打开'}
            </Button>
          )
        }
        // 内置 Chromium actions
        return (
          <Space size={4}>
            <Button
              size="small"
              icon={<Stethoscope size={14} />}
              loading={diagnosingAccountId === account.id}
              onClick={() => onDiagnose(account.id)}
            >
              检测
            </Button>
            <Button
              size="small"
              danger
              icon={<Trash2 size={14} />}
              loading={cleaningAccountId === account.id}
              onClick={() => onCleanup(account.id)}
            >
              清理
            </Button>
          </Space>
        )
      },
    },
  ]

  return (
    <Space direction="vertical" size={16} className="full-width">
      {accounts.length === 0 ? (
        <Card>
          <EmptyState
            title="暂无账号"
            description="请先在账号管理中新增账号。"
          />
        </Card>
      ) : (
        <Table
          rowKey="id"
          size="small"
          columns={columns}
          dataSource={accounts}
          scroll={{ x: 1300 }}
          pagination={{ pageSize: 10, showSizeChanger: true }}
        />
      )}

      <Modal
        title="浏览器诊断结果"
        open={diagnosisResult !== null}
        onCancel={onCloseDiagnosis}
        footer={[
          <Button key="close" onClick={onCloseDiagnosis}>
            关闭
          </Button>,
        ]}
      >
        {diagnosisResult ? (
          <Descriptions size="small" column={1} bordered>
            <Descriptions.Item label="账号">{diagnosisResult.accountId}</Descriptions.Item>
            <Descriptions.Item label="Provider">{diagnosisResult.provider}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={diagnosisResult.status === 'ok' ? 'green' : diagnosisResult.status === 'warning' ? 'gold' : 'red'}>
                {diagnosisResult.status}
              </Tag>
            </Descriptions.Item>
            {diagnosisResult.checks.map((check) => (
              <Descriptions.Item key={check.name} label={check.name}>
                <Tag color={check.status === 'ok' ? 'green' : check.status === 'warning' ? 'gold' : 'red'}>
                  {check.status}
                </Tag>
                <Typography.Text type="secondary" style={{ marginLeft: 8 }}>{check.detail}</Typography.Text>
              </Descriptions.Item>
            ))}
          </Descriptions>
        ) : null}
      </Modal>
    </Space>
  )
}

function BuiltinChromiumPanel({
  chromiumStatus,
  accounts,
  diagnosingAccountId,
  cleaningAccountId,
  diagnosisResult,
  onDiagnose,
  onCleanup,
  onCloseDiagnosis,
}: {
  chromiumStatus: BuiltinChromiumStatus | null
  accounts: AccountSummary[]
  diagnosingAccountId?: string
  cleaningAccountId?: string
  diagnosisResult: AccountBrowserDiagnosis | null
  onDiagnose: (accountId: string) => void
  onCleanup: (accountId: string) => void
  onCloseDiagnosis: () => void
}) {
  const columns: ColumnsType<AccountSummary> = [
    {
      title: '账号',
      dataIndex: 'id',
      key: 'id',
      fixed: 'left',
      width: 160,
      render: (id: string) => <Typography.Text strong>{id}</Typography.Text>,
    },
    {
      title: '代理',
      key: 'proxy',
      width: 200,
      ellipsis: true,
      render: (_, account) => account.browser?.proxy || '-',
    },
    {
      title: 'User Data Dir',
      key: 'userDataDir',
      width: 220,
      ellipsis: true,
      render: (_, account) => {
        const dir = account.browser?.userDataDir
        return dir ? (
          <Typography.Text copyable={{ text: dir }} type="secondary">
            {dir}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary">默认（自动生成）</Typography.Text>
        )
      },
    },
    {
      title: '运行状态',
      key: 'runStatus',
      width: 110,
      render: (_, account) => {
        if (!account.lastRunAt) {
          return <StatusTag status="idle" label="未运行" />
        }
        if (account.lastStatus === 'ok') {
          return <StatusTag status="running" label="已运行" />
        }
        if (account.lastStatus === 'error') {
          return <StatusTag status="error" label="异常" />
        }
        return <StatusTag status="idle" label={account.lastStatus ?? '未知'} />
      },
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right',
      width: 260,
      render: (_, account) => (
        <Space size={4}>
          <Button
            size="small"
            icon={<Stethoscope size={14} />}
            loading={diagnosingAccountId === account.id}
            onClick={() => onDiagnose(account.id)}
          >
            检测
          </Button>
          <Button
            size="small"
            icon={<Copy size={14} />}
            onClick={() => {
              const dir = account.browser?.userDataDir ?? ''
              if (dir) {
                void navigator.clipboard.writeText(dir).then(() => message.success('已复制路径'))
              } else {
                message.info('该账号使用默认 user data dir，无自定义路径')
              }
            }}
          >
            复制路径
          </Button>
          <Button
            size="small"
            danger
            icon={<Trash2 size={14} />}
            loading={cleaningAccountId === account.id}
            onClick={() => onCleanup(account.id)}
          >
            清理数据
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} className="full-width">
      <Alert
        type="info"
        showIcon
        message="内置 Chromium 为生产可选方案"
        description="不等价替代 BitBrowser 指纹环境能力。强指纹隔离场景请继续优先使用 BitBrowser。"
      />

      <Card size="small" title="Chromium 环境信息">
        <Descriptions size="small" column={1}>
          <Descriptions.Item label="可执行文件">
            {chromiumStatus?.available ? (
              <Typography.Text copyable={{ text: chromiumStatus.executablePath ?? '' }}>
                {chromiumStatus.executablePath ?? '未知'}
              </Typography.Text>
            ) : (
              <Typography.Text type="danger">
                {chromiumStatus?.error ??
                  '未检测到可用 Chromium，请安装 Chrome/Edge 或手动指定可执行文件。'}
              </Typography.Text>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="数据根目录">
            <Typography.Text copyable={{ text: chromiumStatus?.dataRoot ?? '' }}>
              {chromiumStatus?.dataRoot ?? '-'}
            </Typography.Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {accounts.length === 0 ? (
        <Card>
          <EmptyState
            title="暂无内置 Chromium 账号"
            description="可在账号管理中将浏览器提供方设为内置 Chromium。"
          />
        </Card>
      ) : (
        <Table
          rowKey="id"
          size="small"
          columns={columns}
          dataSource={accounts}
          scroll={{ x: 1000 }}
          pagination={{ pageSize: 10, showSizeChanger: true }}
        />
      )}

      <Modal
        title="浏览器诊断结果"
        open={diagnosisResult !== null}
        onCancel={onCloseDiagnosis}
        footer={[
          <Button key="close" onClick={onCloseDiagnosis}>
            关闭
          </Button>,
        ]}
      >
        {diagnosisResult ? (
          <Descriptions size="small" column={1} bordered>
            <Descriptions.Item label="账号">{diagnosisResult.accountId}</Descriptions.Item>
            <Descriptions.Item label="Provider">{diagnosisResult.provider}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={diagnosisResult.status === 'ok' ? 'green' : diagnosisResult.status === 'warning' ? 'gold' : 'red'}>
                {diagnosisResult.status}
              </Tag>
            </Descriptions.Item>
            {diagnosisResult.checks.map((check) => (
              <Descriptions.Item key={check.name} label={check.name}>
                <Tag color={check.status === 'ok' ? 'green' : check.status === 'warning' ? 'gold' : 'red'}>
                  {check.status}
                </Tag>
                <Typography.Text type="secondary" style={{ marginLeft: 8 }}>{check.detail}</Typography.Text>
              </Descriptions.Item>
            ))}
          </Descriptions>
        ) : null}
      </Modal>
    </Space>
  )
}

function ResultBox({ proxyResult }: { proxyResult: ProxyCheckResult | null }) {
  if (!proxyResult) {
    return <Alert type="info" showIcon message="代理检测结果会显示在这里" />
  }
  return (
    <Alert
      type={proxyResult.valid ? (proxyResult.used ? 'warning' : 'success') : 'error'}
      showIcon
      message={proxyResult.message}
      description={
        proxyResult.proxy ? (
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="代理">{proxyResult.proxy.masked}</Descriptions.Item>
            <Descriptions.Item label="Host">{proxyResult.proxy.host}</Descriptions.Item>
            <Descriptions.Item label="端口">{proxyResult.proxy.port}</Descriptions.Item>
          </Descriptions>
        ) : null
      }
    />
  )
}

function BatchResult({ result }: { result: BatchCreateProfileResult }) {
  const issues = [...result.skipped, ...result.failed]
  return (
    <Space direction="vertical" size={12} className="full-width">
      <Space wrap>
        <Tag color="green">成功 {result.created.length}</Tag>
        <Tag color="gold">跳过 {result.skipped.length}</Tag>
        <Tag color="red">失败 {result.failed.length}</Tag>
      </Space>
      <Table
        size="small"
        rowKey={(row) => `${row.lineNumber}-${row.name}`}
        pagination={{ pageSize: 6 }}
        dataSource={result.created}
        columns={[
          { title: '行号', dataIndex: 'lineNumber', width: 80 },
          { title: '窗口', dataIndex: 'name', width: 160 },
          {
            title: 'profile_id',
            dataIndex: 'profileId',
            render: (value: string) => <Typography.Text copyable>{value}</Typography.Text>,
          },
          { title: '代理', dataIndex: 'proxy', width: 220 },
        ]}
      />
      {issues.length ? (
        <Table
          size="small"
          rowKey={(row) => `${row.lineNumber}-${row.proxy}-${row.reason}`}
          pagination={{ pageSize: 6 }}
          dataSource={issues}
          columns={[
            { title: '行号', dataIndex: 'lineNumber', width: 80 },
            { title: '窗口', dataIndex: 'name', width: 160, render: (value?: string) => value || '-' },
            { title: '代理', dataIndex: 'proxy', width: 220 },
            { title: '原因', dataIndex: 'reason' },
          ]}
        />
      ) : null}
    </Space>
  )
}

function SyncPreviewView({ preview }: { preview: SyncPreview }) {
  return (
    <Space direction="vertical" size={12} className="full-width">
      <Space wrap>
        <Tag color="blue">待追加 {preview.accountsToAdd.length}</Tag>
        <Tag>已存在 {preview.existingAccounts.length}</Tag>
        <Tag color={preview.missingProfiles.length ? 'red' : 'green'}>
          缺失 profile {preview.missingProfiles.length}
        </Tag>
        <Tag color={preview.duplicateProfiles.length ? 'red' : 'green'}>
          重名窗口 {preview.duplicateProfiles.length}
        </Tag>
      </Space>
      {!preview.canApply ? (
        <Alert
          type="error"
          showIcon
          message="当前 dry-run 不能 apply"
          description={[
            preview.missingProfiles.length ? `缺失窗口：${preview.missingProfiles.join(', ')}` : '',
            preview.duplicateProfiles.length ? `重名窗口：${preview.duplicateProfiles.join(', ')}` : '',
          ]
            .filter(Boolean)
            .join('；')}
        />
      ) : null}
      <Table
        size="small"
        rowKey="id"
        dataSource={preview.accountsToAdd}
        pagination={{ pageSize: 8 }}
        columns={[
          { title: '账号 ID', dataIndex: 'id', width: 150 },
          { title: '平台', dataIndex: 'platform', width: 110, render: (value) => getPlatformLabel(value) },
          { title: 'IP 组', dataIndex: 'ipGroup', width: 90 },
          {
            title: '班次',
            dataIndex: 'activeHours',
            width: 120,
            render: (ranges: Array<[number, number]>) => ranges.map(([start, end]) => `${start}-${end}`).join(', '),
          },
          {
            title: 'profile_id',
            dataIndex: 'bitbrowserProfileId',
            render: (value: string) => <Typography.Text copyable>{value}</Typography.Text>,
          },
          { title: '备注', dataIndex: 'notes' },
        ]}
      />
    </Space>
  )
}

function proxyTypeOptions() {
  return [
    { value: 'socks5', label: 'socks5' },
    { value: 'http', label: 'http' },
    { value: 'https', label: 'https' },
  ]
}

function platformOptions() {
  return PLATFORMS.map((platform) => ({
    value: platform.id,
    label: `${platform.localeName}${platform.automaticExecutionSupported ? '' : '（预留）'}`,
  }))
}

function profileMatchesPlatform(profile: BrowserProfile, platform: Platform) {
  if (profile.platform) {
    return profile.platform === platform
  }
  return profile.name.toLowerCase().startsWith(`${platform}_`)
}

function effectiveProvider(account: AccountSummary): BrowserProviderId {
  return account.browserProvider ?? account.browser?.provider ?? 'bitbrowser'
}

async function readProxyImportFile(file: File) {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''

  if (['txt', 'log'].includes(extension)) {
    return normalizeImportedLines(await file.text())
  }
  if (extension === 'csv') {
    return rowsToProxyLines(parseDelimitedRows(await file.text(), ','))
  }
  if (extension === 'tsv') {
    return rowsToProxyLines(parseDelimitedRows(await file.text(), '\t'))
  }
  if (extension === 'docx') {
    return normalizeImportedLines(await readDocxText(await file.arrayBuffer()))
  }
  if (extension === 'xlsx') {
    return rowsToProxyLines(await readXlsxRows(await file.arrayBuffer()))
  }
  if (['doc', 'xls'].includes(extension)) {
    throw new Error('暂不支持旧版二进制 .doc/.xls，请另存为 .docx/.xlsx、.csv 或 .txt 后导入')
  }

  return normalizeImportedLines(await file.text())
}

function normalizeImportedLines(content: string) {
  return content.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
}

function rowsToProxyLines(rows: string[][]) {
  return rows
    .map((row) => row.map((cell) => cell.trim()).filter(Boolean))
    .filter((row) => row.length > 0 && !row[0].startsWith('#'))
    .map((row) => (row.length === 1 ? row[0] : row.join(':')))
    .join('\n')
}

function parseDelimitedRows(content: string, delimiter: ',' | '\t') {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false

  for (let index = 0; index < content.length; index += 1) {
    const char = content[index]
    const next = content[index + 1]

    if (char === '"') {
      if (quoted && next === '"') {
        cell += '"'
        index += 1
      } else {
        quoted = !quoted
      }
      continue
    }

    if (!quoted && char === delimiter) {
      row.push(cell)
      cell = ''
      continue
    }

    if (!quoted && (char === '\n' || char === '\r')) {
      row.push(cell)
      rows.push(row)
      row = []
      cell = ''
      if (char === '\r' && next === '\n') {
        index += 1
      }
      continue
    }

    cell += char
  }

  row.push(cell)
  rows.push(row)
  return rows
}

async function readDocxText(buffer: ArrayBuffer) {
  const files = await readZipFiles(buffer)
  const documentXml = files.get('word/document.xml')
  if (!documentXml) {
    throw new Error('未在 docx 中找到 word/document.xml')
  }

  const paragraphs = documentXml.match(/<w:p[\s\S]*?<\/w:p>/g) ?? [documentXml]
  return paragraphs
    .map((paragraph) =>
      Array.from(paragraph.matchAll(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g))
        .map((match) => decodeXml(match[1]))
        .join(''),
    )
    .filter(Boolean)
    .join('\n')
}

async function readXlsxRows(buffer: ArrayBuffer) {
  const files = await readZipFiles(buffer)
  const sharedStrings = parseSharedStrings(files.get('xl/sharedStrings.xml') ?? '')
  const sheetNames = Array.from(files.keys())
    .filter((name) => /^xl\/worksheets\/sheet\d+\.xml$/.test(name))
    .sort()

  if (!sheetNames.length) {
    throw new Error('未在 xlsx 中找到工作表')
  }

  return sheetNames.flatMap((sheetName) => parseWorksheetRows(files.get(sheetName) ?? '', sharedStrings))
}

function parseSharedStrings(xml: string) {
  return Array.from(xml.matchAll(/<si[^>]*>([\s\S]*?)<\/si>/g)).map((match) =>
    Array.from(match[1].matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g))
      .map((textMatch) => decodeXml(textMatch[1]))
      .join(''),
  )
}

function parseWorksheetRows(xml: string, sharedStrings: string[]) {
  return Array.from(xml.matchAll(/<row[^>]*>([\s\S]*?)<\/row>/g)).map((rowMatch) =>
    Array.from(rowMatch[1].matchAll(/<c\b([^>]*)>([\s\S]*?)<\/c>/g)).map((cellMatch) => {
      const attrs = cellMatch[1]
      const body = cellMatch[2]
      const type = attrs.match(/\bt="([^"]+)"/)?.[1]
      const value = body.match(/<v[^>]*>([\s\S]*?)<\/v>/)?.[1] ?? ''

      if (type === 's') {
        return sharedStrings[Number(value)] ?? ''
      }
      if (type === 'inlineStr') {
        return Array.from(body.matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g))
          .map((match) => decodeXml(match[1]))
          .join('')
      }
      return decodeXml(value)
    }),
  )
}

async function readZipFiles(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer)
  const view = new DataView(buffer)
  const files = new Map<string, string>()
  const eocdOffset = findEndOfCentralDirectory(view)
  const centralDirectoryOffset = view.getUint32(eocdOffset + 16, true)
  const entryCount = view.getUint16(eocdOffset + 10, true)
  let offset = centralDirectoryOffset

  for (let index = 0; index < entryCount; index += 1) {
    if (view.getUint32(offset, true) !== 0x02014b50) {
      throw new Error('Office 文件目录结构异常')
    }

    const compression = view.getUint16(offset + 10, true)
    const compressedSize = view.getUint32(offset + 20, true)
    const fileNameLength = view.getUint16(offset + 28, true)
    const extraLength = view.getUint16(offset + 30, true)
    const commentLength = view.getUint16(offset + 32, true)
    const localHeaderOffset = view.getUint32(offset + 42, true)
    const name = decodeUtf8(bytes.slice(offset + 46, offset + 46 + fileNameLength))
    const localNameLength = view.getUint16(localHeaderOffset + 26, true)
    const localExtraLength = view.getUint16(localHeaderOffset + 28, true)
    const dataStart = localHeaderOffset + 30 + localNameLength + localExtraLength
    const compressedData = bytes.slice(dataStart, dataStart + compressedSize)

    if (!name.endsWith('/')) {
      files.set(name, decodeUtf8(await inflateZipEntry(compressedData, compression)))
    }

    offset += 46 + fileNameLength + extraLength + commentLength
  }

  return files
}

function findEndOfCentralDirectory(view: DataView) {
  const minimumOffset = Math.max(0, view.byteLength - 0xffff - 22)
  for (let offset = view.byteLength - 22; offset >= minimumOffset; offset -= 1) {
    if (view.getUint32(offset, true) === 0x06054b50) {
      return offset
    }
  }
  throw new Error('未找到 Office 文件目录，请确认文件格式正确')
}

async function inflateZipEntry(data: Uint8Array, compression: number) {
  if (compression === 0) {
    return data
  }
  if (compression !== 8) {
    throw new Error(`不支持的 Office 压缩方式：${compression}`)
  }

  const DecompressionStreamCtor = (
    globalThis as typeof globalThis & {
      DecompressionStream?: new (format: string) => DecompressionStream
    }
  ).DecompressionStream
  if (!DecompressionStreamCtor) {
    throw new Error('当前 WebView 不支持解压 Office 文件，请改用 .csv 或 .txt 导入')
  }

  const stream = new Blob([data]).stream().pipeThrough(new DecompressionStreamCtor('deflate-raw'))
  return new Uint8Array(await new Response(stream).arrayBuffer())
}

function decodeUtf8(bytes: Uint8Array) {
  return new TextDecoder('utf-8').decode(bytes)
}

function decodeXml(value: string) {
  return value
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
}

function validateProxyFormat(_: unknown, value?: string) {
  if (!value) {
    return Promise.resolve()
  }
  const parts = value.trim().split(':')
  if (parts.length < 4 || parts.slice(0, 4).some((part) => !part)) {
    return Promise.reject(new Error('代理格式必须是 host:port:用户名:密码'))
  }
  const port = Number(parts[1])
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    return Promise.reject(new Error('代理端口必须是 1~65535 的整数'))
  }
  return Promise.resolve()
}
