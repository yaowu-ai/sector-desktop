import { createContext, useContext } from 'react'
import type { ApiStatus } from '../services/types'

export interface BrowserStatuses {
  bitbrowser: ApiStatus | null
  ixbrowser: ApiStatus | null
  usesBitbrowser: boolean
  usesIxbrowser: boolean
  refresh: () => Promise<void>
}

export const BrowserStatusContext = createContext<BrowserStatuses | null>(null)

export function useBrowserStatuses() {
  const value = useContext(BrowserStatusContext)
  if (!value) throw new Error('Browser statuses require AppShell')
  return value
}
