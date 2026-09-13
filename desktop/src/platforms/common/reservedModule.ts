import type {
  PlatformDefinition,
  PlatformModuleManifest,
  ReservedPlatformEntry,
} from '../types'

export function createReservedPlatformModule(
  definition: PlatformDefinition,
  reservationReason: string,
): PlatformModuleManifest {
  return {
    definition,
    implementation: 'reserved',
    pageEntry: './pages',
    serviceEntry: './services',
    reservationReason,
  }
}

export function createReservedPlatformEntry(
  platformLabel: string,
  kind: '页面' | '服务',
): ReservedPlatformEntry {
  return {
    implemented: false,
    reason: `${platformLabel}${kind}尚未接入平台模块，当前仅保留独立入口。`,
  }
}
