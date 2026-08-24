# 多平台平台上下文改造 Design

## 总体方案

采用“全局平台上下文 + 稳定功能导航 + 平台 adapter”的架构。

用户界面：

```text
顶部：平台选择器 + 系统状态
左侧：固定功能菜单
内容区：根据页面作用域和平台上下文渲染
```

工程内部：

```text
共享功能页不按平台拆分
平台特有能力按 adapter 和平台目录拆分
所有数据读写带 platform 维度
```

## 导航结构

顶部平台选择器：

```text
TikTok | Instagram | WhatsApp | 抖音 | 更多平台
```

左侧菜单：

```text
首页
账号管理
浏览器环境
养号任务
目标号互动
调度计划
评论素材
执行记录
Session 日志
统计报表
Gmail 初始化
诊断工具
系统设置
```

【平台管理】不再作为左侧菜单出现，平台设置入口位于顶部“更多平台”。

## 页面作用域模型

```ts
type PageScope = 'current_platform' | 'all_platforms' | 'system'
```

页面分类：

| 页面 | Scope | 默认平台行为 |
| --- | --- | --- |
| 首页 | all_platforms | 默认全部平台，页面内可筛选 |
| 账号管理 | current_platform | 跟随顶部当前平台 |
| 浏览器环境 | current_platform | 跟随顶部当前平台 |
| 养号任务 | current_platform | 跟随顶部当前平台 |
| 目标号互动 | current_platform | 跟随顶部当前平台 |
| 调度计划 | current_platform | 跟随顶部当前平台 |
| 评论素材 | current_platform | 跟随顶部当前平台 |
| 执行记录 | all_platforms | 默认全部平台，页面内可筛选 |
| Session 日志 | all_platforms | 默认全部平台，页面内可筛选 |
| 统计报表 | all_platforms | 默认全部平台，页面内可筛选 |
| Gmail 初始化 | current_platform | 跟随顶部当前平台，不支持则提示 |
| 诊断工具 | system | 全局诊断，内部可选平台/账号 |
| 系统设置 | system | 全局设置 |
| 平台设置 | system | 全局平台配置 |

## 平台上下文状态

前端维护一个全局平台上下文：

```ts
type Platform = 'tiktok' | 'instagram' | 'whatsapp' | 'douyin'

interface PlatformContextState {
  currentPlatform: Platform
  setCurrentPlatform(platform: Platform): void
}
```

行为：

- 当前平台持久化到 localStorage。
- 顶部平台切换不改变左侧当前菜单。
- 当前平台页面读取 `currentPlatform` 后加载对应平台数据。
- 全平台页面默认不使用 `currentPlatform` 作为过滤条件，但页面筛选器可以选择平台。

## 平台 registry

前端平台 registry：

```ts
interface PlatformDefinition {
  id: Platform
  name: string
  localeName: string
  status: 'supported' | 'reserved' | 'in_development' | 'not_supported'
  enabled: boolean
  capabilities: Record<PlatformCapability, CapabilityStatus>
  defaultTaskConfig?: unknown
  defaultTargetConfig?: unknown
}

type PlatformCapability =
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

type CapabilityStatus = 'supported' | 'reserved' | 'in_development' | 'not_supported'
```

registry 用于：

- 顶部平台选择器。
- 平台设置页。
- 当前页面是否支持的判断。
- 统一不支持状态渲染。

## 页面渲染策略

严格当前平台页面：

```text
读取 currentPlatform
查询该平台数据
检查 capability
支持则渲染功能
不支持则渲染 UnsupportedCapabilityState
```

全平台页面：

```text
默认 platformFilter = all
页面内筛选器控制 platformFilter
查询时传 platformFilter
展示汇总 + 分平台明细
```

系统页面：

```text
不读取 currentPlatform 作为默认过滤
需要平台时用内部筛选器
```

## 统一不支持状态

