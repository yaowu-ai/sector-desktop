import type { AiCommentGenerationResult, AiCommentSettings, Platform } from './types'

const API_BASE_STORAGE_KEY = 'account-matrix-desktop-api-base-url'
const SESSION_STORAGE_KEY = 'account-matrix-desktop-session'
const DEVICE_FINGERPRINT_STORAGE_KEY = 'account-matrix-device-fingerprint'

const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_DESKTOP_API_BASE_URL || 'http://localhost:3000/api/desktop'
const DEFAULT_LICENSE_PUBLIC_KEY = import.meta.env.VITE_LICENSE_PUBLIC_KEY || ''
const DEFAULT_DESKTOP_USER_ROLE = 2

export interface DesktopApiEnvelope<T> {
  success: boolean
  code: number
  desc: string
  data?: T
  details?: unknown
}

export interface DesktopSession {
  accessToken: string
  expiresAt: number
  username: string
  userId: string
  userName: string
  phone: string
  userRole: 1 | 2
}

export interface DesktopAuthResponse {
  accessToken: string
  expiresIn: number
  user?: {
    userId: string
    userName: string
    phone: string
    userRole: 1 | 2
  }
}

export interface DesktopDeviceResponse {
  deviceId: string
  deviceFingerprint: string
  deviceName: string
  status: 'active' | 'inactive'
  updateTime: string
}

export interface DesktopPlanItem {
  planId: string
  planName: string
  planCode: string
  priceCents: string
  limits: {
    maxEnabledAccounts: number
    maxDevices: number
    dailyTaskRuns: number
    scheduler: boolean
    targetEngagement: boolean
    exportCsv: boolean
    aiComment: boolean
  } | null
  status: 'active' | 'disabled'
}

export interface DesktopPlansResponse {
  plans: DesktopPlanItem[]
  source: 'placeholder' | 'configured'
}

export interface DesktopSubscriptionCurrentResponse {
  subscriptionId: string | null
  planId: string | null
  status: 'active' | 'expired' | 'none' | 'not_configured'
  expiresAt: string | null
  source: 'placeholder' | 'configured'
}

export interface DesktopLicenseCurrentResponse {
  licenseId: string | null
  status: 'active' | 'inactive' | 'expired' | 'revoked' | 'not_configured' | 'not_implemented'
  claims: Record<string, unknown> | null
  signature: string | null
  algorithm: 'Ed25519' | null
  signedPayload: string | null
  source: 'placeholder' | 'configured'
}

export interface DesktopUsageReportResponse {
  recorded: boolean
  metricKey: string
  metricDate: string
  status: 'ok'
}

export type DesktopUpdatePlatform = 'windows' | 'macos' | 'linux'
export type DesktopUpdateArch = 'x64' | 'arm64'

export interface DesktopDownloadOptionResponse {
  platform: DesktopUpdatePlatform
  arch: DesktopUpdateArch
  label: string
  url: string
  available: boolean
  version?: string
}

export interface DesktopDownloadOptionsResponse {
  version?: string
  releaseUrl?: string
  options: DesktopDownloadOptionResponse[]
}

export type DesktopBroadcastNotificationType = 'system' | 'maintenance' | 'risk' | 'feature'
export type DesktopBroadcastNotificationPriority = 'normal' | 'important' | 'urgent'
export type DesktopBroadcastNotificationStatus = 'draft' | 'published' | 'revoked'
export type DesktopNotificationCategory = 'system' | 'support'
export type DesktopNotificationSource = 'broadcast' | 'feedback'

export interface DesktopNotification {
  id: string
  source: DesktopNotificationSource
  sourceId: string
  category: DesktopNotificationCategory
  title: string
  content: string
  time: string
  read: boolean
  readAt: string | null
  priority?: DesktopBroadcastNotificationPriority
  broadcastType?: DesktopBroadcastNotificationType
  threadId?: string
}

export interface DesktopBroadcastNotificationsResponse {
  notifications: DesktopNotification[]
}

export interface DesktopFeedbackCreateResponse {
  threadId: string
  messageId: string
  status: 'created'
}

export interface DesktopAiCommentGenerateRequest {
  platform?: Platform
  title: string
  description?: string
  settings: Pick<AiCommentSettings, 'language' | 'timeoutSeconds' | 'maxCommentLength' | 'blockedWords'>
}

export function getDesktopApiBaseUrl() {
  return normalizeApiBaseUrl(window.localStorage.getItem(API_BASE_STORAGE_KEY) || DEFAULT_API_BASE_URL)
}

export function getLicensePublicKey() {
  return normalizePemEnvValue(DEFAULT_LICENSE_PUBLIC_KEY)
}

export function hasLicensePublicKey() {
  return getLicensePublicKey().length > 0
}

