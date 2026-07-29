export {
  EMPTY_PLATFORM_CAPABILITIES,
  PLATFORM_CAPABILITIES,
  PLATFORM_IDS,
  PLATFORM_REGISTRY,
  PLATFORMS,
  getAutomaticExecutionDisabledReason,
  getCapabilityStatus,
  getCapabilityStatusLabel,
  getPlatformDefinition,
  getPlatformLabel,
  getUnsupportedCapabilityReason,
  isExecutablePlatform,
  isPlatform,
  supportsCapability,
} from '../platforms/registry'
export type {
  CapabilityStatus,
  PlatformCapability,
  PlatformCapabilityDefinition,
  PlatformDefaultConfig,
  PlatformDefinition,
  PlatformStatus,
} from '../platforms/types'
