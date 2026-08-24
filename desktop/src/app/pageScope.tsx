import { createContext, useContext, type ReactNode } from 'react'

import type { Platform, PlatformCapability } from '../platforms/types'

export type PageScope = 'current_platform' | 'all_platforms' | 'system'
export type PlatformFilterValue = Platform | 'all'

export const DEFAULT_PLATFORM_FILTER: PlatformFilterValue = 'all'

export function resolveRoutePlatformFilter(
  scope: PageScope,
  currentPlatform: Platform,
  platformFilter: PlatformFilterValue,
): PlatformFilterValue {
  return scope === 'current_platform' ? currentPlatform : platformFilter
}

export interface PageScopeContextValue {
  routeKey: string
  routeLabel: string
  scope: PageScope
  capability?: PlatformCapability
  platformFilter: PlatformFilterValue
  setPlatformFilter(value: PlatformFilterValue): void
}

const PageScopeContext = createContext<PageScopeContextValue | null>(null)

export function PageScopeProvider({
  children,
  value,
}: {
  children: ReactNode
  value: PageScopeContextValue
}) {
  return <PageScopeContext.Provider value={value}>{children}</PageScopeContext.Provider>
}

export function usePageScopeContext() {
  const context = useContext(PageScopeContext)
  if (!context) {
    throw new Error('usePageScopeContext must be used within PageScopeProvider')
  }
  return context
}

export function useOptionalPageScopeContext() {
  return useContext(PageScopeContext)
}
