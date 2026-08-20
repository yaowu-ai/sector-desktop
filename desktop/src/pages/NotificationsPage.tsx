import { Badge, Button, Card, Col, Empty, List, Row, Space, Tag, Typography, message } from 'antd'
import { Bell, CheckCircle2, Clock, Megaphone, RefreshCw, ShieldAlert } from 'lucide-react'
import { useMemo, useState } from 'react'

import { useDesktopAuth } from '../app/DesktopAuthContext'
import { PageHeader } from '../components/PageHeader'

interface NotificationItem {
  id: string
  title: string
  detail: string
  time: string
  type: 'auth' | 'system' | 'usage'
  unread: boolean
}

export function NotificationsPage() {
  const auth = useDesktopAuth()
  const [readIds, setReadIds] = useState<Set<string>>(new Set())
  const notifications = useMemo(() => buildNotifications(auth, readIds), [auth, readIds])
  const unreadCount = notifications.filter((item) => item.unread).length

  const markAllRead = () => {
    setReadIds(new Set(notifications.map((item) => item.id)))
    message.success('已全部标记为已读')
  }

  return (
    <div>
      <PageHeader
        title="消息通知"
        description="查看授权、订阅和本地运行相关提醒。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} onClick={() => void auth.refreshEntitlement()} loading={auth.loading}>
              刷新
            </Button>
            <Button onClick={markAllRead} disabled={unreadCount === 0}>
              全部已读
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <SummaryCard icon={<Bell size={24} />} title="未读通知" value={String(unreadCount)} />
        </Col>
        <Col xs={24} md={8}>
          <SummaryCard icon={<ShieldAlert size={24} />} title="授权状态" value={formatLicenseStatus(auth.license?.status)} />
        </Col>
        <Col xs={24} md={8}>
          <SummaryCard icon={<Clock size={24} />} title="最近刷新" value={new Date().toLocaleTimeString('zh-CN', { hour12: false })} />
        </Col>

        <Col xs={24}>
          <Card title="通知列表">
            {notifications.length === 0 ? (
              <Empty description="暂无通知" />
            ) : (
              <List
                itemLayout="horizontal"
                dataSource={notifications}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      item.unread ? (
                        <Button key="read" type="link" onClick={() => setReadIds(new Set(readIds).add(item.id))}>
                          标记已读
                        </Button>
                      ) : (
                        <Typography.Text key="read" type="secondary">
                          已读
                        </Typography.Text>
                      ),
                    ]}
                  >
                    <List.Item.Meta
                      avatar={<NotificationIcon type={item.type} />}
                      title={
                        <Space>
                          <Badge status={item.unread ? 'processing' : 'default'} />
                          <Typography.Text strong>{item.title}</Typography.Text>
                          <Tag>{formatNotificationType(item.type)}</Tag>
                        </Space>
                      }
                      description={
                        <Space direction="vertical" size={2}>
                          <Typography.Text>{item.detail}</Typography.Text>
                          <Typography.Text type="secondary">{item.time}</Typography.Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

function buildNotifications(auth: ReturnType<typeof useDesktopAuth>, readIds: Set<string>): NotificationItem[] {
  const items: NotificationItem[] = []

  if (auth.subscription?.status !== 'active') {
    items.push({
      id: 'subscription-not-active',
      title: '当前账号没有有效订阅',
      detail: '请完成套餐开通后再使用桌面端养号能力。',
      time: '实时状态',
      type: 'auth',
      unread: !readIds.has('subscription-not-active'),
    })
  }

  if (auth.license?.status && auth.license.status !== 'active') {
    items.push({
      id: `license-${auth.license.status}`,
      title: '当前 License 不可用',
      detail: `License 状态：${formatLicenseStatus(auth.license.status)}`,
      time: '实时状态',
      type: 'auth',
      unread: !readIds.has(`license-${auth.license.status}`),
    })
  }

  if (auth.entitlementWarning) {
    items.push({
      id: 'entitlement-warning',
      title: '授权状态暂时无法刷新',
      detail: auth.entitlementWarning,
      time: '实时状态',
      type: 'system',
      unread: !readIds.has('entitlement-warning'),
    })
  }

  items.push({
    id: 'desktop-productization',
    title: '桌面端产品化页面已启用',
    detail: '个人中心已包含账号信息、套餐中心、授权与设备、联系客服和消息通知。',
    time: '本地消息',
    type: 'system',
    unread: !readIds.has('desktop-productization'),
  })

  return items
}

function SummaryCard({ icon, title, value }: { icon: React.ReactNode; title: string; value: string }) {
  return (
    <Card>
      <Space size={14}>
        <div className="product-page-icon">{icon}</div>
        <div>
          <Typography.Text type="secondary">{title}</Typography.Text>
          <Typography.Title level={3}>{value}</Typography.Title>
        </div>
      </Space>
    </Card>
  )
}

function NotificationIcon({ type }: { type: NotificationItem['type'] }) {
  const icon = type === 'auth' ? <ShieldAlert size={20} /> : type === 'usage' ? <CheckCircle2 size={20} /> : <Megaphone size={20} />
  return <div className="notification-icon">{icon}</div>
}

function formatNotificationType(type: NotificationItem['type']) {
  if (type === 'auth') return '授权'
  if (type === 'usage') return '用量'
  return '系统'
}

function formatLicenseStatus(status?: string) {
  if (status === 'active') return '有效'
  if (status === 'expired') return '已过期'
  if (status === 'revoked') return '已撤销'
  if (status === 'inactive') return '未激活'
  if (status === 'not_configured') return '未配置'
  if (status === 'not_implemented') return '未实现'
  return '未知'
}
