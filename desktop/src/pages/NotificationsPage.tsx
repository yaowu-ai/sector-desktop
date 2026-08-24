import { Badge, Button, Card, Col, Empty, List, Row, Segmented, Space, Tag, Typography, message } from 'antd'
import { Bell, Headphones, Megaphone, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { useDesktopNotifications } from '../app/DesktopNotificationsContext'
import { PageHeader } from '../components/PageHeader'
import {
  type DesktopNotification,
  type DesktopNotificationCategory,
} from '../services/desktopApi'

type NotificationFilter = 'all' | DesktopNotificationCategory
const NOTIFICATION_PAGE_SIZE = 10

export function NotificationsPage() {
  const {
    notifications,
    loading,
    unreadCount,
    refreshNotifications,
    markRead: markNotificationRead,
    markAllRead: markAllNotificationsRead,
  } = useDesktopNotifications()
  const [filter, setFilter] = useState<NotificationFilter>('all')
  const [currentPage, setCurrentPage] = useState(1)

  const filteredNotifications = useMemo(() => {
    if (filter === 'all') return notifications
    return notifications.filter((item) => item.category === filter)
  }, [filter, notifications])
  const pagedNotifications = useMemo(() => {
    const start = (currentPage - 1) * NOTIFICATION_PAGE_SIZE
    return filteredNotifications.slice(start, start + NOTIFICATION_PAGE_SIZE)
  }, [currentPage, filteredNotifications])

  const systemCount = notifications.filter((item) => item.category === 'system').length
  const supportCount = notifications.filter((item) => item.category === 'support').length

  useEffect(() => {
    setCurrentPage(1)
  }, [filter])

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(filteredNotifications.length / NOTIFICATION_PAGE_SIZE))
    if (currentPage > maxPage) setCurrentPage(maxPage)
  }, [currentPage, filteredNotifications.length])

  const markRead = async (item: DesktopNotification) => {
    try {
      await markNotificationRead(item)
    } catch (error) {
      message.error(formatNotificationError(error))
    }
  }

  const markAllRead = async () => {
    try {
      await markAllNotificationsRead()
      message.success('已全部标记为已读')
    } catch (error) {
      message.error(formatNotificationError(error))
    }
  }

  return (
    <div>
      <PageHeader
        title="消息通知"
        description="查看系统公告和客服回复。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} onClick={() => void refreshNotifications()} loading={loading}>
              刷新
            </Button>
            <Button onClick={() => void markAllRead()} disabled={unreadCount === 0}>
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
          <SummaryCard icon={<Megaphone size={24} />} title="系统消息" value={String(systemCount)} />
        </Col>
        <Col xs={24} md={8}>
          <SummaryCard icon={<Headphones size={24} />} title="客服消息" value={String(supportCount)} />
        </Col>

        <Col xs={24}>
          <Card
            title="通知列表"
            extra={
              <Segmented
                value={filter}
                onChange={(value) => setFilter(value as NotificationFilter)}
                options={[
                  { label: '全部', value: 'all' },
                  { label: <FilterLabel category="system" />, value: 'system' },
                  { label: <FilterLabel category="support" />, value: 'support' },
                ]}
              />
            }
          >
            {filteredNotifications.length === 0 ? (
              <Empty description="暂无通知" />
            ) : (
              <List
                itemLayout="horizontal"
                dataSource={pagedNotifications}
                pagination={
                  filteredNotifications.length > NOTIFICATION_PAGE_SIZE
                    ? {
                        current: currentPage,
                        pageSize: NOTIFICATION_PAGE_SIZE,
                        total: filteredNotifications.length,
                        showSizeChanger: false,
                        showTotal: (total, range) => `显示 ${range[0]}-${range[1]} / ${total} 条`,
                        onChange: setCurrentPage,
                      }
                    : false
                }
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      !item.read ? (
                        <Button key="read" type="link" onClick={() => void markRead(item)}>
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
                      avatar={<NotificationIcon category={item.category} />}
                      title={
                        <Space wrap>
                          <Badge status={!item.read ? 'processing' : 'default'} />
                          <Typography.Text strong>{item.title}</Typography.Text>
                          <Tag className={notificationTagClassName(item.category)}>
                            {formatNotificationCategory(item.category)}
                          </Tag>
                          {item.priority && item.priority !== 'normal' ? <Tag color={item.priority === 'urgent' ? 'red' : 'orange'}>{formatPriority(item.priority)}</Tag> : null}
                        </Space>
                      }
                      description={
                        <Space direction="vertical" size={2}>
                          <Typography.Text>{item.content}</Typography.Text>
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

function NotificationIcon({ category }: { category: DesktopNotificationCategory }) {
  const icon = category === 'support' ? <Headphones size={20} /> : <Megaphone size={20} />
  return <div className="notification-icon">{icon}</div>
}

function FilterLabel({ category }: { category: DesktopNotificationCategory }) {
  return <span className={notificationFilterClassName(category)}>{formatNotificationCategory(category)}</span>
}

function notificationTagClassName(category: DesktopNotificationCategory) {
  return `notification-category-tag notification-category-tag-${category}`
}

function notificationFilterClassName(category: DesktopNotificationCategory) {
  return `notification-filter-label notification-filter-label-${category}`
}

function formatNotificationCategory(category: DesktopNotificationCategory) {
  return category === 'support' ? '客服消息' : '系统消息'
}

function formatPriority(priority?: DesktopNotification['priority']) {
  if (priority === 'urgent') return '紧急'
  if (priority === 'important') return '重要'
  return '普通'
}

function formatNotificationError(error: unknown) {
  return error instanceof Error ? error.message : '通知加载失败，请稍后重试'
}