export function saveDesktopApiBaseUrl(value: string) {
  window.localStorage.setItem(API_BASE_STORAGE_KEY, normalizeApiBaseUrl(value))
}

export function loadDesktopSession(): DesktopSession | null {
  const raw = window.localStorage.getItem(SESSION_STORAGE_KEY)
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw) as DesktopSession & {
      email?: unknown
      mail?: unknown
      userEmail?: unknown
    }
    const { email: _email, mail: _mail, userEmail: _userEmail, ...session } = parsed
    if (!session.accessToken || !session.expiresAt || !session.username) return null
    if (session.expiresAt <= Date.now()) {
      clearDesktopSession()
      return null
    }
    const normalized: DesktopSession = {
      ...session,
      userId: session.userId || '',
      userName: session.userName || session.username,
      phone: session.phone || '',
      userRole: normalizeUserRole(session.userRole),
    }
    if (typeof _email !== 'undefined' || typeof _mail !== 'undefined' || typeof _userEmail !== 'undefined') {
      saveDesktopSession(normalized)
    }
    return normalized
  } catch {
    clearDesktopSession()
    return null
  }
}

export function saveDesktopSession(session: DesktopSession) {
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session))
}

export function clearDesktopSession() {
  window.localStorage.removeItem(SESSION_STORAGE_KEY)
}

export function buildDesktopSession(username: string, response: DesktopAuthResponse): DesktopSession {
  return {
    username,
    userId: response.user?.userId || '',
    userName: response.user?.userName || username,
    phone: response.user?.phone || '',
    userRole: normalizeUserRole(response.user?.userRole),
    accessToken: response.accessToken,
    expiresAt: Date.now() + response.expiresIn * 1000,
  }
}

export function getDeviceFingerprint() {
  const saved = window.localStorage.getItem(DEVICE_FINGERPRINT_STORAGE_KEY)
  if (saved) return saved

  const next =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  window.localStorage.setItem(DEVICE_FINGERPRINT_STORAGE_KEY, next)
  return next
}

export function getDeviceName() {
  const platform = navigator.platform || 'Desktop'
  return `Account Matrix ${platform}`
}

export function desktopLogin(username: string, password: string, apiBaseUrl = getDesktopApiBaseUrl()) {
  return desktopApiRequest<DesktopAuthResponse>(
    apiBaseUrl,
    '/auth/login',
    {
      method: 'POST',
      body: { username, password },
    },
  )
}

export function desktopRefresh(session: DesktopSession, apiBaseUrl = getDesktopApiBaseUrl()) {
  return desktopApiRequest<DesktopAuthResponse>(
    apiBaseUrl,
    '/auth/refresh',
    {
      method: 'POST',
      token: session.accessToken,
    },
  )
}

export function activateDesktopDevice(session: DesktopSession, apiBaseUrl = getDesktopApiBaseUrl()) {
  return desktopApiRequest<DesktopDeviceResponse>(
    apiBaseUrl,
    '/devices/activate',
    {
      method: 'POST',
      token: session.accessToken,
      body: {
        deviceFingerprint: getDeviceFingerprint(),
        deviceName: getDeviceName(),
      },
    },
  )
}

export function deactivateDesktopDevice(session: DesktopSession, apiBaseUrl = getDesktopApiBaseUrl()) {
  return desktopApiRequest<DesktopDeviceResponse>(
    apiBaseUrl,
    '/devices/deactivate',
    {
      method: 'POST',
      token: session.accessToken,
      body: {
        deviceFingerprint: getDeviceFingerprint(),
      },
    },
  )
}

export function loadDesktopPlans(session: DesktopSession, apiBaseUrl = getDesktopApiBaseUrl()) {
  return desktopApiRequest<DesktopPlansResponse>(
    apiBaseUrl,
    '/plans',
    {
      method: 'GET',
      token: session.accessToken,
    },
  )
}

export function loadCurrentSubscription(session: DesktopSession, apiBaseUrl = getDesktopApiBaseUrl()) {
  return desktopApiRequest<DesktopSubscriptionCurrentResponse>(
    apiBaseUrl,
    '/subscription/current',
    {
      method: 'GET',
      token: session.accessToken,
    },
  )
}

export function loadCurrentLicense(session: DesktopSession, apiBaseUrl = getDesktopApiBaseUrl()) {
  const query = new URLSearchParams({ deviceFingerprint: getDeviceFingerprint() })
  return desktopApiRequest<DesktopLicenseCurrentResponse>(
    apiBaseUrl,
    `/license/current?${query.toString()}`,
    {
      method: 'GET',
      token: session.accessToken,
    },
  )
}

export async function loadVerifiedCurrentLicense(session: DesktopSession, apiBaseUrl = getDesktopApiBaseUrl()) {
  const license = await loadCurrentLicense(session, apiBaseUrl)
  await verifyDesktopLicense(license)
  return license
}

