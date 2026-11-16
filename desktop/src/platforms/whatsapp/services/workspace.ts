export const WHATSAPP_BRIDGE = 'account-matrix:whatsapp:v1'
const STORAGE_KEY = 'account-matrix-whatsapp-workspace'

export function normalizeWorkspaceUrl(value: string): string {
  const url = new URL(value.trim())
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback)) {
    throw new Error('请填写 HTTPS 地址；本地开发可使用 localhost 或 127.0.0.1。')
  }
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('请填写养号服务的站点地址，不包含路径、参数或登录凭据。')
  }
  return url.origin
}

export function getWorkspaceUrl(): string {
  const value = localStorage.getItem(STORAGE_KEY) || import.meta.env.VITE_WHATSAPP_WORKSPACE_URL || ''
  if (!value) return ''
  try { return normalizeWorkspaceUrl(value) } catch { return '' }
}

export function saveWorkspaceUrl(value: string) {
  const url = normalizeWorkspaceUrl(value)
  localStorage.setItem(STORAGE_KEY, url)
  return url
}

export function buildWorkspaceEmbedUrl(base: string, view: string, theme: string, context?: string) {
  const url = new URL('/embed', base)
  url.searchParams.set('parentOrigin', window.location.origin)
  url.searchParams.set('view', view)
  url.searchParams.set('theme', theme)
  if (context) url.searchParams.set('context', context)
  return url.href
}

// WebView2/WKWebView versions vary; keep URL parsing as a compatibility fallback.
export function sameOrigin(candidate: string, expected: string) {
  try {
    if (candidate === 'null' || expected === 'null') return false
    const originApi = (globalThis as typeof globalThis & {
      Origin?: { from(value: string): { isSameOrigin(other: unknown): boolean } }
    }).Origin
    if (originApi) return originApi.from(candidate).isSameOrigin(originApi.from(expected))
    return new URL(candidate).origin === new URL(expected).origin
  } catch { return false }
}
