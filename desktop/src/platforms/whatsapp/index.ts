import { NOT_SUPPORTED_CAPABILITIES } from '../common/capabilities'
import type { PlatformDefinition, PlatformModuleManifest } from '../types'
import { whatsappDefaultConfig } from './config'

export const whatsappPlatform: PlatformDefinition = {
  id: 'whatsapp',
  name: 'WhatsApp',
  localeName: 'WhatsApp',
  status: 'supported',
  enabled: true,
  automaticExecutionSupported: false,
  integration: 'hosted_web',
  accountPrefix: 'whatsapp_',
  summary: '通过独立托管网页管理 WhatsApp 账号与养号任务，任务由原服务执行。',
  capabilities: {
    ...NOT_SUPPORTED_CAPABILITIES,
    accountManagement: 'supported',
    warmupTask: 'supported',
    comments: 'supported',
    records: 'supported',
    diagnostics: 'supported',
  },
  defaultConfig: whatsappDefaultConfig,
}

export const whatsappModule: PlatformModuleManifest = {
  definition: whatsappPlatform,
  implementation: 'embedded',
  pageEntry: './pages',
  serviceEntry: './services',
}

export { whatsappPageEntry } from './pages'
export { whatsappServiceEntry } from './services'
export { whatsappDefaultConfig } from './config'
