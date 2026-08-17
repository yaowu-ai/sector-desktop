import { Alert, Button, Layout, Menu, Space, Switch, Tooltip, Typography, message } from 'antd'
import { Moon, RefreshCw, Sun } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { appRoutes, routes } from '../app/routes'
import { PROCESS_STARTED_EVENT, checkBitbrowserApi, getCurrentRunStatus } from '../services/api'
import { runStatusLabel } from '../services/runStatus'
import type { ApiStatus, ProcessStatus } from '../services/types'
import { PlatformSelector } from './PlatformSelector'
import { RouteScopeFrame } from './RouteScopeFrame'
import { StatusTag, type StatusTone } from './StatusTag'

const { Header, Sider, Content } = Layout

const TASK_POLL_MS = 1500
const BITBROWSER_POLL_MS = 10000

interface AppShellProps {
  themeMode: 'light' | 'dark'
  onThemeModeChange: (mode: 'light' | 'dark') => void
}

export function AppShell({ themeMode, onThemeModeChange }: AppShellProps) {
  const contentRef = useRef<HTMLElement>(null)
  const [activeKey, setActiveKey] = useState(getInitialRouteKey)
  const [bitbrowserStatus, setBitbrowserStatus] = useState<ApiStatus | null>(null)
  const [processStatus, setProcessStatus] = useState<ProcessStatus | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [shellError, setShellError] = useState<string | null>(null)

  const activeRoute = useMemo(
    () => appRoutes.find((route) => route.key === activeKey) ?? routes[0],
    [activeKey],
  )

  const refreshBitbrowser = useCallback(async () => {
    const nextStatus = await checkBitbrowserApi()
    setBitbrowserStatus(nextStatus)
    return nextStatus
  }, [])

  const refreshTask = useCallback(async () => {
    const nextStatus = await getCurrentRunStatus()
    setProcessStatus(nextStatus)
    return nextStatus
  }, [])

  const refreshAll = useCallback(async () => {
    setRefreshing(true)
    setShellError(null)
    try {
      await Promise.all([refreshBitbrowser(), refreshTask()])
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      setShellError(detail)
      message.error(detail)
    } finally {
      setRefreshing(false)
    }
  }, [refreshBitbrowser, refreshTask])

  useEffect(() => {
    window.location.hash = activeKey
  }, [activeKey])

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, left: 0 })
  }, [activeKey])

  useEffect(() => {
    const onHashChange = () => {
      setActiveKey(getInitialRouteKey())
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    void refreshAll()
  }, [])

  useEffect(() => {
    const onProcessStarted = () => {
      void refreshTask().catch(handleBackgroundError(setShellError))
    }
    window.addEventListener(PROCESS_STARTED_EVENT, onProcessStarted)
    return () => window.removeEventListener(PROCESS_STARTED_EVENT, onProcessStarted)
  }, [refreshTask])

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshTask().catch(handleBackgroundError(setShellError))
    }, TASK_POLL_MS)
    return () => window.clearInterval(id)
  }, [refreshTask])

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshBitbrowser().catch(handleBackgroundError(setShellError))
    }, BITBROWSER_POLL_MS)
    return () => window.clearInterval(id)
  }, [refreshBitbrowser])

  return (
    <Layout className="app-shell">
      <Sider width={192} className="app-sider">
        <div className="app-brand">
          <Typography.Title level={4}>星域</Typography.Title>
          <Typography.Text type="secondary">PC 端养号 V1</Typography.Text>
        </div>
        <Menu
          mode="inline"
          selectedKeys={routes.some((route) => route.key === activeKey) ? [activeKey] : []}
          onClick={({ key }) => setActiveKey(key)}
          items={routes.map((route) => {
            const Icon = route.icon
            return {
              key: route.key,
              icon: <Icon size={18} />,
              label: route.label,
            }
          })}
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space size={16} wrap>
            <PlatformSelector onOpenSettings={() => setActiveKey('platforms')} />
            <Space size={12} wrap>
              <Tooltip title={bitbrowserStatus?.error ?? bitbrowserStatus?.apiUrl ?? '尚未检测'}>
                <span>
                  <StatusTag status={bitbrowserTone(bitbrowserStatus)} label={bitbrowserLabel(bitbrowserStatus)} />
                </span>
              </Tooltip>
              <StatusTag status={processTone(processStatus)} label={processLabel(processStatus)} />
            </Space>
          </Space>
          <Space size={12}>
            <Tooltip title={themeMode === 'dark' ? '切换为浅色模式' : '切换为深色模式'}>
              <Switch
                checked={themeMode === 'dark'}
                checkedChildren={<Moon size={14} />}
                unCheckedChildren={<Sun size={14} />}
                onChange={(checked) => onThemeModeChange(checked ? 'dark' : 'light')}
              />
            </Tooltip>
            <Button icon={<RefreshCw size={16} />} onClick={refreshAll} loading={refreshing}>
              刷新
            </Button>
          </Space>
        </Header>
        <Content ref={contentRef} className="app-content">
          {shellError ? (
            <Alert
              className="shell-alert"
              type="error"
              showIcon
              closable
              message="桌面端状态刷新失败"
              description={shellError}
              onClose={() => setShellError(null)}
            />
          ) : null}
          <RouteScopeFrame
            routeKey={activeRoute.key}
            routeLabel={activeRoute.label}
            scope={activeRoute.scope}
            capability={activeRoute.capability}
          >
            {activeRoute.element}
          </RouteScopeFrame>
        </Content>
      </Layout>
    </Layout>
  )
}

function getInitialRouteKey() {
  const hashKey = window.location.hash.replace(/^#/, '')
  if (hashKey === 'targets') {
    return 'target-engagement'
  }
  return appRoutes.some((route) => route.key === hashKey) ? hashKey : routes[0].key
}

function bitbrowserTone(status: ApiStatus | null): StatusTone {
  if (!status) return 'idle'
  return status.available ? 'ok' : 'error'
}

function bitbrowserLabel(status: ApiStatus | null) {
  if (!status) return 'BitBrowser API 待检测'
  return status.available ? 'BitBrowser API 在线' : 'BitBrowser API 不可用'
}

function processTone(status: ProcessStatus | null): StatusTone {
  if (!status || status.status === 'idle') return 'idle'
  if (status.status === 'running' || status.status === 'starting') return 'running'
  if (status.status === 'intervention_required') return 'warning'
  if (status.status === 'failed' || status.status === 'partial_failed') return 'error'
  return 'warning'
}

function processLabel(status: ProcessStatus | null) {
  if (!status) return '当前任务待检测'
  if (status.status === 'idle') return '当前任务空闲'
  return `当前任务：${runStatusLabel(status.status)}`
}

function handleBackgroundError(setShellError: (value: string) => void) {
  return (error: unknown) => {
    setShellError(error instanceof Error ? error.message : String(error))
  }
}
