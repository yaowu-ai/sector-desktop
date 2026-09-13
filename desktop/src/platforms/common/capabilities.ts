import type {
  CapabilityStatus,
  PlatformCapability,
  PlatformCapabilityDefinition,
} from '../types'

export const SUPPORTED_CAPABILITIES: Record<PlatformCapability, CapabilityStatus> = {
  accountManagement: 'supported',
  browserProfile: 'supported',
  warmupTask: 'supported',
  targetEngagement: 'supported',
  scheduler: 'supported',
  comments: 'supported',
  records: 'supported',
  stats: 'supported',
  profileStats: 'supported',
  gmailSetup: 'supported',
  diagnostics: 'supported',
}

export const RESERVED_CAPABILITIES: Record<PlatformCapability, CapabilityStatus> = {
  accountManagement: 'reserved',
  browserProfile: 'reserved',
  warmupTask: 'reserved',
  targetEngagement: 'reserved',
  scheduler: 'reserved',
  comments: 'reserved',
  records: 'reserved',
  stats: 'reserved',
  profileStats: 'not_supported',
  gmailSetup: 'reserved',
  diagnostics: 'reserved',
}

export const INSTAGRAM_CAPABILITIES: Record<PlatformCapability, CapabilityStatus> = {
  ...RESERVED_CAPABILITIES,
  targetEngagement: 'reserved',
  profileStats: 'not_supported',
  gmailSetup: 'reserved',
}

export const NOT_SUPPORTED_CAPABILITIES: Record<PlatformCapability, CapabilityStatus> = {
  accountManagement: 'not_supported',
  browserProfile: 'not_supported',
  warmupTask: 'not_supported',
  targetEngagement: 'not_supported',
  scheduler: 'not_supported',
  comments: 'not_supported',
  records: 'not_supported',
  stats: 'not_supported',
  profileStats: 'not_supported',
  gmailSetup: 'not_supported',
  diagnostics: 'not_supported',
}

export const PLATFORM_CAPABILITIES: PlatformCapabilityDefinition[] = [
  {
    key: 'accountManagement',
    label: '账号配置',
    description: '账号、启用状态、IP 分组、运行班次和 profile 绑定',
  },
  {
    key: 'browserProfile',
    label: '浏览器环境',
    description: 'Bit浏览器 profile 绑定、打开、关闭和状态检测',
  },
  {
    key: 'warmupTask',
    label: '养号任务',
    description: '浏览、点赞、关注和评论的自动化执行',
  },
  {
    key: 'targetEngagement',
    label: '目标号互动',
    description: '品牌目标号新视频检测、点赞、评论和可选关注',
  },
  {
    key: 'scheduler',
    label: '调度运行',
    description: '按 active_hours 和 fires_per_day 生成本机调度',
  },
  {
    key: 'comments',
    label: '评论素材',
    description: '通用评论池和品牌目标号评论池',
  },
  {
    key: 'records',
    label: '执行记录',
    description: '动作日志和目标互动明细',
  },
  {
    key: 'stats',
    label: '统计报表',
    description: '养号、目标互动和全平台汇总统计',
  },
  {
    key: 'profileStats',
    label: '成果展示',
    description: 'TikTok 养号任务结束后自动采集的账号主页和互动证据快照',
  },
  {
    key: 'gmailSetup',
    label: 'Gmail 初始化',
    description: '使用浏览器 profile 执行 Gmail 初始化流程',
  },
  {
    key: 'diagnostics',
    label: '诊断工具',
    description: '按平台和账号执行点赞、评论等诊断动作',
  },
]

export const EMPTY_PLATFORM_CAPABILITIES = NOT_SUPPORTED_CAPABILITIES
