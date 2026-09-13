import type { PlatformDefinition, PlatformModuleManifest } from '../types'
import { SUPPORTED_CAPABILITIES } from '../common/capabilities'

const defaultConfig: PlatformDefinition['defaultConfig'] = {
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

export const tiktokPlatform: PlatformDefinition = {
  id: 'tiktok',
  name: 'TikTok',
  localeName: 'TikTok',
  status: 'supported',
  enabled: true,
  automaticExecutionSupported: true,
  accountPrefix: 'tiktok_',
  summary: 'V1 已接入现有 Python 脚本，允许启动真实自动化任务。',
  capabilities: SUPPORTED_CAPABILITIES,
  defaultConfig,
  defaultTaskConfig: defaultConfig.warmup,
  defaultTargetConfig: defaultConfig.targetEngagement,
}

export const tiktokModule: PlatformModuleManifest = {
  definition: tiktokPlatform,
  implementation: 'executable',
  pageEntry: './pages',
  serviceEntry: './services',
}
