import { App as AntdApp, ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { useEffect, useMemo, useState } from 'react'

import { PlatformProvider } from './PlatformContext'
import { DesktopAuthGate, DesktopAuthProvider } from './DesktopAuthContext'
import { DesktopNotificationsProvider } from './DesktopNotificationsContext'
import { AppShell } from '../components/AppShell'

type ThemeMode = 'light' | 'dark'

export function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    const saved = window.localStorage.getItem('account-matrix-theme')
    return saved === 'dark' ? 'dark' : 'light'
  })

  useEffect(() => {
    window.localStorage.setItem('account-matrix-theme', themeMode)
    document.documentElement.dataset.theme = themeMode
  }, [themeMode])

  const themeConfig = useMemo(
    () => ({
      algorithm: themeMode === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm,
      token: {
        colorPrimary: themeMode === 'dark' ? '#76a9ff' : '#3662ec',
        colorInfo: themeMode === 'dark' ? '#76a9ff' : '#3662ec',
        colorLink: themeMode === 'dark' ? '#a9c7ff' : '#3662ec',
        colorBgLayout: themeMode === 'dark' ? '#0d1729' : '#eef4fc',
        colorBgContainer: themeMode === 'dark' ? '#111d31' : '#ffffff',
        colorBorder: themeMode === 'dark' ? '#2a3c58' : '#dbe7f6',
        colorText: themeMode === 'dark' ? '#eef4ff' : '#182b49',
        colorTextSecondary: themeMode === 'dark' ? '#a9b9d0' : '#667892',
        borderRadius: 10,
        controlHeight: 36,
        controlHeightSM: 32,
        fontFamily:
          '"Source Han Sans CN", "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      },
    }),
    [themeMode],
  )

  return (
    <ConfigProvider
      locale={zhCN}
      theme={themeConfig}
    >
      <AntdApp>
        <DesktopAuthProvider>
          <DesktopAuthGate>
            <PlatformProvider>
              <DesktopNotificationsProvider>
                <AppShell themeMode={themeMode} onThemeModeChange={setThemeMode} />
              </DesktopNotificationsProvider>
            </PlatformProvider>
          </DesktopAuthGate>
        </DesktopAuthProvider>
      </AntdApp>
    </ConfigProvider>
  )
}
