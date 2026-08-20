import { Card, Col, Descriptions, Row, Space, Tag, Typography } from 'antd'
import { CalendarClock, KeyRound, Mail, Monitor, Phone, ShieldCheck, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'

import { useDesktopAuth } from '../app/DesktopAuthContext'
import { PageHeader } from '../components/PageHeader'
import { StatusTag, type StatusTone } from '../components/StatusTag'
import type { DesktopLicenseCurrentResponse, DesktopSubscriptionCurrentResponse } from '../services/desktopApi'

export function ProfilePage() {
  const auth = useDesktopAuth()
  const session = auth.session
  const subscription = auth.subscription
  const license = auth.license
  const device = auth.device

  return (
    <div>
      <PageHeader title="账号信息" description="查看当前登录账号、订阅、授权和设备状态。" />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card>
            <Space size={16} align="start">
              <div className="profile-avatar">
                <UserRound size={34} />
              </div>
              <div>
                <Typography.Title level={3} className="profile-title">
                  {session?.userName || session?.username || '产品用户'}
                </Typography.Title>
                <Typography.Text type="secondary">ID：{session?.userId || '-'}</Typography.Text>
                <div className="profile-role-row">
                  <Tag color={session?.userRole === 1 ? 'blue' : 'green'}>{formatUserRole(session?.userRole)}</Tag>
                </div>
              </div>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={16}>
          <Card title="账号信息">
            <Descriptions column={{ xs: 1, md: 2 }} bordered size="small">
              <Descriptions.Item label={<InfoLabel icon={<Phone size={15} />} text="手机号" />}>
                {session?.phone || '-'}
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<Mail size={15} />} text="邮箱" />}>
                {session?.email || '-'}
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<ShieldCheck size={15} />} text="订阅状态" />}>
                <StatusTag status={subscriptionTone(subscription?.status)} label={formatSubscriptionStatus(subscription?.status)} />
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<KeyRound size={15} />} text="License 状态" />}>
                <StatusTag status={licenseTone(license?.status)} label={formatLicenseStatus(license?.status)} />
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<CalendarClock size={15} />} text="订阅到期时间" />}>
                {formatDateTime(subscription?.expiresAt)}
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<CalendarClock size={15} />} text="License 到期时间" />}>
                {formatDateTime(readClaimString(license, 'expiresAt'))}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="当前设备">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label={<InfoLabel icon={<Monitor size={15} />} text="设备名称" />}>
                {device?.deviceName || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="设备状态">
                <StatusTag status={device?.status === 'active' ? 'ok' : 'warning'} label={device?.status === 'active' ? '已激活' : '未激活'} />
              </Descriptions.Item>
              <Descriptions.Item label="设备指纹">{device?.deviceFingerprint || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="套餐与授权">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="套餐 ID">{subscription?.planId || '-'}</Descriptions.Item>
              <Descriptions.Item label="订阅 ID">{subscription?.subscriptionId || '-'}</Descriptions.Item>
              <Descriptions.Item label="License ID">{license?.licenseId || '-'}</Descriptions.Item>
              <Descriptions.Item label="License Key">{readClaimString(license, 'licenseKey') || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
    </div>
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

function formatUserRole(role?: 1 | 2) {
  return role === 1 ? '技术人员' : '普通用户'
}

function subscriptionTone(status?: DesktopSubscriptionCurrentResponse['status']): StatusTone {
  if (status === 'active') return 'ok'
  if (status === 'expired' || status === 'none') return 'warning'
  return 'idle'
}

function licenseTone(status?: DesktopLicenseCurrentResponse['status']): StatusTone {
  if (status === 'active') return 'ok'
  if (status === 'expired' || status === 'revoked' || status === 'inactive') return 'warning'
  return 'idle'
}

function formatSubscriptionStatus(status?: DesktopSubscriptionCurrentResponse['status']) {
  if (status === 'active') return '有效'
  if (status === 'expired') return '已过期'
  if (status === 'none') return '无订阅'
  if (status === 'not_configured') return '未配置'
  return '未知'
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

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function readClaimString(license: DesktopLicenseCurrentResponse | null, key: string) {
  const value = license?.claims?.[key]
  return typeof value === 'string' ? value : ''
}
