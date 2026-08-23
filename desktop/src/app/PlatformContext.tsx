import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { getPlatformDefinition, PLATFORMS } from '../platforms/registry'
import type { Platform, PlatformDefinition } from '../platforms/types'

export const PLATFORM_STORAGE_KEY = 'account-matrix-current-platform'
export const DEFAULT_PLATFORM: Platform = 'tiktok'

export function resolveInitialPlatform(saved: string | null): Platform {
  return saved && PLATFORMS.some((platform) => platform.id === saved) ? (saved as Platform) : DEFAULT_PLATFORM
}

interface PlatformContextState {
  currentPlatform: Platform
  currentPlatformDefinition: PlatformDefinition
  setCurrentPlatform(platform: Platform): void
}

const PlatformContext = createContext<PlatformContextState | null>(null)

export function PlatformProvider({ children }: { children: ReactNode }) {
  const [currentPlatform, setCurrentPlatformState] = useState<Platform>(() => {
    const saved = window.localStorage.getItem(PLATFORM_STORAGE_KEY)
    return resolveInitialPlatform(saved)
  })

  useEffect(() => {
    window.localStorage.setItem(PLATFORM_STORAGE_KEY, currentPlatform)
  }, [currentPlatform])

  const setCurrentPlatform = useCallback((platform: Platform) => {
    setCurrentPlatformState(platform)
  }, [])

  const value = useMemo(
    () => ({
      currentPlatform,
      currentPlatformDefinition: getPlatformDefinition(currentPlatform),
      setCurrentPlatform,
    }),
    [currentPlatform, setCurrentPlatform],
  )

  return <PlatformContext.Provider value={value}>{children}</PlatformContext.Provider>
}

export function usePlatformContext() {
  const context = useContext(PlatformContext)
  if (!context) {
    throw new Error('usePlatformContext must be used within PlatformProvider')
  }
  return context
}
