import { Alert, Button, Card, Form, Input, Space, Typography, message } from 'antd'
import { LockKeyhole, Server, UserRound } from 'lucide-react'
import { useState } from 'react'

interface DesktopLoginPageProps {
  apiBaseUrl: string
  error: string | null
  onLogin: (values: { apiBaseUrl: string; username: string; password: string }) => Promise<{ authorized: boolean }>
}

export function DesktopLoginPage({ apiBaseUrl, error, onLogin }: DesktopLoginPageProps) {
  const [submitting, setSubmitting] = useState(false)

  const submit = async (values: { apiBaseUrl: string; username: string; password: string }) => {
    setSubmitting(true)
    try {
      const result = await onLogin(values)
      if (result.authorized) {
        message.success('登录成功')
      } else {
        message.warning('登录成功，但当前账号暂无可用授权')
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="desktop-login-page">
      <Card className="desktop-login-card">
        <Space direction="vertical" size={20} className="full-width">
          <div>
            <Typography.Title level={2} style={{ marginBottom: 4 }}>
              星域桌面端
            </Typography.Title>
            <Typography.Text type="secondary">登录产品账号后使用本机养号工具。</Typography.Text>
          </div>
          {error ? <Alert type="error" showIcon message={error} /> : null}
          <Form
            layout="vertical"
            requiredMark={false}
            initialValues={{ apiBaseUrl, username: '' }}
            onFinish={submit}
          >
            <Form.Item
              name="apiBaseUrl"
              label="服务端接口地址"
              rules={[{ required: true, message: '请输入服务端接口地址' }]}
            >
              <Input prefix={<Server size={16} />} placeholder="http://localhost:3000/api/desktop" />
            </Form.Item>
            <Form.Item
              name="username"
              label="产品账号"
              rules={[{ required: true, message: '请输入手机号、邮箱或用户名' }]}
            >
              <Input prefix={<UserRound size={16} />} placeholder="手机号、邮箱或用户名" autoComplete="username" />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password prefix={<LockKeyhole size={16} />} placeholder="密码" autoComplete="current-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" block size="large" loading={submitting}>
              登录并检查授权
            </Button>
          </Form>
        </Space>
      </Card>
    </div>
  )
}
