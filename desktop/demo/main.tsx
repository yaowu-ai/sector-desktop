// Separate Vite entry. This module is never imported by the shipped application.
import { App as AntdApp, Button, ConfigProvider, Result, Space, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { DesktopAuthContext, signOutEmbeddedWorkspaces } from '../src/app/DesktopAuthContext'
import { DesktopNotificationsProvider } from '../src/app/DesktopNotificationsContext'
import { PlatformProvider } from '../src/app/PlatformContext'
import { AppShell } from '../src/components/AppShell'
import type { DesktopSession } from '../src/services/desktopApi'
import '../src/styles/globals.css'
import './style.css'

localStorage.setItem('account-matrix-current-platform', 'whatsapp')
if (!window.location.hash) window.location.hash = 'home'
const demoOrigin = 'http://127.0.0.1:8789'
function demoSession(id: number, context = crypto.randomUUID()): DesktopSession {
  return { accessToken:`demo-sector-${id}`,expiresAt:Date.now()+3600000,userId:String(id),
    username:id===1?'sector-operator':'sector-observer',userName:id===1?'桌面运营员':'桌面观察员',
    phone:'',userRole:2,whatsappContext:context }
}

// Only the local demo entry supplies this mock. Production uses the native Tauri bridge.
Object.assign(window, { __TAURI_INTERNALS__: { invoke: async (command: string) => {
  if (command === 'load_scheduler_config') return { accounts: [] }
  if (command === 'get_current_run_status') return { status: 'idle', command: [], queuedAccounts: [], completedAccounts: [], stdoutLength: 0, stderrLength: 0 }
  if (command === 'get_home_summary') return { bitbrowser: { available: false }, todayPlannedTasks: 0, todayCompletedAccounts: 0, todayFailedAccounts: 0, todayTargetInteractions: 0 }
  if (command === 'load_accounts') return []
  if (command === 'get_project_paths') return { projectRoot: '本地交互演示', configPath: '示例配置', dataDir: '示例数据' }
  throw new Error('此项需要完整桌面运行环境；请切换到 WhatsApp 体验嵌入演示。')
} } })

function Demo() {
  const [mode, setMode] = useState<'light' | 'dark'>('light')
  const [session, setSession] = useState<DesktopSession|null>(() => {
    try { const saved=JSON.parse(sessionStorage.getItem('wa-sso-demo-desktop')||'null')
      if(saved?.id&&saved.context)return demoSession(saved.id===2?2:1,saved.context)
    }catch{}
    return demoSession(1)
  })
  const [changing, setChanging] = useState(false)
  const logout = async () => { await signOutEmbeddedWorkspaces();setSession(null);sessionStorage.removeItem('wa-sso-demo-desktop') }
  const switchUser = async () => {
    setChanging(true)
    try { await logout();setSession(demoSession(session?.userId==='1'?2:1)) }finally{setChanging(false)}
  }
  const resetBinding = async () => {
    setChanging(true)
    try { await logout();await fetch(`${demoOrigin}/demo/reset`,{method:'POST'});setSession(demoSession(1)) }
    finally { setChanging(false) }
  }
  useEffect(() => { if(session)sessionStorage.setItem('wa-sso-demo-desktop',JSON.stringify({id:Number(session.userId),context:session.whatsappContext})) },[session])
  useEffect(() => { document.documentElement.dataset.theme = mode }, [mode])
  return (
    <ConfigProvider locale={zhCN} theme={{ algorithm: mode === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm, token: {
      colorPrimary: mode === 'dark' ? '#76a9ff' : '#3662ec', borderRadius: 10, controlHeight: 36,
      colorBgContainer: mode === 'dark' ? '#111d31' : '#ffffff',
      fontFamily: '"PingFang SC", "Microsoft YaHei", sans-serif',
    } }}>
      <AntdApp>
        <DesktopAuthContext.Provider value={{
          apiBaseUrl: 'http://127.0.0.1:8790/api/desktop', session, device: null, subscription: null, license: null,
          loading: false, error: null, entitlementWarning: null,
          login: async () => ({ authorized: false }), refreshEntitlement: async () => {},
          unbindCurrentDevice: async () => {}, logout,
        }}>
          <PlatformProvider>
            <DesktopNotificationsProvider>
              <div className="wa-demo-label" role="note">统一登录演示 · 隔离示例数据</div>
              {session ? <AppShell themeMode={mode} onThemeModeChange={setMode} whatsappWorkspaceUrl={demoOrigin} />
                : <Result title="已退出桌面和 WA 会话" subTitle="重新登录同一演示用户，可验证已绑定账号自动进入。" extra={<Button type="primary" onClick={()=>setSession(demoSession(1))}>重新登录演示运营员</Button>} />}
              <div className="wa-demo-controls">
                <strong>SSO 演示 · 不连接真实 WhatsApp</strong>
                <span>桌面：{session?.username||'已退出'}</span>
                <span>首次绑定邮箱：{session?.userId==='2'?'viewer':'demo'}@account-matrix.local</span>
                <span>示例 WA 密码：DemoOnly2026!</span>
                <Space><Button size="small" loading={changing} onClick={()=>void switchUser()}>切换演示用户</Button><Button size="small" loading={changing} onClick={()=>void resetBinding()}>重置绑定演示</Button></Space>
              </div>
            </DesktopNotificationsProvider>
          </PlatformProvider>
        </DesktopAuthContext.Provider>
      </AntdApp>
    </ConfigProvider>
  )
}
createRoot(document.getElementById('root')!).render(<Demo />)
