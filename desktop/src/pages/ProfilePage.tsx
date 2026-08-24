import { Card, Descriptions, Space, Tag, Typography } from 'antd'
import { CalendarClock, KeyRound, ShieldCheck, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { useDesktopAuth } from '../app/DesktopAuthContext'
import { PageHeader } from '../components/PageHeader'
import { StatusTag, type StatusTone } from '../components/StatusTag'
import { loadDesktopPlans, type DesktopLicenseCurrentResponse, type DesktopPlanItem, type DesktopSubscriptionCurrentResponse } from '../services/desktopApi'

export function ProfilePage() {
  const auth = useDesktopAuth()
  const session = auth.session
  const subscription = auth.subscription
  const license = auth.license
  const [plans, setPlans] = useState<DesktopPlanItem[] | null>(null)

  useEffect(() => {
    if (!auth.session) return
    void loadDesktopPlans(auth.session, auth.apiBaseUrl)
      .then((response) => setPlans(response.plans))
      .catch(() => setPlans(null))
  }, [auth.apiBaseUrl, auth.session])

  const memberPlan =
    findCurrentPlanName(plans, subscription?.planId) ||
    findCurrentPlanName(plans, readClaimString(license?.claims, 'planId')) ||
    '未开通'

  return (
    <div>
      <PageHeader title="账号信息" description="查看当前账号状态。" />

      <Card>
        <Space size={16} align="start" className="profile-summary">
          <div className="profile-avatar">
            <UserRound size={34} />
          </div>
          <div>
            <Typography.Title level={3} className="profile-title">
              {session?.userName || session?.username || '产品用户'}
            </Typography.Title>
            <div className="profile-role-row">
              <Tag color={subscription?.status === 'active' ? 'blue' : 'default'}>{memberPlan}</Tag>
            </div>
          </div>
        </Space>

        <Typography.Title level={5} className="profile-section-title">
          账号信息
        </Typography.Title>
        <Descriptions column={{ xs: 1, md: 2 }} bordered size="small">
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
            {formatDateTime(readClaimString(license?.claims, 'expiresAt'))}
          </Descriptions.Item>
        </Descriptions>
      </Card>
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

function readClaimString(claims: Record<string, unknown> | null | undefined, key: string) {
  const value = claims?.[key]
  return typeof value === 'string' ? value : ''
}

function findCurrentPlanName(plans: DesktopPlanItem[] | null, planId?: string | null) {
  if (!plans || !planId) return ''
  return plans.find((plan) => plan.planId === planId)?.planName ?? ''
}
