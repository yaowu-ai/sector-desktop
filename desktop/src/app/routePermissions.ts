import type { AppRoute } from './routes'
import type { PlatformDefinition } from '../platforms/types'

export const DESKTOP_USER_ROLES = {
  technician: 1,
  customer: 2,
} as const

export type DesktopUserRole = (typeof DESKTOP_USER_ROLES)[keyof typeof DESKTOP_USER_ROLES]

const CUSTOMER_ROUTE_KEYS = new Set([
  'home',
  'profile',
  'plans',
  'license-devices',
  'contact',
  'notifications',
  'about',
  'accounts',
  'browser',
  'tasks',
  'target-engagement',
  'scheduler',
  'comments',
  'records',
  'stats',
  'gmail',
])

export function normalizeDesktopUserRole(role: unknown): DesktopUserRole {
  return role === DESKTOP_USER_ROLES.technician ? DESKTOP_USER_ROLES.technician : DESKTOP_USER_ROLES.customer
}

export function canAccessRoute(routeKey: string, role: DesktopUserRole) {
  if (role === DESKTOP_USER_ROLES.technician) return true
  return CUSTOMER_ROUTE_KEYS.has(routeKey)
}

export function filterRoutesByRole<T extends Pick<AppRoute, 'key'>>(routes: T[], role: DesktopUserRole) {
  return routes.filter((route) => canAccessRoute(route.key, role))
}

export function canAccessPlatform(platform: Pick<PlatformDefinition, 'status'>, role: DesktopUserRole) {
  if (role === DESKTOP_USER_ROLES.technician) return true
  return platform.status === 'supported'
}

export function filterPlatformsByRole<T extends Pick<PlatformDefinition, 'status'>>(platforms: T[], role: DesktopUserRole) {
  return platforms.filter((platform) => canAccessPlatform(platform, role))
}
