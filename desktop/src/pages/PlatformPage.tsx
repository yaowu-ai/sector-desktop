import { Alert, Button, Card, Col, Descriptions, Modal, Row, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Ban, CheckCircle2, Chrome, Clock3, FileJson, PlayCircle, PlugZap, ShieldAlert } from 'lucide-react'
import { useState } from 'react'

import { PageHeader } from '../components/PageHeader'
import { StatusTag } from '../components/StatusTag'
import {
  PLATFORM_CAPABILITIES,
  PLATFORMS,
  type PlatformDefinition,
} from '../services/platforms'
import type { PlatformCapabilityStatus, PlatformSupportStatus } from '../services/types'

export function PlatformPage() {
  const [configPlatform, setConfigPlatform] = useState<PlatformDefinition | null>(null)

  const columns: ColumnsType<PlatformDefinition> = [
    {
      title: '平台',
      dataIndex: 'localeName',
      key: 'platform',
      fixed: 'left',
      width: 150,
      render: (_, platform) => (
        <Space direction="vertical" size={2}>
          <Typography.Text strong>{platform.localeName}</Typography.Text>
          <Typography.Text type="secondary">{platform.accountPrefix}*</Typography.Text>
        </Space>
      ),
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 90,
      render: (enabled: boolean) => (
        <StatusTag status={enabled ? 'ok' : 'idle'} label={enabled ? '启用' : '停用'} />
      ),
    },
    {
      title: '接入状态',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (status: PlatformSupportStatus) => <PlatformStatus status={status} />,
    },
    ...PLATFORM_CAPABILITIES.map((capability) => ({
      title: (
        <Tooltip title={capability.description}>
          <span>{capability.label}</span>
        </Tooltip>
      ),
      key: capability.key,
      align: 'center' as const,
      width: 116,
      render: (_: unknown, platform: PlatformDefinition) => (
        <CapabilityTag status={platform.capabilities[capability.key]} />
      ),
    })),
    {
      title: '配置 / 执行',
      key: 'execution',
      fixed: 'right',
      width: 230,
      render: (_, platform) => (
        <Space>
          <Button icon={<FileJson size={16} />} onClick={() => setConfigPlatform(platform)}>
            默认配置
          </Button>
          {platform.automaticExecutionSupported ? (
            <Button icon={<PlayCircle size={16} />} onClick={() => goRoute('tasks')}>
              查看任务
            </Button>
          ) : (
            <Tooltip title="V1 未适配该平台，自动执行入口已禁用">
              <Button icon={<Ban size={16} />} disabled>
                不可执行
              </Button>
            </Tooltip>
          )}
        </Space>
      ),
    },
  ]

  const supportedCount = PLATFORMS.filter((platform) => platform.status === 'supported').length
  const unavailableCount = PLATFORMS.length - supportedCount

  return (
    <>
      <PageHeader
        title="平台设置"
        description="平台能力矩阵和自动执行适配状态。"
      />

        <Alert
          className="shell-alert"
          type="info"
          showIcon
          message="TikTok 已允许启动真实自动化任务"
          description="WhatsApp 和抖音仍保留账号、浏览器环境、任务、调度和统计入口。"
        />

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Space align="start" size={12}>
              <CheckCircle2 size={22} color="#16a34a" />
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">已支持平台</Typography.Text>
                <Typography.Title level={3}>{supportedCount}</Typography.Title>
              </Space>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Space align="start" size={12}>
              <Clock3 size={22} color="#ca8a04" />
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">预留、开发中或未支持</Typography.Text>
                <Typography.Title level={3}>{unavailableCount}</Typography.Title>
              </Space>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Space align="start" size={12}>
              <ShieldAlert size={22} color="#2563eb" />
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">自动执行策略</Typography.Text>
                <Typography.Title level={3}>白名单</Typography.Title>
              </Space>
            </Space>
          </Card>
        </Col>

        <Col span={24}>
            <Table
              columns={columns}
              dataSource={PLATFORMS}
              pagination={false}
              rowKey="id"
              scroll={{ x: 1120 }}
              expandable={{
                expandedRowRender: (platform) => <PlatformAccessDetails platform={platform} />,
                defaultExpandedRowKeys: ['tiktok'],
              }}
            />
        </Col>

        <Col span={24}>
          <Card title="API / 环境说明">
            <Row gutter={[16, 16]}>
              {PLATFORMS.map((platform) => (
                <Col xs={24} xl={12} key={platform.id}>
                  <PlatformAccessDetails platform={platform} />
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      </Row>

      <Modal
        title={configPlatform ? `${configPlatform.localeName} 默认配置` : '默认配置'}
        open={Boolean(configPlatform)}
        width={720}
        footer={null}
        onCancel={() => setConfigPlatform(null)}
      >
        <Typography.Paragraph type="secondary">
          这里展示 registry 中的平台默认配置入口。M8 会把保存结构迁移到 platforms.&lt;platform&gt;。
        </Typography.Paragraph>
        <pre className="platform-config-preview">
          {JSON.stringify(configPlatform?.defaultConfig ?? {}, null, 2)}
        </pre>
      </Modal>
    </>
  )
}

function PlatformAccessDetails({ platform }: { platform: PlatformDefinition }) {
  const details = platformAccessDetails(platform)
  return (
    <div className={`platform-access-card platform-access-card-${platform.status}`}>
      <div className="platform-access-header">
        <Space direction="vertical" size={4}>
          <Space size={8} wrap>
            <Typography.Text strong className="platform-access-title">
              {platform.localeName}
            </Typography.Text>
            <PlatformStatus status={platform.status} />
          </Space>
          <Typography.Text type="secondary" code>
            {platform.accountPrefix}*
          </Typography.Text>
        </Space>
        <Tag color={platform.automaticExecutionSupported ? 'blue' : 'default'} className="platform-access-execution-tag">
          {platform.automaticExecutionSupported ? '可启动自动执行' : '仅预留配置入口'}
        </Tag>
      </div>

      <Typography.Paragraph className="platform-access-summary">{platform.summary}</Typography.Paragraph>

      <div className="platform-access-detail-list">
        <AccessDetailItem icon={<Chrome size={16} />} label="浏览器环境" text={details.browser} />
        <AccessDetailItem
          icon={platform.automaticExecutionSupported ? <PlayCircle size={16} /> : <Ban size={16} />}
          label="执行入口"
          text={details.runner}
          chips={details.runnerChips}
          muted={!platform.automaticExecutionSupported}
        />
        <AccessDetailItem icon={<PlugZap size={16} />} label="API / 环境" text={details.api} chips={details.apiChips} />
      </div>
    </div>
  )
}

function AccessDetailItem({
  icon,
  label,
  text,
  chips,
  muted,
}: {
  icon: JSX.Element
  label: string
  text: string
  chips?: string[]
  muted?: boolean
}) {
  return (
    <div className={`platform-access-detail-item${muted ? ' platform-access-detail-item-muted' : ''}`}>
      <div className="platform-access-detail-label">
        {icon}
        <Typography.Text strong>{label}</Typography.Text>
      </div>
      <div className="platform-access-detail-content">
        <Typography.Text>{text}</Typography.Text>
        {chips?.length ? (
          <Space size={[6, 6]} wrap className="platform-access-chip-row">
            {chips.map((chip) => (
              <Typography.Text code key={chip} className="platform-access-chip">
                {chip}
              </Typography.Text>
            ))}
          </Space>
        ) : null}
      </div>
    </div>
  )
}

function platformAccessDetails(platform: PlatformDefinition) {
  if (platform.id === 'tiktok') {
    return {
      browser: '使用 Bit浏览器 Local API 和账号绑定 profile_id。',
      runner: '已接入统一入口和诊断脚本，可启动真实自动化任务。',
      runnerChips: ['src/main.py', 'src/test_like.py', 'src/test_comment.py', 'src/scheduler.py'],
      api: '运行前需要本机 Python、Bit浏览器 API、账号配置和动作数据库。',
      apiChips: ['Python', 'Bit浏览器 API', 'config/accounts.yaml', 'data/actions.db'],
    }
  }
  if (platform.id === 'douyin') {
    return {
      browser: '可预留账号和 Bit浏览器 profile 绑定。',
      runner: '现有抓取器暂不接入 PC 端自动执行，启动入口保持禁用。',
      runnerChips: ['src/douyin-fetcher'],
      api: '后续接入时需补齐平台 adapter、执行器入口和日志统计口径。',
      apiChips: ['platform adapter', 'runner', 'stats schema'],
    }
  }
  return {
    browser: '可预留账号和 Bit浏览器 profile 绑定。',
    runner: '自动执行 runner 未接入，启动类入口保持禁用。',
    runnerChips: ['reserved runner'],
    api: '后续接入时需补齐平台 adapter、平台 API 凭据或网页自动化环境说明。',
    apiChips: ['platform adapter', 'API credentials', 'automation env'],
  }
}

function PlatformStatus({ status }: { status: PlatformSupportStatus }) {
  if (status === 'supported') {
    return <StatusTag status="ok" label="已支持" />
  }
  if (status === 'reserved') {
    return <StatusTag status="warning" label="预留" />
  }
  if (status === 'in_development') {
    return <StatusTag status="running" label="开发中" />
  }
  return <StatusTag status="idle" label="未支持" />
}

function CapabilityTag({ status }: { status?: PlatformCapabilityStatus }) {
  if (status === 'supported') {
    return <Tag color="green">支持</Tag>
  }
  if (status === 'reserved') {
    return <Tag color="gold">预留</Tag>
  }
  if (status === 'in_development') {
    return <Tag color="blue">开发中</Tag>
  }
  return <Tag>未支持</Tag>
}

function goRoute(routeKey: string) {
  window.location.hash = routeKey
}
