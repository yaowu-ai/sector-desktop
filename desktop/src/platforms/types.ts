export type Platform = 'tiktok' | 'instagram' | 'whatsapp' | 'douyin'

export type PlatformStatus = 'supported' | 'reserved' | 'in_development' | 'not_supported'

export type PlatformCapability =
  | 'accountManagement'
  | 'browserProfile'
  | 'warmupTask'
  | 'targetEngagement'
  | 'scheduler'
  | 'comments'
  | 'records'
  | 'stats'
  | 'gmailSetup'
  | 'diagnostics'

export type CapabilityStatus = 'supported' | 'reserved' | 'in_development' | 'not_supported'

export interface PlatformCapabilityDefinition {
  key: PlatformCapability
  label: string
  description: string
}

export interface PlatformDefaultConfig {
  warmup?: {
    fypBrowseMinutes: [number, number]
    likeProbability: number
    followsPerSession: [number, number]
    comment: {
      enabled: boolean
      commentsPerSession: [number, number]
      minVideoComments: number
      probability: number
    }
  }
  instagramWarmup?: {
    duration: number
    likeProb: number
    saveProb: number
    commentProb: number
    activeHours: string
    sessionsPerDay: string
    restDayProb: number
    minSessionGapMinutes: number
    onePerWindow: boolean
    durationJitter: string
    maxLikesPerDay: number
    maxSavesPerDay: number
    maxFollowsPerDay: number
    maxLikesPerSession: number
    maxCommentsPerDay: number
    maxCommentsPerSession: number
    blockCooldownHours: number
    roundSkipProb: number
    requireProxy: boolean
    noLike: boolean
    noSave: boolean
    noComment: boolean
    noFollow: boolean
    noStories: boolean
    noReels: boolean
    noExplore: boolean
  }
  targetEngagement?: {
    enabled: boolean
    handles: string[]
    participants: string[]
    firstRunLatestN: number
    maxVideosPerRun: number
    likeProbability: number
    commentProbability: number
    commentsFile: string
    follow: boolean
    followProbability: number
  }
  comments?: {
    generalFile: string
    targetFile: string
  }
  scheduler?: {
    firesPerDay: number
  }
}

export interface PlatformDefinition {
  id: Platform
  name: string
  localeName: string
  status: PlatformStatus
  enabled: boolean
  automaticExecutionSupported: boolean
  accountPrefix: string
  summary: string
  capabilities: Record<PlatformCapability, CapabilityStatus>
  defaultConfig: PlatformDefaultConfig
  defaultTaskConfig?: PlatformDefaultConfig['warmup'] | PlatformDefaultConfig['instagramWarmup']
  defaultTargetConfig?: PlatformDefaultConfig['targetEngagement']
}
