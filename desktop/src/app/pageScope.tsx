import { createContext, useContext, type ReactNode } from 'react'

import type { PlatformCapability } from '../platforms'

export type PageScope = 'current_platform' | 'system'

export interface PageScopeContextValue {
  routeKey: string
  routeLabel: string
  scope: PageScope
  capability?: PlatformCapability
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