export async function verifyDesktopLicense(license: DesktopLicenseCurrentResponse) {
  if (license.status !== 'active') return

  try {
    if (!license.claims || !license.signedPayload || !license.signature || license.algorithm !== 'Ed25519') {
      throw new Error('License 签名信息不完整')
    }

    if (!hasLicensePublicKey()) {
      throw new Error('桌面端缺少 License 公钥配置')
    }

    const expectedPayload = stableStringify(license.claims)
    if (license.signedPayload !== expectedPayload) {
      throw new Error('License 载荷与签名内容不一致')
    }

    const publicKey = await crypto.subtle.importKey(
      'spki',
      parsePemToBytes(getLicensePublicKey(), 'License 公钥格式无效，请检查桌面端 VITE_LICENSE_PUBLIC_KEY 配置'),
      { name: 'Ed25519' },
      false,
      ['verify'],
    )
    const ok = await crypto.subtle.verify(
      { name: 'Ed25519' },
      publicKey,
      base64ToBytes(license.signature, 'License 签名格式无效'),
      new TextEncoder().encode(license.signedPayload),
    )

    if (!ok) {
      throw new Error('License 签名校验失败')
    }
  } catch (error) {
    throw new Error(formatLicenseVerificationError(error))
  }
}

export function desktopLicenseAllowsAiComment(license: DesktopLicenseCurrentResponse | null) {
  return readDesktopLicenseLimits(license).aiComment
}

export function readDesktopLicenseLimits(license: DesktopLicenseCurrentResponse | null) {
  const limits = license?.claims?.limits
  if (!limits || typeof limits !== 'object' || Array.isArray(limits)) return DEFAULT_DESKTOP_LIMITS
  const record = limits as Record<string, unknown>
  return {
    maxEnabledAccounts: readLimitNumber(record.maxEnabledAccounts),
    maxDevices: readLimitNumber(record.maxDevices),
    dailyTaskRuns: readLimitNumber(record.dailyTaskRuns),
    scheduler: record.scheduler === true,
    targetEngagement: record.targetEngagement === true,
    exportCsv: record.exportCsv === true,
    aiComment: record.aiComment === true,
  }
}

export function reportDesktopUsage(
  session: DesktopSession,
  payload: { metricKey: string; metricValue: string | number; metricDate?: string },
  apiBaseUrl = getDesktopApiBaseUrl(),
) {
  return desktopApiRequest<DesktopUsageReportResponse>(
    apiBaseUrl,
    '/usage/report',
    {
      method: 'POST',
      token: session.accessToken,
      body: {
        ...payload,
        deviceFingerprint: getDeviceFingerprint(),
      },
    },
  )
}

export function loadDesktopDownloadOptions(apiBaseUrl = getDesktopApiBaseUrl()) {
  return desktopApiRequest<DesktopDownloadOptionsResponse>(
    getPublicApiBaseUrl(apiBaseUrl),
    '/desktop-updates/download-options',
    {
      method: 'GET',
    },
  )
}

