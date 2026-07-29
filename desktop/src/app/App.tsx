import { App as AntdApp, ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { useEffect, useMemo, useState } from 'react'

import { PlatformProvider } from './PlatformContext'
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
        colorPrimary: themeMode === 'dark' ? '#60a5fa' : '#2563eb',
        colorInfo: themeMode === 'dark' ? '#60a5fa' : '#2563eb',
        colorLink: themeMode === 'dark' ? '#93c5fd' : '#2563eb',
        borderRadius: 6,
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif',
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
        <PlatformProvider>
          <AppShell themeMode={themeMode} onThemeModeChange={setThemeMode} />
        </PlatformProvider>
      </AntdApp>
    </ConfigProvider>
  )
}