```ts
interface UnsupportedCapabilityStateProps {
  platform: Platform
  capability: PlatformCapability
  status: CapabilityStatus
  reason: string
  nextAction?: string
}
```

展示内容：

- 当前平台名称。
- 当前功能名称。
- 接入状态。
- 不支持原因。
- 平台设置入口。

## 前端目录结构

页面仍按功能组织：

```text
desktop/src/
  app/
    routes.tsx
    PlatformContext.tsx
  components/
    PlatformSelector.tsx
    PlatformScopeFilter.tsx
    UnsupportedCapabilityState.tsx
  pages/
    HomePage.tsx
    AccountPage.tsx
    BrowserProfilePage.tsx
    TaskPage.tsx
    TargetEngagementPage.tsx
    SchedulerPage.tsx
    CommentPoolPage.tsx
    ExecutionRecordPage.tsx
    SessionLogPage.tsx
    StatsPage.tsx
    GmailSetupPage.tsx
    DiagnosticPage.tsx
    SettingsPage.tsx
    PlatformSettingsPage.tsx
  platforms/
    registry.ts
    types.ts
    tiktok/
      definition.ts
      taskConfig.tsx
      targetConfig.tsx
      stats.ts
    instagram/
      definition.ts
      taskConfig.tsx
      targetConfig.tsx
      stats.ts
    whatsapp/
      definition.ts
      taskConfig.tsx
      stats.ts
    douyin/
      definition.ts
      taskConfig.tsx
      targetConfig.tsx
      stats.ts
```

## 后端目录结构

共享执行层和平台执行器分离：

```text
src/
  core/
    config.py
    runner.py
    scheduler.py
    browser.py
    logging.py
    stats.py
  platforms/
    tiktok/
      runner.py
      fyp.py
      target_engage.py
      stats.py
    instagram/
      runner.py
      warmup.py
      target_engage.py
      stats.py
    whatsapp/
      runner.py
      keepalive.py
      stats.py
    douyin/
      runner.py
      feed.py
      target_engage.py
      stats.py
```

Tauri 后端仍提供统一命令：

```text
run_platform_task(platform, taskType, accountIds, options)
query_records(filter)
query_stats(filter)
save_platform_config(platform, section, payload)
```

## 配置结构建议

目标配置结构：

```yaml
platforms:
  tiktok:
    enabled: true
    status: supported
    warmup:
      fyp_browse_minutes: [2, 5]
      like_probability: 0.35
      follows_per_session: [1, 1]
      comment:
        enabled: true
        comments_per_session: [1, 2]
        min_video_comments: 1000
        probability: 0.25
    target_engagement:
      enabled: true
      handles: []
      participants: []
      first_run_latest_n: 1
      max_videos_per_run: 3
      like_probability: 0.9
      comment_probability: 0.5
      comments_file: comments_brand.txt
    comments:
      general_file: comments.txt
      target_file: comments_brand.txt
    scheduler:
      fires_per_day: 3

  instagram:
    enabled: false
    status: reserved

accounts:
  - id: tiktok_101
    platform: tiktok
    enabled: true
    ip_group: 101
    active_hours: [[9, 12]]
    bitbrowser_profile_id: "..."
```

兼容旧结构：

- `defaults.daily_actions` 映射为 `platforms.tiktok.warmup`。
- `target_accounts` 映射为 `platforms.tiktok.target_engagement`。
- 顶层 `scheduler` 可继续作为默认值，也可迁移到 `platforms.tiktok.scheduler`。

## 数据库结构建议

新写入数据必须显式包含 platform。

建议新增或扩展字段：

```sql
action_log.platform TEXT
target_engagements.platform TEXT
target_follows.platform TEXT
session_events.platform TEXT
```

兼容策略：

- 旧记录 platform 为空时，通过 account_id 查询账号平台。
- 如果无法查询且账号 ID 以 `tiktok_` 开头，按历史兼容推导为 `tiktok`。
- 新记录不允许 platform 为空。

## 日志结构

