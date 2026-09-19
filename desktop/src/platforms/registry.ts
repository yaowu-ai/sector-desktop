import {
  EMPTY_PLATFORM_CAPABILITIES,
  PLATFORM_CAPABILITIES,
} from './common/capabilities'
import { douyinModule } from './douyin'
import { instagramModule } from './instagram'
import { tiktokModule } from './tiktok'
import { whatsappModule } from './whatsapp'
import type {
  CapabilityStatus,
  Platform,
  PlatformCapability,
  PlatformModuleManifest,
} from './types'

export {
  EMPTY_PLATFORM_CAPABILITIES,
  PLATFORM_CAPABILITIES,
} from './common/capabilities'

export const PLATFORM_MODULES: Record<Platform, PlatformModuleManifest> = {
  tiktok: tiktokModule,
  instagram: instagramModule,
  whatsapp: whatsappModule,
  douyin: douyinModule,
}

export const PLATFORM_REGISTRY = {
  tiktok: PLATFORM_MODULES.tiktok.definition,
  instagram: PLATFORM_MODULES.instagram.definition,
  whatsapp: PLATFORM_MODULES.whatsapp.definition,
  douyin: PLATFORM_MODULES.douyin.definition,
} as const

export const PLATFORMS = [
  PLATFORM_REGISTRY.tiktok,
  PLATFORM_REGISTRY.instagram,
  PLATFORM_REGISTRY.whatsapp,
  PLATFORM_REGISTRY.douyin,
]

export const PLATFORM_IDS: Platform[] = PLATFORMS.map((platform) => platform.id)

export function isPlatform(value: string): value is Platform {
  return value in PLATFORM_REGISTRY
}

export function getPlatformDefinition(platform: Platform) {
  return PLATFORM_REGISTRY[platform]
}

export function getPlatformModule(platform: Platform) {
  return PLATFORM_MODULES[platform]
}

export function getPlatformLabel(platform: Platform) {
  return getPlatformDefinition(platform).localeName
}

export function getCapabilityStatus(platform: Platform, capability: PlatformCapability) {
  return getPlatformDefinition(platform).capabilities[capability]
}

export function getCapabilityStatusLabel(status: CapabilityStatus) {
  if (status === 'supported') return '已支持'
  if (status === 'reserved') return '预留'
  if (status === 'in_development') return '开发中'
  return '未支持'
}

export function getUnsupportedCapabilityReason(platform: Platform, capability: PlatformCapability) {
  const definition = getPlatformDefinition(platform)
  const capabilityDefinition = PLATFORM_CAPABILITIES.find((item) => item.key === capability)
  const status = getCapabilityStatus(platform, capability)
  if (!definition.enabled) {
    return `${definition.localeName} 当前未启用。${definition.summary}`
  }
  return `${definition.localeName} / ${capabilityDefinition?.label ?? capability} 当前状态为${getCapabilityStatusLabel(
    status,
  )}。${definition.summary}`
}

export function supportsCapability(platform: Platform, capability: PlatformCapability) {
  const definition = getPlatformDefinition(platform)
  return definition.enabled && definition.capabilities[capability] === 'supported'
}

export function isExecutablePlatform(platform: Platform) {
  const definition = getPlatformDefinition(platform)
  return definition.enabled && definition.status === 'supported' && definition.automaticExecutionSupported
}

export function getAutomaticExecutionDisabledReason(platform: Platform, capability: PlatformCapability) {
  const definition = getPlatformDefinition(platform)
  if (isExecutablePlatform(platform)) return undefined
  if (!supportsCapability(platform, capability)) {
    return getUnsupportedCapabilityReason(platform, capability)
  }
  const capabilityDefinition = PLATFORM_CAPABILITIES.find((item) => item.key === capability)
  return `${definition.localeName} / ${capabilityDefinition?.label ?? capability} 已预留配置入口，但 V1 尚未接入自动执行。${definition.summary}`
}
