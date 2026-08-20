import { Alert, Button, Card, Col, Descriptions, Row, Skeleton, Space, Tag, Typography } from 'antd'
import { CalendarClock, CheckCircle2, CreditCard, Gauge, Monitor, RefreshCw, ShieldCheck, Users } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { useDesktopAuth } from '../app/DesktopAuthContext'
import { PageHeader } from '../components/PageHeader'
import { StatusTag, type StatusTone } from '../components/StatusTag'
import {
  loadDesktopPlans,
  type DesktopPlanItem,
  type DesktopPlansResponse,
  type DesktopSubscriptionCurrentResponse,
} from '../services/desktopApi'

export function PlanCenterPage() {
  const auth = useDesktopAuth()
  const [plans, setPlans] = useState<DesktopPlansResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const currentPlanId = auth.subscription?.planId
  const currentPlanCode = readClaimString(auth.license?.claims, 'planCode')
  const limits = useMemo(() => readLimits(auth.license?.claims), [auth.license?.claims])

  useEffect(() => {
    if (!auth.session) return

    setLoading(true)
    setError(null)
    loadDesktopPlans(auth.session, auth.apiBaseUrl)
      .then(setPlans)
      .catch((nextError) => setError(nextError instanceof Error ? nextError.message : String(nextError)))
      .finally(() => setLoading(false))
  }, [auth.apiBaseUrl, auth.session])

  return (
    <div>
      <PageHeader
        title="套餐中心"
        description="查看当前套餐、订阅状态和已下发到本机的使用额度。"
        extra={
          <Button icon={<RefreshCw size={16} />} onClick={() => void auth.refreshEntitlement()} loading={auth.loading}>
            刷新授权
          </Button>
        }
      />

      {auth.subscription?.status !== 'active' ? (
        <Alert
          className="shell-alert"
          type="warning"
          showIcon
          message="当前账号没有有效订阅"
          description="请完成套餐开通后再使用桌面端养号能力。"
        />
      ) : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="当前订阅">
            <Space direction="vertical" size={14} className="full-width">
              <div className="plan-current-badge">
                <CreditCard size={28} />
                <div>
                  <Typography.Text type="secondary">当前套餐</Typography.Text>
                  <Typography.Title level={3}>{findCurrentPlanName(plans?.plans, currentPlanId) || currentPlanCode || '-'}</Typography.Title>
                </div>
              </div>
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="订阅状态">
                  <StatusTag status={subscriptionTone(auth.subscription?.status)} label={formatSubscriptionStatus(auth.subscription?.status)} />
                </Descriptions.Item>
                <Descriptions.Item label="套餐 ID">{currentPlanId || '-'}</Descriptions.Item>
                <Descriptions.Item label="套餐编码">{currentPlanCode || '-'}</Descriptions.Item>
                <Descriptions.Item label="到期时间">{formatDateTime(auth.subscription?.expiresAt)}</Descriptions.Item>
              </Descriptions>
              <Button type="primary" block disabled>
                续费或升级（支付宝待接入）
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Card title="套餐列表">
            {loading ? <Skeleton active paragraph={{ rows: 4 }} /> : null}
            {!loading && error ? <Alert type="error" showIcon message="套餐列表加载失败" description={error} /> : null}
            {!loading && !error ? (
              <Row gutter={[12, 12]}>
                {(plans?.plans ?? []).map((plan) => (
                  <Col xs={24} md={12} key={plan.planId}>
                    <PlanCard plan={plan} current={plan.planId === currentPlanId || plan.planCode === currentPlanCode} />
                  </Col>
                ))}
                {(plans?.plans ?? []).length === 0 ? (
                  <Col span={24}>
                    <div className="empty-state">
                      <Typography.Text type="secondary">暂无可用套餐</Typography.Text>
                    </div>
                  </Col>
                ) : null}
              </Row>
            ) : null}
          </Card>
        </Col>

        <Col xs={24}>
          <Card title="当前额度">
            <Row gutter={[12, 12]}>
              <QuotaCard icon={<Users size={22} />} title="启用账号上限" value={formatLimit(limits.maxEnabledAccounts)} />
              <QuotaCard icon={<Monitor size={22} />} title="授权设备上限" value={formatLimit(limits.maxDevices)} />
              <QuotaCard icon={<Gauge size={22} />} title="每日任务次数" value={formatLimit(limits.dailyTaskRuns)} />
              <QuotaCard icon={<CalendarClock size={22} />} title="自动调度" value={formatBooleanLimit(limits.scheduler)} />
              <QuotaCard icon={<CheckCircle2 size={22} />} title="目标号互动" value={formatBooleanLimit(limits.targetEngagement)} />
              <QuotaCard icon={<ShieldCheck size={22} />} title="CSV 导出" value={formatBooleanLimit(limits.exportCsv)} />
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

function PlanCard({ plan, current }: { plan: DesktopPlanItem; current: boolean }) {
  return (
    <div className={current ? 'plan-option-card plan-option-card-current' : 'plan-option-card'}>
      <Space direction="vertical" size={10} className="full-width">
        <Space className="plan-option-head">
          <Typography.Text strong>{plan.planName || plan.planCode || '未命名套餐'}</Typography.Text>
          <Space size={6}>
            {current ? <Tag color="blue">当前套餐</Tag> : null}
            <Tag color={plan.status === 'active' ? 'green' : 'default'}>{plan.status === 'active' ? '可用' : '停用'}</Tag>
          </Space>
        </Space>
        <Typography.Text type="secondary">套餐编码：{plan.planCode || '-'}</Typography.Text>
        <Typography.Text type="secondary">套餐 ID：{plan.planId}</Typography.Text>
      </Space>
    </div>
  )
}

function QuotaCard({ icon, title, value }: { icon: React.ReactNode; title: string; value: string }) {
  return (
    <Col xs={24} sm={12} lg={8} xl={4}>
      <div className="quota-card">
        <div className="quota-card-icon">{icon}</div>
        <Typography.Text type="secondary">{title}</Typography.Text>
        <Typography.Title level={4}>{value}</Typography.Title>
      </div>
    </Col>
  )
}

function findCurrentPlanName(plans: DesktopPlanItem[] | undefined, planId?: string | null) {
  return plans?.find((plan) => plan.planId === planId)?.planName ?? ''
}

function subscriptionTone(status?: DesktopSubscriptionCurrentResponse['status']): StatusTone {
  if (status === 'active') return 'ok'
  if (status === 'expired' || status === 'none') return 'warning'
  return 'idle'
}

function formatSubscriptionStatus(status?: DesktopSubscriptionCurrentResponse['status']) {
  if (status === 'active') return '有效'
  if (status === 'expired') return '已过期'
  if (status === 'none') return '无订阅'
  if (status === 'not_configured') return '未配置'
  return '未知'
}

function readLimits(claims?: Record<string, unknown> | null) {
  const limits = claims?.limits
  return limits && typeof limits === 'object' ? (limits as Record<string, unknown>) : {}
}

function readClaimString(claims: Record<string, unknown> | null | undefined, key: string) {
  const value = claims?.[key]
  return typeof value === 'string' ? value : ''
}

function formatLimit(value: unknown) {
  if (value === -1) return '不限'
  if (typeof value === 'number') return String(value)
  return '-'
}

function formatBooleanLimit(value: unknown) {
  if (value === true) return '支持'
  if (value === false) return '不支持'
  return '-'
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
