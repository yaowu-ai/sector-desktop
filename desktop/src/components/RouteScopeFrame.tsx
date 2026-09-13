import { type ReactNode } from 'react'

import { usePlatformContext } from '../app/PlatformContext'
import {
  PageScopeProvider,
  type PageScope,
} from '../app/pageScope'
import {
  getCapabilityStatus,
  getUnsupportedCapabilityReason,
  supportsCapability,
} from '../platforms'
import type { PlatformCapability } from '../platforms'
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
  const contextValue = {
    routeKey,
    routeLabel,
    scope,
    capability,
  }

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
