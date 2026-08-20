import type {
  CapabilityStatus,
  Platform,
  PlatformCapability,
  PlatformCapabilityDefinition,
  PlatformDefinition,
} from './types'

const SUPPORTED_CAPABILITIES: Record<PlatformCapability, CapabilityStatus> = {
  accountManagement: 'supported',
  browserProfile: 'supported',
  warmupTask: 'supported',
  targetEngagement: 'supported',
  scheduler: 'supported',
  comments: 'supported',
  records: 'supported',
  stats: 'supported',
  gmailSetup: 'supported',
  diagnostics: 'supported',
}

const RESERVED_CAPABILITIES: Record<PlatformCapability, CapabilityStatus> = {
  accountManagement: 'supported',
  browserProfile: 'supported',
  warmupTask: 'reserved',
  targetEngagement: 'reserved',
  scheduler: 'supported',
  comments: 'supported',
  records: 'supported',
  stats: 'supported',
  gmailSetup: 'reserved',
  diagnostics: 'supported',
}

const INSTAGRAM_CAPABILITIES: Record<PlatformCapability, CapabilityStatus> = {
  ...SUPPORTED_CAPABILITIES,
  targetEngagement: 'reserved',
  gmailSetup: 'reserved',
}

const NOT_SUPPORTED_CAPABILITIES: Record<PlatformCapability, CapabilityStatus> = {
  accountManagement: 'not_supported',
  browserProfile: 'not_supported',
  warmupTask: 'not_supported',
  targetEngagement: 'not_supported',
  scheduler: 'not_supported',
  comments: 'not_supported',
  records: 'not_supported',
  stats: 'not_supported',
  gmailSetup: 'not_supported',
  diagnostics: 'not_supported',
}

const TIKTOK_DEFAULT_CONFIG: PlatformDefinition['defaultConfig'] = {
  warmup: {
    fypBrowseMinutes: [2, 5],
    likeProbability: 0.35,
    followsPerSession: [0, 1],
    comment: {
      enabled: false,
      commentsPerSession: [0, 1],
      minVideoComments: 100,
      probability: 0.2,
    },
  },
  targetEngagement: {
    enabled: false,
    handles: [],
    participants: [],
    firstRunLatestN: 1,
    maxVideosPerRun: 3,
    likeProbability: 0.9,
    commentProbability: 0.5,
    commentsFile: 'comments_brand.txt',
    follow: false,
    followProbability: 0.2,
  },
  comments: {
    generalFile: 'comments.txt',
    targetFile: 'comments_brand.txt',
  },
  scheduler: {
    firesPerDay: 3,
  },
}

const INSTAGRAM_DEFAULT_CONFIG: PlatformDefinition['defaultConfig'] = {
  instagramWarmup: {
    duration: 15,
    likeProb: 0.06,
    saveProb: 0.02,
    commentProb: 0.5,
    activeHours: '7-9,12-14,18-23',
    sessionsPerDay: '1-3',
    restDayProb: 0.15,
    minSessionGapMinutes: 90,
    onePerWindow: false,
    durationJitter: '0.5-1.5',
    maxLikesPerDay: 20,
    maxSavesPerDay: 10,
    maxFollowsPerDay: 3,
    maxLikesPerSession: 0,
    maxCommentsPerDay: 5,
    maxCommentsPerSession: 1,
    blockCooldownHours: 24,
    roundSkipProb: 0.15,
    requireProxy: true,
    noLike: false,
    noSave: false,
    noComment: false,
    noFollow: false,
    noStories: false,
    noReels: false,
    noExplore: false,
  },
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
    description: 'BitBrowser profile 绑定、打开、关闭和状态检测',
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

export const PLATFORM_REGISTRY: Record<Platform, PlatformDefinition> = {
  tiktok: {
    id: 'tiktok',
    name: 'TikTok',
    localeName: 'TikTok',
    status: 'supported',
    enabled: true,
    automaticExecutionSupported: true,
    accountPrefix: 'tiktok_',
    summary: 'V1 已接入现有 Python 脚本，允许启动真实自动化任务。',
    capabilities: SUPPORTED_CAPABILITIES,
    defaultConfig: TIKTOK_DEFAULT_CONFIG,
    defaultTaskConfig: TIKTOK_DEFAULT_CONFIG.warmup,
    defaultTargetConfig: TIKTOK_DEFAULT_CONFIG.targetEngagement,
  },
  instagram: {
    id: 'instagram',
    name: 'Instagram',
    localeName: 'Instagram',
    status: 'supported',
    enabled: true,
    automaticExecutionSupported: true,
    accountPrefix: 'instagram_',
    summary: 'Instagram 养号已接入桌面端，任务页可直接启动 Python runner。',
    capabilities: INSTAGRAM_CAPABILITIES,
    defaultConfig: INSTAGRAM_DEFAULT_CONFIG,
    defaultTaskConfig: INSTAGRAM_DEFAULT_CONFIG.instagramWarmup,
  },
  whatsapp: {
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
    defaultConfig: {},
  },
  douyin: {
    id: 'douyin',
    name: 'Douyin',
    localeName: '抖音',
    status: 'reserved',
    enabled: true,
    automaticExecutionSupported: false,
    accountPrefix: 'douyin_',
    summary: '已预留账号、浏览器环境、任务、调度和统计入口；现有 src/douyin-fetcher 暂不接入 PC 端自动执行。',
    capabilities: RESERVED_CAPABILITIES,
    defaultConfig: {},
  },
}

export const PLATFORMS: PlatformDefinition[] = [
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

export function getPlatformLabel(platform: Platform) {
  return getPlatformDefinition(platform).localeName
}

export function getCapabilityStatus(platform: Platform, capability: PlatformCapability) {
  return getPlatformDefinition(platform).capabilities[capability]
}

export function getCapabilityStatusLabel(status: CapabilityStatus) {
  if (status === 'supported') {
    return '已支持'
  }
  if (status === 'reserved') {
    return '预留'
  }
  if (status === 'in_development') {
    return '开发中'
  }
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
  if (isExecutablePlatform(platform)) {
    return undefined
  }
  if (!supportsCapability(platform, capability)) {
    return getUnsupportedCapabilityReason(platform, capability)
  }
  const capabilityDefinition = PLATFORM_CAPABILITIES.find((item) => item.key === capability)
  return `${definition.localeName} / ${capabilityDefinition?.label ?? capability} 已预留配置入口，但 V1 尚未接入自动执行。${definition.summary}`
}

export const EMPTY_PLATFORM_CAPABILITIES = NOT_SUPPORTED_CAPABILITIES
