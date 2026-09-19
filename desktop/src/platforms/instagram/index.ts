import { createReservedPlatformModule } from '../common/reservedModule'
import { INSTAGRAM_CAPABILITIES } from '../common/capabilities'
import type { PlatformDefinition } from '../types'
import { instagramDefaultConfig } from './config'

export const instagramPlatform: PlatformDefinition = {
  id: 'instagram',
  name: 'Instagram',
  localeName: 'Instagram',
  status: 'reserved',
  enabled: true,
  automaticExecutionSupported: false,
  accountPrefix: 'instagram_',
  summary: 'Instagram 账号和界面入口已预留，V1 不提供真实自动执行。',
  capabilities: INSTAGRAM_CAPABILITIES,
  defaultConfig: instagramDefaultConfig,
  defaultTaskConfig: instagramDefaultConfig.instagramWarmup,
}

export const instagramModule = createReservedPlatformModule(
  instagramPlatform,
  'Instagram 尚未接入平台执行器、页面业务实现和服务适配器。',
)

export { instagramDefaultConfig } from './config'
export { instagramPageEntry } from './pages'
export { instagramServiceEntry } from './services'
