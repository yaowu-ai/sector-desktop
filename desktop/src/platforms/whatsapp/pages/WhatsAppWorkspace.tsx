import { Alert, Button, Empty, Form, Input, Modal, Space, Spin, Tag, Typography } from 'antd'
import { Link2, RefreshCw, Settings2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { buildWorkspaceEmbedUrl, getWorkspaceUrl, normalizeWorkspaceUrl, sameOrigin, saveWorkspaceUrl, WHATSAPP_BRIDGE } from '../services/workspace'

interface Props {
  view: string
  themeMode: 'light' | 'dark'
  visible: boolean
  initialUrl?: string
  sessionContext?: string
  requestSsoTicket?(nonce: string, workspaceOrigin: string): Promise<{ ticket: string; expiresAt: number }>
  onViewChange(view: string): void
}

export function WhatsAppWorkspace({ view, themeMode, visible, initialUrl, sessionContext, requestSsoTicket, onViewChange }: Props) {
  const frame = useRef<HTMLIFrameElement>(null)
  const [baseUrl, setBaseUrl] = useState(() => initialUrl || getWorkspaceUrl())
  const [attempt, setAttempt] = useState(0)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [authenticated, setAuthenticated] = useState(false)
  const [workspaceName, setWorkspaceName] = useState('')
  const [authError, setAuthError] = useState('')
  const [authPending, setAuthPending] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [form] = Form.useForm()
  const latest = useRef({ view, themeMode, onViewChange, requestSsoTicket })
  latest.current = { view, themeMode, onViewChange, requestSsoTicket }
  // Deliberately keep the same frame across menu, theme and system-page changes.
  const src = useMemo(
    () => baseUrl ? buildWorkspaceEmbedUrl(baseUrl, latest.current.view, latest.current.themeMode, sessionContext) : '',
    [baseUrl, attempt, sessionContext],
  )
  const send = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    if (baseUrl) frame.current?.contentWindow?.postMessage({ channel: WHATSAPP_BRIDGE, type, ...payload }, baseUrl)
  }, [baseUrl])

  useEffect(() => {
    if (!src) return
    setStatus('loading')
    setAuthenticated(false)
    setWorkspaceName('')
    setAuthError('')
    setAuthPending(false)
    let active = true, pendingNonce = ''
    let signedOut: (() => void) | undefined
    const timeout = window.setTimeout(() => setStatus('error'), 15000)
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow || !sameOrigin(event.origin, baseUrl)) return
      const message = event.data
      if (!message || message.channel !== WHATSAPP_BRIDGE) return
      if (message.type === 'signed-out') { signedOut?.(); return }
      if (message.type === 'sso-error') {
        setAuthPending(false)
        setAuthError(typeof message.error === 'string' ? message.error : '统一登录未完成，请重试')
        return
      }
      if (message.type === 'sso-request') {
        if (typeof message.nonce !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(message.nonce) || pendingNonce === message.nonce) return
        const issue = latest.current.requestSsoTicket, nonce = message.nonce
        if (!issue) { send('sso-cancel'); setAuthError('请先登录桌面端'); return }
        pendingNonce = nonce
        setAuthPending(true)
        setAuthError('')
        void issue(nonce, baseUrl).then(result => {
          if (active && pendingNonce === nonce) send('sso-ticket', { nonce, ticket: result.ticket })
        }).catch(error => {
          if (!active || pendingNonce !== nonce) return
          setAuthPending(false)
          setAuthError(error instanceof Error ? error.message : '统一登录暂不可用，请重试')
          send('sso-cancel', { nonce })
        })
        return
      }
      if (!['ready', 'state'].includes(message.type)) return
      window.clearTimeout(timeout)
      setStatus('ready')
      setAuthenticated(message.authenticated === true)
      if (message.authenticated) setAuthError('')
      if (message.authenticated || message.bindingRequired) setAuthPending(false)
      setWorkspaceName(typeof message.workspaceName === 'string' ? message.workspaceName : '')
      if (message.type === 'ready') {
        send('theme', { theme: latest.current.themeMode })
        send('navigate', { view: latest.current.view })
        if (message.ssoEnabled && !message.authenticated) send('authenticate')
      } else if (typeof message.view === 'string') {
        latest.current.onViewChange(message.view)
      }
    }
    const beforeLogout = (event: Event) => {
      pendingNonce = ''
      const tasks = (event as CustomEvent<{ tasks: Promise<unknown>[] }>).detail.tasks
      tasks.push(new Promise<void>(resolve => { signedOut = resolve; send('sign-out') }))
    }
    window.addEventListener('message', receive)
    window.addEventListener('account-matrix:before-logout', beforeLogout)
    return () => {
      active = false
      signedOut?.()
      window.clearTimeout(timeout)
      window.removeEventListener('message', receive)
      window.removeEventListener('account-matrix:before-logout', beforeLogout)
    }
  }, [src, baseUrl, send])

  useEffect(() => { if (status === 'ready') send('navigate', { view }) }, [view, status, send])
  useEffect(() => { if (status === 'ready') send('theme', { theme: themeMode }) }, [themeMode, status, send])
  useEffect(() => {
    const refresh = () => { if (visible) status === 'ready' ? send('refresh') : setAttempt(value => value + 1) }
    window.addEventListener('account-matrix:refresh-whatsapp', refresh)
    return () => window.removeEventListener('account-matrix:refresh-whatsapp', refresh)
  }, [visible, status, send])

  return (
    <section className="wa-workspace" hidden={!visible} aria-label="WhatsApp 养号工作空间">
      <div className="wa-workspace-toolbar">
        <Space size={8}>
          <Link2 size={16} aria-hidden />
          <Typography.Text strong>WhatsApp</Typography.Text>
          <Tag color={status === 'ready' ? 'success' : status === 'error' ? 'error' : 'processing'}>
            {status === 'ready' ? authenticated ? '已连接' : authPending ? '正在统一登录' : '等待登录' : status === 'error' ? '连接未完成' : '正在连接'}
          </Tag>
          <Typography.Text type="secondary">{workspaceName || '养号工作空间'}</Typography.Text>
        </Space>
        <Button type="text" icon={<Settings2 size={16} />} onClick={() => { form.setFieldsValue({ url: baseUrl }); setSettingsOpen(true) }}>
          连接设置
        </Button>
      </div>
      {authError && <Alert type="warning" showIcon message={authError} action={<Button size="small" onClick={() => { setAuthError(''); send('authenticate') }}>重试登录</Button>} />}
      {!baseUrl ? (
        <div className="wa-workspace-placeholder">
          <Empty description="连接 WhatsApp 养号工作空间">
            <Typography.Paragraph type="secondary">填写现有养号服务地址，即可在桌面端管理账号与任务。</Typography.Paragraph>
            <Button type="primary" onClick={() => setSettingsOpen(true)}>配置服务地址</Button>
          </Empty>
        </div>
      ) : (
        <div className="wa-workspace-body">
          <iframe
            ref={frame}
            key={`${baseUrl}:${attempt}:${sessionContext || ''}`}
            src={src}
            title="WhatsApp 养号网页"
            className="wa-workspace-frame"
            allow="clipboard-write"
            referrerPolicy="no-referrer"
            sandbox="allow-scripts allow-same-origin allow-forms allow-downloads allow-modals allow-popups allow-popups-to-escape-sandbox"
            onError={() => setStatus('error')}
          />
          {status === 'loading' && <div className="wa-workspace-loading" role="status"><Space><Spin /><Typography.Text>正在打开养号工作空间…</Typography.Text></Space></div>}
          {status === 'error' && (
            <div className="wa-workspace-error">
              <Alert type="warning" showIcon message="尚未连接养号工作空间" description="请确认服务可访问，并已允许当前桌面端来源嵌入。">
              </Alert>
              <Space>
                <Button type="primary" icon={<RefreshCw size={16} />} onClick={() => setAttempt(value => value + 1)}>重新连接</Button>
                <Button onClick={() => { form.setFieldsValue({ url: baseUrl }); setSettingsOpen(true) }}>修改地址</Button>
              </Space>
            </div>
          )}
        </div>
      )}
      <Modal title="WhatsApp 连接设置" open={settingsOpen} onCancel={() => setSettingsOpen(false)} onOk={() => form.submit()} okText="保存并连接" cancelText="取消" destroyOnClose>
        <Typography.Paragraph type="secondary">已配置统一登录时自动进入工作空间；首次需要验证并绑定原养号账号。账号与任务由养号服务保存。</Typography.Paragraph>
        <Form form={form} layout="vertical" onFinish={({ url }) => {
          if (initialUrl) setBaseUrl(normalizeWorkspaceUrl(url))
          else setBaseUrl(saveWorkspaceUrl(url))
          setAttempt(value => value + 1)
          setSettingsOpen(false)
        }}>
          <Form.Item name="url" label="养号服务地址" rules={[{ required: true, message: '请填写服务地址' }, { validator: async (_, value) => {
            if (!value) return
            normalizeWorkspaceUrl(value)
          } }]}>
            <Input placeholder="https://your-whatsapp-service.example.com" autoComplete="url" />
          </Form.Item>
          <Typography.Text type="secondary">当前桌面端来源：{window.location.origin}</Typography.Text>
        </Form>
      </Modal>
    </section>
  )
}
