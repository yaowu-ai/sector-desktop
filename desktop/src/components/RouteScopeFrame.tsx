import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { usePlatformContext } from '../app/PlatformContext'
import {
  DEFAULT_PLATFORM_FILTER,
  PageScopeProvider,
  resolveRoutePlatformFilter,
  type PageScope,
  type PlatformFilterValue,
} from '../app/pageScope'
import {
  getCapabilityStatus,
  getUnsupportedCapabilityReason,
  supportsCapability,
} from '../platforms/registry'
import type { PlatformCapability } from '../platforms/types'
import { UnsupportedCapabilityState } from './UnsupportedCapabilityState'

interface RouteScopeFrameProps {
  routeKey: string
  routeLabel: string
  scope: PageScope
  capability?: PlatformCapability
  children: ReactNode
}

export function RouteScopeFrame({
  routeKey,
  routeLabel,
  scope,
  capability,
  children,
}: RouteScopeFrameProps) {
  const { currentPlatform } = usePlatformContext()
  const [platformFilter, setPlatformFilter] = useState<PlatformFilterValue>(DEFAULT_PLATFORM_FILTER)

  useEffect(() => {
    setPlatformFilter(DEFAULT_PLATFORM_FILTER)
  }, [routeKey])

  const contextValue = useMemo(
    () => ({
      routeKey,
      routeLabel,
      scope,
      capability,
      platformFilter: resolveRoutePlatformFilter(scope, currentPlatform, platformFilter),
      setPlatformFilter,
    }),
    [capability, currentPlatform, platformFilter, routeKey, routeLabel, scope],
  )

  if (scope === 'current_platform' && capability) {
    const capabilityStatus = getCapabilityStatus(currentPlatform, capability)
    const supported = supportsCapability(currentPlatform, capability)

    if (!supported) {
      return (
        <PageScopeProvider value={contextValue}>
          <UnsupportedCapabilityState
            platform={currentPlatform}
            capability={capability}
            status={capabilityStatus}
            reason={getUnsupportedCapabilityReason(currentPlatform, capability)}
          />
        </PageScopeProvider>
      )
    }
  }

  return <PageScopeProvider value={contextValue}>{children}</PageScopeProvider>
}
