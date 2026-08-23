import { Alert, Button, Card, Col, Descriptions, Form, Input, Row, Space, Tag, Typography, message } from 'antd'
import { Loader2, MessageSquareText, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useDesktopAuth } from '../app/DesktopAuthContext'
import { PageHeader } from '../components/PageHeader'
import {
  buildDesktopFeedbackWsUrl,
  submitDesktopFeedback,
  type DesktopFeedbackRealtimeEvent,
  type DesktopFeedbackThread,
} from '../services/desktopApi'

const CONTACT_PLACEHOLDER = '请联系项目对接人获取'

export function ContactSupportPage() {
  const auth = useDesktopAuth()
  const [form] = Form.useForm<{ category: string; content: string }>()
  const [submitting, setSubmitting] = useState(false)
  const [wsConnected, setWsConnected] = useState(false)
  const [thread, setThread] = useState<DesktopFeedbackThread | null>(null)
  const [lastSubmittedAt, setLastSubmittedAt] = useState<string | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const pendingRequestsRef = useRef(new Map<string, { resolve: () => void; reject: (error: Error) => void }>())

  useEffect(() => {
    if (!auth.session) return

    const socket = new WebSocket(buildDesktopFeedbackWsUrl(auth.session, auth.apiBaseUrl))
    socketRef.current = socket
    socket.onopen = () => setWsConnected(true)
    socket.onclose = () => setWsConnected(false)
    socket.onerror = () => setWsConnected(false)
    socket.onmessage = (event) => {
      const data = parseJson<DesktopFeedbackRealtimeEvent>(event.data)
      if (!data) return
      if (data.type === 'feedback.ack') {
        const pending = data.requestId ? pendingRequestsRef.current.get(data.requestId) : undefined
        if (pending) {
          pendingRequestsRef.current.delete(data.requestId as string)
          pending.resolve()
        }
        return
      }
      if (data.type === 'feedback.error') {
        const pending = data.requestId ? pendingRequestsRef.current.get(data.requestId) : undefined
        if (pending) {
          pendingRequestsRef.current.delete(data.requestId as string)
          pending.reject(new Error(formatSupportError(data.message || '反馈消息发送失败')))
          return
        }
        message.error(formatSupportError(data.message || '反馈消息同步失败'))
        return
      }
      if (data.type === 'feedback.thread.created' || data.type === 'feedback.message.created') {
        setThread(data.thread)
        return
      }
      if (data.type === 'feedback.thread.status.updated') {
        setThread(data.thread)
      }
    }

    return () => {
      pendingRequestsRef.current.forEach((pending) => pending.reject(new Error('页面已关闭，反馈发送已取消')))
      pendingRequestsRef.current.clear()
      socketRef.current = null
      socket.close()
    }
  }, [auth.apiBaseUrl, auth.session])

  const submitFeedback = async (values: { category: string; content: string }) => {
    if (!auth.session) return
    const content = [`问题类型：${values.category || '未填写'}`, `问题描述：${values.content}`].join('\n')
    setSubmitting(true)
    try {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        await sendFeedbackViaSocket(socketRef.current, pendingRequestsRef.current, content)
      } else {
        await submitDesktopFeedback(auth.session, { content, imageUrls: [] }, auth.apiBaseUrl)
      }
      form.resetFields()
      setLastSubmittedAt(new Date().toISOString())
      message.success('反馈已提交')
    } catch (error) {
      message.error(formatSupportError(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader title="联系客服" description="提交问题反馈，便于定位授权、登录或运行异常。" />

      <Row gutter={[16, 16]} className="contact-support-grid">
        <Col xs={24} lg={9}>
          <Card title="联系信息">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label={<InfoLabel icon={<MessageSquareText size={15} />} text="企业微信" />}>
                {CONTACT_PLACEHOLDER}
              </Descriptions.Item>
            </Descriptions>
            <Alert
              className="contact-hint"
              type="info"
              showIcon
              message="当前仅支持企业微信联系"
              description="如果企业微信还未配置，请联系项目对接人获取。"
            />
          </Card>
        </Col>

        <Col xs={24} lg={15}>
          <Card
            title="问题反馈"
            extra={
              <Space>
                {thread ? <Tag color={getFeedbackStatusColor(thread.status)}>{formatFeedbackStatus(thread.status)}</Tag> : null}
                <Tag color={wsConnected ? 'green' : 'default'}>{wsConnected ? '实时同步中' : '普通提交模式'}</Tag>
              </Space>
            }
          >
            <Form form={form} layout="vertical" onFinish={submitFeedback}>
              <Form.Item label="问题类型" name="category" rules={[{ max: 80, message: '问题类型不能超过80个字符' }]}>
                <Input placeholder="例如：登录授权、任务运行、浏览器环境、数据统计" />
              </Form.Item>
              <Form.Item
                label="问题描述"
                name="content"
                rules={[
                  { required: true, message: '请填写问题描述' },
                  { max: 4500, message: '问题描述不能超过4500个字符' },
                ]}
              >
                <Input.TextArea rows={6} placeholder="请描述出现问题的页面、操作步骤、错误提示和发生时间。" />
              </Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" icon={submitting ? <Loader2 size={16} /> : <Send size={16} />} loading={submitting}>
                  提交反馈
                </Button>
                <Typography.Text type="secondary">
                  {lastSubmittedAt ? `上次提交：${formatDateTime(lastSubmittedAt)}` : '反馈会提交到后台，请等待管理员处理。'}
                </Typography.Text>
              </Space>
            </Form>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

function InfoLabel({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <Space size={6}>
      {icon}
      <span>{text}</span>
    </Space>
  )
}

function formatFeedbackStatus(status: DesktopFeedbackThread['status']) {
  const labels: Record<DesktopFeedbackThread['status'], string> = {
    pending: '待处理',
    processing: '处理中',
    resolved: '已解决',
    closed: '已关闭',
  }
  return labels[status] || status
}

function getFeedbackStatusColor(status: DesktopFeedbackThread['status']) {
  const colors: Record<DesktopFeedbackThread['status'], string> = {
    pending: 'orange',
    processing: 'blue',
    resolved: 'green',
    closed: 'default',
  }
  return colors[status] || 'default'
}

function formatDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || '-'
  return date.toLocaleString()
}

function parseJson<T>(value: string): T | null {
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

function sendFeedbackViaSocket(
  socket: WebSocket,
  pendingRequests: Map<string, { resolve: () => void; reject: (error: Error) => void }>,
  content: string,
) {
  const requestId = createRequestId()
  return new Promise<void>((resolve, reject) => {
    pendingRequests.set(requestId, { resolve, reject })
    try {
      socket.send(JSON.stringify({ type: 'feedback.user_message.send', requestId, content, imageUrls: [] }))
    } catch {
      pendingRequests.delete(requestId)
      reject(new Error('反馈消息发送失败，请稍后重试'))
      return
    }
    window.setTimeout(() => {
      if (!pendingRequests.has(requestId)) return
      pendingRequests.delete(requestId)
      reject(new Error('反馈消息发送超时，请稍后重试'))
    }, 10_000)
  })
}

function createRequestId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function formatSupportError(error: unknown) {
  const messageText = error instanceof Error ? error.message : String(error)
  const normalized = messageText.trim()
  const translations: Record<string, string> = {
    'Failed to fetch': '暂时无法提交反馈，请稍后重试',
    'Invalid desktop session': '登录状态已失效，请重新登录后再提交反馈',
    Unauthorized: '登录状态已失效，请重新登录后再提交反馈',
  }
  if (translations[normalized]) return translations[normalized]
  if (/failed to fetch/i.test(normalized)) return translations['Failed to fetch']
  if (/unauthorized/i.test(normalized)) return translations.Unauthorized
  return normalized || '反馈提交失败，请稍后重试'
}
