import { Alert, Button, Card, Col, Descriptions, Row, Space, Typography } from 'antd'
import { BadgeCheck, CalendarClock, Fingerprint, KeyRound, Monitor, RefreshCw, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'

import { useDesktopAuth } from '../app/DesktopAuthContext'
import { PageHeader } from '../components/PageHeader'
import { StatusTag, type StatusTone } from '../components/StatusTag'
import type { DesktopLicenseCurrentResponse } from '../services/desktopApi'

export function LicenseDevicePage() {
  const auth = useDesktopAuth()
  const claims = auth.license?.claims

  return (
    <div>
      <PageHeader
        title="授权与设备"
        description="查看当前账号的 License、签名校验和本机设备绑定状态。"
        extra={
          <Button icon={<RefreshCw size={16} />} onClick={() => void auth.refreshEntitlement()} loading={auth.loading}>
            重新检查
          </Button>
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
            title="签名校验"
            value={auth.license?.algorithm === 'Ed25519' && auth.license?.signature ? '已校验' : '无签名'}
            tone={auth.license?.algorithm === 'Ed25519' && auth.license?.signature ? 'ok' : 'warning'}
          />
        </Col>

        <Col xs={24} xl={12}>
          <Card title="License 信息">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label={<InfoLabel icon={<KeyRound size={15} />} text="License ID" />}>
                {auth.license?.licenseId || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="License Key">{readClaimString(claims, 'licenseKey') || '-'}</Descriptions.Item>
              <Descriptions.Item label="License 状态">
                <StatusTag status={licenseTone(auth.license?.status)} label={formatLicenseStatus(auth.license?.status)} />
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<CalendarClock size={15} />} text="签发时间" />}>
                {formatDateTime(readClaimString(claims, 'issuedAt'))}
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<CalendarClock size={15} />} text="到期时间" />}>
                {formatDateTime(readClaimString(claims, 'expiresAt'))}
              </Descriptions.Item>
              <Descriptions.Item label="签名算法">{auth.license?.algorithm || '-'}</Descriptions.Item>
              <Descriptions.Item label="签名状态">{auth.license?.signature ? '已下发' : '-'}</Descriptions.Item>
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
              <Descriptions.Item label={<InfoLabel icon={<Fingerprint size={15} />} text="设备指纹" />}>
                {auth.device?.deviceFingerprint || readClaimString(claims, 'deviceFingerprint') || '-'}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24}>
          <Card title="授权载荷">
            <Descriptions column={{ xs: 1, md: 2 }} bordered size="small">
              <Descriptions.Item label="用户 ID">{readClaimString(claims, 'userId') || auth.session?.userId || '-'}</Descriptions.Item>
              <Descriptions.Item label="用户角色">{formatUserRole(readClaimNumber(claims, 'userRole') || auth.session?.userRole)}</Descriptions.Item>
              <Descriptions.Item label="订阅 ID">{readClaimString(claims, 'subscriptionId') || auth.subscription?.subscriptionId || '-'}</Descriptions.Item>
              <Descriptions.Item label="套餐 ID">{readClaimString(claims, 'planId') || auth.subscription?.planId || '-'}</Descriptions.Item>
              <Descriptions.Item label="套餐编码">{readClaimString(claims, 'planCode') || '-'}</Descriptions.Item>
              <Descriptions.Item label="签发方">{readClaimString(claims, 'issuer') || '-'}</Descriptions.Item>
              <Descriptions.Item label="使用方">{readClaimString(claims, 'audience') || '-'}</Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<ShieldCheck size={15} />} text="载荷版本" />}>
                {String(readClaimNumber(claims, 'version') || '-')}
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

function formatUserRole(role?: number) {
  return role === 1 ? '技术人员' : '普通用户'
}

function readClaimString(claims: Record<string, unknown> | null | undefined, key: string) {
  const value = claims?.[key]
  return typeof value === 'string' ? value : ''
}

function readClaimNumber(claims: Record<string, unknown> | null | undefined, key: string) {
  const value = claims?.[key]
  return typeof value === 'number' ? value : undefined
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