export function resolveDesktopDownloadUrl(downloadUrl: string, apiBaseUrl = getDesktopApiBaseUrl()) {
  const normalized = downloadUrl.trim()
  if (/^https?:\/\//i.test(normalized)) return normalized

  const apiOrigin = getApiOrigin(apiBaseUrl)
  return new URL(normalized, `${apiOrigin}/`).toString()
}

export function loadDesktopNotifications(session: DesktopSession, apiBaseUrl = getDesktopApiBaseUrl()) {
  return desktopApiRequest<DesktopBroadcastNotificationsResponse>(
    apiBaseUrl,
    '/notifications',
    {
      method: 'GET',
      token: session.accessToken,
    },
  )
}

export function markDesktopNotificationRead(session: DesktopSession, id: string, apiBaseUrl = getDesktopApiBaseUrl()) {
  return desktopApiRequest<{ id: string; read: true }>(
    apiBaseUrl,
    '/notifications/read',
    {
      method: 'POST',
      token: session.accessToken,
      body: { id },
    },
  )
}

export function submitDesktopFeedback(
  session: DesktopSession,
  payload: { content: string; imageUrls?: string[] },
  apiBaseUrl = getDesktopApiBaseUrl(),
) {
  return desktopApiRequest<DesktopFeedbackCreateResponse>(
    apiBaseUrl,
    '/feedback',
    {
      method: 'POST',
      token: session.accessToken,
      body: {
        content: payload.content,
        imageUrls: payload.imageUrls ?? [],
      },
    },
  )
}

export function generateDesktopAiComment(
  session: DesktopSession,
  payload: DesktopAiCommentGenerateRequest,
  apiBaseUrl = getDesktopApiBaseUrl(),
) {
  return desktopApiRequest<AiCommentGenerationResult>(
    apiBaseUrl,
    '/ai-comments/generate',
    {
      method: 'POST',
      token: session.accessToken,
      body: {
        ...payload,
        deviceFingerprint: getDeviceFingerprint(),
      },
    },
  )
}

async function desktopApiRequest<T>(
  apiBaseUrl: string,
  path: string,
  options: {
    method: 'GET' | 'POST'
    token?: string
    body?: unknown
  },
) {
  let response: Response
  try {
    response = await fetch(`${normalizeApiBaseUrl(apiBaseUrl)}${path}`, {
      method: options.method,
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
  } catch (error) {
    throw new Error(formatDesktopApiError(error))
  }

  const envelope = (await response.json().catch(() => null)) as DesktopApiEnvelope<T> | null
  if (!response.ok) {
    throw new Error(formatDesktopApiError(envelope?.desc || `请求失败：HTTP ${response.status}`))
  }
  if (!envelope?.success) {
    throw new Error(formatDesktopApiError(envelope?.desc || '请求失败'))
  }
  if (typeof envelope.data === 'undefined') {
    throw new Error('接口响应缺少 data')
  }
  return envelope.data
}

function normalizeApiBaseUrl(value: string) {
  return value.trim().replace(/\/+$/, '')
}

function getPublicApiBaseUrl(apiBaseUrl: string) {
  const url = new URL(normalizeApiBaseUrl(apiBaseUrl))
  url.pathname = url.pathname.replace(/\/api\/desktop\/?$/, '/api')
  url.search = ''
  url.hash = ''
  return normalizeApiBaseUrl(url.toString())
}

function getApiOrigin(apiBaseUrl: string) {
  const url = new URL(normalizeApiBaseUrl(apiBaseUrl))
  return url.origin
}

function normalizeUserRole(role: unknown): 1 | 2 {
  return role === 1 ? 1 : DEFAULT_DESKTOP_USER_ROLE
}

function readLimitNumber(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) return Math.trunc(value)
  if (typeof value === 'string' && value.trim()) {
    const next = Number(value)
    if (Number.isFinite(next)) return Math.trunc(next)
  }
  return 0
}

const DEFAULT_DESKTOP_LIMITS = {
  maxEnabledAccounts: 0,
  maxDevices: 0,
  dailyTaskRuns: 0,
  scheduler: false,
  targetEngagement: false,
  exportCsv: false,
  aiComment: false,
}

function normalizePemEnvValue(value: string) {
  return value.trim().replace(/\\n/g, '\n')
}

function formatDesktopApiError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error)
  const normalized = message.trim()

  const translations: Record<string, string> = {
    'Failed to fetch': '无法连接服务端，请检查服务端地址或网络连接',
    'Invalid username or password': '账号或密码错误',
    'Active subscription required': '当前账号没有有效订阅',
    'Active device required': '当前设备未激活',
    'Active license required': '当前账号没有有效 License',
    'Device fingerprint is already bound to another user': '当前设备已绑定到其他账号',
    'Device not found': '未找到当前设备',
    'Device quota exceeded': '设备名额已满，请先释放旧设备后再登录',
    'Invalid desktop session': '桌面端登录状态无效，请重新登录',
    'Password verification failed': '密码校验失败，请稍后再试',
    Unauthorized: '请先登录',
    'Load failed': '请求服务端失败，请稍后重试',
  }

  if (translations[normalized]) return translations[normalized]
  if (/failed to fetch/i.test(normalized)) return translations['Failed to fetch']
  if (/invalid username or password/i.test(normalized)) return translations['Invalid username or password']
  if (/active subscription required/i.test(normalized)) return translations['Active subscription required']
  if (/active device required/i.test(normalized)) return translations['Active device required']
  if (/active license required/i.test(normalized)) return translations['Active license required']
  if (/设备名额已满|device quota exceeded/i.test(normalized)) return '设备名额已满，请先在管理后台释放旧设备后再登录'

  return normalized
}

function parsePemToBytes(pem: string, errorMessage: string) {
  const base64 = pem
    .replace(/-----BEGIN PUBLIC KEY-----/g, '')
    .replace(/-----END PUBLIC KEY-----/g, '')
    .replace(/\s/g, '')

  if (!base64) {
    throw new Error(errorMessage)
  }

  return base64ToBytes(base64, errorMessage)
}

function base64ToBytes(value: string, errorMessage: string) {
  let binary = ''
  try {
    binary = atob(value)
  } catch {
    throw new Error(errorMessage)
  }

  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return bytes
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map((item) => stableStringify(item)).join(',')}]`

  const record = value as Record<string, unknown>
  return `{${Object.keys(record)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`)
    .join(',')}}`
}

function formatLicenseVerificationError(error: unknown) {
  if (error instanceof Error) {
    if (error.message.startsWith('License ') || error.message.startsWith('桌面端')) return error.message
  }
  return 'License 校验失败，请检查授权配置'
}
