import { createReservedPlatformModule } from '../common/reservedModule'
import { RESERVED_CAPABILITIES } from '../common/capabilities'
import type { PlatformDefinition } from '../types'
import { douyinDefaultConfig } from './config'

export const douyinPlatform: PlatformDefinition = {
  id: 'douyin',
  name: 'Douyin',
  localeName: '抖音',
  status: 'reserved',
  enabled: true,
  automaticExecutionSupported: false,
  accountPrefix: 'douyin_',
  summary: '已预留账号、浏览器环境、任务、调度和统计入口；现有 src/douyin-fetcher 暂不接入 PC 端自动执行。',
  capabilities: RESERVED_CAPABILITIES,
  defaultConfig: douyinDefaultConfig,
}

export const douyinModule = createReservedPlatformModule(
  douyinPlatform,
  '抖音尚未接入平台执行器、页面业务实现和服务适配器。',
)

export { douyinPageEntry } from './pages'
export { douyinServiceEntry } from './services'
export { douyinDefaultConfig } from './config'
