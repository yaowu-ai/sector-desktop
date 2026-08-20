import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  BadgeCheck,
  BarChart3,
  CalendarClock,
  Chrome,
  ClipboardList,
  CreditCard,
  FileText,
  Gauge,
  Headphones,
  Home,
  Info,
  Mail,
  MessageSquareText,
  Bell,
  Settings,
  ShieldCheck,
  Target,
  UserCog,
  UserRound,
} from 'lucide-react'

import { AccountPage } from '../pages/AccountPage'
import { AboutPage } from '../pages/AboutPage'
import { BrowserProfilePage } from '../pages/BrowserProfilePage'
import { CommentPoolPage } from '../pages/CommentPoolPage'
import { ContactSupportPage } from '../pages/ContactSupportPage'
import { DiagnosticPage } from '../pages/DiagnosticPage'
import { ExecutionRecordPage } from '../pages/ExecutionRecordPage'
import { GmailSetupPage } from '../pages/GmailSetupPage'
import { HomePage } from '../pages/HomePage'
import { LicenseDevicePage } from '../pages/LicenseDevicePage'
import { NotificationsPage } from '../pages/NotificationsPage'
import { PlatformPage } from '../pages/PlatformPage'
import { PlanCenterPage } from '../pages/PlanCenterPage'
import { ProfilePage } from '../pages/ProfilePage'
import { SchedulerPage } from '../pages/SchedulerPage'
import { SessionLogPage } from '../pages/SessionLogPage'
import { SettingsPage } from '../pages/SettingsPage'
import { StatsPage } from '../pages/StatsPage'
import { TargetEngagementPage } from '../pages/TargetEngagementPage'
import { TaskPage } from '../pages/TaskPage'
import type { PageScope } from './pageScope'
import type { PlatformCapability } from '../platforms/types'

export interface AppMenuGroup {
  key: string
  label: string
  icon: LucideIcon
}

export interface AppRoute {
  key: string
  label: string
  icon: LucideIcon
  element: JSX.Element
  scope: PageScope
  capability?: PlatformCapability
  menuGroup?: AppMenuGroup
}

export const personalCenterMenuGroup: AppMenuGroup = {
  key: 'personal-center',
  label: '个人中心',
  icon: UserRound,
}

export const platformSettingsRoute: AppRoute = {
  key: 'platforms',
  label: '平台设置',
  icon: ShieldCheck,
  element: <PlatformPage />,
  scope: 'system',
}

export const routes: AppRoute[] = [
  { key: 'home', label: '首页', icon: Home, element: <HomePage />, scope: 'all_platforms' },
  {
    key: 'accounts',
    label: '账号管理',
    icon: UserCog,
    element: <AccountPage />,
    scope: 'current_platform',
    capability: 'accountManagement',
  },
  {
    key: 'browser',
    label: '浏览器环境',
    icon: Chrome,
    element: <BrowserProfilePage />,
    scope: 'current_platform',
    capability: 'browserProfile',
  },
  {
    key: 'tasks',
    label: '养号任务',
    icon: Activity,
    element: <TaskPage />,
    scope: 'current_platform',
    capability: 'warmupTask',
  },
  {
    key: 'target-engagement',
    label: '目标号互动',
    icon: Target,
    element: <TargetEngagementPage />,
    scope: 'current_platform',
    capability: 'targetEngagement',
  },
  {
    key: 'scheduler',
    label: '调度计划',
    icon: CalendarClock,
    element: <SchedulerPage />,
    scope: 'current_platform',
    capability: 'scheduler',
  },
  {
    key: 'comments',
    label: '评论素材',
    icon: MessageSquareText,
    element: <CommentPoolPage />,
    scope: 'current_platform',
    capability: 'comments',
  },
  {
    key: 'records',
    label: '执行记录',
    icon: ClipboardList,
    element: <ExecutionRecordPage />,
    scope: 'all_platforms',
    capability: 'records',
  },
  {
    key: 'sessions',
    label: 'Session 日志',
    icon: FileText,
    element: <SessionLogPage />,
    scope: 'all_platforms',
    capability: 'records',
  },
  {
    key: 'stats',
    label: '统计报表',
    icon: BarChart3,
    element: <StatsPage />,
    scope: 'all_platforms',
    capability: 'stats',
  },
  {
    key: 'gmail',
    label: 'Gmail 初始化',
    icon: Mail,
    element: <GmailSetupPage />,
    scope: 'current_platform',
    capability: 'gmailSetup',
  },
  {
    key: 'profile',
    label: '账号信息',
    icon: UserRound,
    element: <ProfilePage />,
    scope: 'system',
    menuGroup: personalCenterMenuGroup,
  },
  {
    key: 'plans',
    label: '套餐中心',
    icon: CreditCard,
    element: <PlanCenterPage />,
    scope: 'system',
    menuGroup: personalCenterMenuGroup,
  },
  {
    key: 'license-devices',
    label: '授权与设备',
    icon: BadgeCheck,
    element: <LicenseDevicePage />,
    scope: 'system',
    menuGroup: personalCenterMenuGroup,
  },
  {
    key: 'contact',
    label: '联系客服',
    icon: Headphones,
    element: <ContactSupportPage />,
    scope: 'system',
    menuGroup: personalCenterMenuGroup,
  },
  {
    key: 'notifications',
    label: '消息通知',
    icon: Bell,
    element: <NotificationsPage />,
    scope: 'system',
    menuGroup: personalCenterMenuGroup,
  },
  { key: 'about', label: '关于软件', icon: Info, element: <AboutPage />, scope: 'system' },
  { key: 'diagnostic', label: '诊断工具', icon: Gauge, element: <DiagnosticPage />, scope: 'system' },
  { key: 'settings', label: '系统设置', icon: Settings, element: <SettingsPage />, scope: 'system' },
]

export const appRoutes: AppRoute[] = [platformSettingsRoute, ...routes]