长期建议将 `sessions.log` 从纯文本追加升级为结构化事件或旁路事件表。

最低要求：

```text
timestamp | platform | account_id | task_type | level | message
```

如果短期仍保留现有文本日志，则新增写入格式必须包含 platform，查询时支持按 platform 过滤。

## API 设计

前端 API：

```ts
loadConfig(platform?: Platform): Promise<ConfigSnapshot>
loadAccounts(filter: { platform?: Platform | 'all' }): Promise<Account[]>
saveAccounts(platform: Platform, accounts: Account[]): Promise<SaveResult>
saveWarmupSettings(platform: Platform, payload: unknown): Promise<SaveResult>
saveTargetEngagementSettings(platform: Platform, payload: unknown): Promise<SaveResult>
runPlatformTask(request: RunPlatformTaskRequest): Promise<ProcessStartResult>
queryActionLogs(filter: PlatformRecordFilter): Promise<ActionLog[]>
queryStats(filter: PlatformStatsFilter): Promise<StatsSummary>
```

执行请求：

```ts
interface RunPlatformTaskRequest {
  platform: Platform
  taskType: 'warmup' | 'target_engagement' | 'gmail_setup' | 'diagnostic'
  accountIds: string[]
  mode: 'all' | 'single' | 'selected'
  options?: Record<string, unknown>
}
```

后端校验顺序：

1. platform 合法。
2. capability 已支持。
3. 账号都属于该 platform。
4. 账号启用。
5. 账号 profile 已配置。
6. BitBrowser API 可用。
7. 当前无冲突运行进程。
8. 传递给对应平台 runner。

## 平台执行器

后端平台 runner 接口：

```python
class PlatformRunner:
    platform = "tiktok"

    def supports(self, capability: str) -> bool:
        ...

    def run_warmup(self, account, config, context):
        ...

    def run_target_engagement(self, account, config, context):
        ...

    def collect_stats(self, db, filter):
        ...
```

统一 runner 负责：

- 加载配置。
- 解析账号。
- 加锁。
- 打开/关闭浏览器 profile。
- 记录通用日志。
- 调用平台 runner。
- 写入通用执行记录。

平台 runner 负责：

- 页面导航。
- 平台动作选择器。
- 平台任务参数。
- 平台目标互动逻辑。
- 平台统计补充口径。

## 全平台页面筛选 UI

推荐筛选器：

```text
平台：[全部平台] [TikTok] [Instagram] [WhatsApp] [抖音]
时间：今天 / 最近 7 天 / 最近 30 天 / 自定义
账号：按平台联动
任务类型：养号 / 目标互动 / 调度 / Gmail / 诊断
状态：成功 / 失败 / 跳过 / 运行中
```

筛选器行为：

- 默认平台为全部平台。
- 选择平台后账号选项联动。
- 清空平台后恢复全部平台汇总。
- 筛选状态反映在 URL query 或页面状态中，方便刷新保留。

## 迁移策略

分阶段迁移：

1. 增加 platform 字段兼容读取，不改变旧配置写法。
2. 新写入账号、日志和记录必须带 platform。
3. 引入 `platforms.tiktok` 配置，同时兼容旧 `defaults` 和 `target_accounts`。
4. 提供配置迁移命令或保存时自动规范化。
5. 将 TikTok Python 逻辑移动到平台 runner，保留旧 `src/main.py` 作为兼容入口。

## 风险与约束

主要风险：

- 全平台页面默认全部平台，可能与顶部当前平台心智冲突。
- 旧数据缺 platform，统计需要兼容推导。
- WhatsApp 的“养号”和“目标号互动”概念不同，需要能力不支持状态或替代任务模型。
- 如果不拆平台 adapter，页面和执行层会快速积累平台条件判断。

规避：

- 在页面标题和筛选器上明确“全部平台”或当前平台。
- 后端统一能力校验。
- 平台 registry 作为唯一能力来源。
- 新平台必须通过 adapter 接入。
