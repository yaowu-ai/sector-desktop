import { createReservedPlatformModule } from '../common/reservedModule'
import { RESERVED_CAPABILITIES } from '../common/capabilities'
import type { PlatformDefinition } from '../types'
import { whatsappDefaultConfig } from './config'

export const whatsappPlatform: PlatformDefinition = {
  id: 'whatsapp',
  name: 'WhatsApp',
  localeName: 'WhatsApp',
  status: 'reserved',
  enabled: true,
  automaticExecutionSupported: false,
  accountPrefix: 'whatsapp_',
  summary: '已预留账号、浏览器环境、任务、调度和统计入口，V1 不启动 WhatsApp 自动执行。',
  capabilities: {
    ...RESERVED_CAPABILITIES,
    targetEngagement: 'not_supported',
    gmailSetup: 'not_supported',
  },
  defaultConfig: whatsappDefaultConfig,
}

export const whatsappModule = createReservedPlatformModule(
  whatsappPlatform,
  'WhatsApp 尚未接入平台执行器、页面业务实现和服务适配器。',
)

export { whatsappPageEntry } from './pages'
export { whatsappServiceEntry } from './services'
export { whatsappDefaultConfig } from './config'
