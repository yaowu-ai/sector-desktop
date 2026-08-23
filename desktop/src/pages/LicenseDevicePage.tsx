import { Alert, Button, Card, Col, Descriptions, Modal, Row, Space, Typography, message } from 'antd'
import { BadgeCheck, CalendarClock, KeyRound, LogOut, Monitor, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'

import { useDesktopAuth } from '../app/DesktopAuthContext'
import { PageHeader } from '../components/PageHeader'
import { StatusTag, type StatusTone } from '../components/StatusTag'
import type { DesktopLicenseCurrentResponse } from '../services/desktopApi'

export function LicenseDevicePage() {
  const auth = useDesktopAuth()
  const claims = auth.license?.claims
  const [modal, contextHolder] = Modal.useModal()

  const confirmUnbindCurrentDevice = () => {
    modal.confirm({
      title: '解除绑定本设备？',
      content: '解除后将释放当前设备名额，并退出桌面端登录。重新使用本机时需要再次登录并占用设备名额。',
      okText: '解除绑定并退出',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        await auth.unbindCurrentDevice()
        message.success('当前设备已解除绑定')
      },
    })
  }

  return (
    <div>
      {contextHolder}
      <PageHeader
        title="授权与设备"
        description="查看当前账号授权和本机设备绑定状态。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} onClick={() => void auth.refreshEntitlement()} loading={auth.loading}>
              重新检查
            </Button>
            <Button
              danger
              icon={<LogOut size={16} />}
              onClick={confirmUnbindCurrentDevice}
              loading={auth.loading}
              disabled={auth.device?.status !== 'active'}
            >
              解除绑定本设备
            </Button>
          </Space>
        }
      />

      {auth.license?.status !== 'active' ? (
        <Alert
          className="shell-alert"
          type="warning"
          showIcon
          message="当前 License 不可用"
          description={readClaimString(claims, 'reason') || '请确认订阅有效、设备已激活，并且 License 未过期或撤销。'}
        />
      ) : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <StatusCard
            icon={<KeyRound size={24} />}
            title="License 状态"
            value={formatLicenseStatus(auth.license?.status)}
            tone={licenseTone(auth.license?.status)}
          />
        </Col>
        <Col xs={24} md={8}>
          <StatusCard
            icon={<Monitor size={24} />}
            title="当前设备"
            value={auth.device?.status === 'active' ? '已激活' : '未激活'}
            tone={auth.device?.status === 'active' ? 'ok' : 'warning'}
          />
        </Col>
        <Col xs={24} md={8}>
          <StatusCard
            icon={<BadgeCheck size={24} />}
            title="授权校验"
            value={auth.license?.algorithm === 'Ed25519' && auth.license?.signature ? '正常' : '需检查'}
            tone={auth.license?.algorithm === 'Ed25519' && auth.license?.signature ? 'ok' : 'warning'}
          />
        </Col>

        <Col xs={24} xl={12}>
          <Card title="License 信息">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="License 状态">
                <StatusTag status={licenseTone(auth.license?.status)} label={formatLicenseStatus(auth.license?.status)} />
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<CalendarClock size={15} />} text="签发时间" />}>
                {formatDateTime(readClaimString(claims, 'issuedAt'))}
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<CalendarClock size={15} />} text="到期时间" />}>
                {formatDateTime(readClaimString(claims, 'expiresAt'))}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} xl={12}>
          <Card title="设备绑定">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label={<InfoLabel icon={<Monitor size={15} />} text="设备名称" />}>
                {auth.device?.deviceName || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="设备状态">
                <StatusTag status={auth.device?.status === 'active' ? 'ok' : 'warning'} label={auth.device?.status === 'active' ? '已激活' : '未激活'} />
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<CalendarClock size={15} />} text="更新时间" />}>
                {auth.device?.updateTime || '-'}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

function StatusCard({ icon, title, value, tone }: { icon: ReactNode; title: string; value: string; tone: StatusTone }) {
  return (
    <Card>
      <Space size={14}>
        <div className={`license-status-icon license-status-icon-${tone}`}>{icon}</div>
        <div>
          <Typography.Text type="secondary">{title}</Typography.Text>
          <Typography.Title level={3}>{value}</Typography.Title>
        </div>
      </Space>
    </Card>
  )
}

function InfoLabel({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <Space size={6}>
      {icon}
      <span>{text}</span>
    </Space>
  )
}

function licenseTone(status?: DesktopLicenseCurrentResponse['status']): StatusTone {
  if (status === 'active') return 'ok'
  if (status === 'expired' || status === 'revoked' || status === 'inactive') return 'warning'
  return 'idle'
}

function formatLicenseStatus(status?: DesktopLicenseCurrentResponse['status']) {
  if (status === 'active') return '有效'
  if (status === 'expired') return '已过期'
  if (status === 'revoked') return '已撤销'
  if (status === 'inactive') return '未激活'
  if (status === 'not_configured') return '未配置'
  if (status === 'not_implemented') return '未实现'
  return '未知'
}

function readClaimString(claims: Record<string, unknown> | null | undefined, key: string) {
  const value = claims?.[key]
  return typeof value === 'string' ? value : ''
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
