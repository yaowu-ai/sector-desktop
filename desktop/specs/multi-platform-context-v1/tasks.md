# 多平台平台上下文改造 Tasks

## M0 决策确认

- [x] 确认顶部全局平台选择器为多平台主入口。
- [x] 确认左侧不做平台二级菜单。
- [x] 确认左侧移除【平台管理】。
- [x] 确认保留【养号任务】和【目标号互动】两个独立菜单。
- [x] 确认页面作用域分类：当前平台、全平台、系统级。
- [x] 确认全平台页面默认展示全部平台，并提供平台筛选。

## M1 平台模型与 registry

- [x] 扩展 Platform 状态：supported、reserved、in_development、not_supported。
- [x] 定义 PlatformCapability。
- [x] 定义 CapabilityStatus。
- [x] 建立前端 `platforms/registry.ts`。
- [x] 将 TikTok、Instagram、WhatsApp、抖音定义迁移到 registry。
- [x] 为每个平台定义能力矩阵。
- [x] 为平台定义 enabled、status、summary、default config。
- [x] 增加 helper：`getPlatformDefinition(platform)`。
- [x] 增加 helper：`supportsCapability(platform, capability)`。

## M2 顶部平台选择器

- [x] 新建 `PlatformContext`。
- [x] 在 AppShell 顶部加入平台选择器。
- [x] 当前平台保存到 localStorage。
- [x] 当前平台切换时不改变左侧当前菜单。
- [x] 平台选择器显示平台状态。
- [x] “更多平台”打开平台设置入口。
- [x] 平台状态为未启用时提供清晰提示。

## M3 左侧导航调整

- [x] 从 routes 中移除【平台管理】。
- [x] 新增或保留平台设置入口，但不放在左侧主导航。
- [x] 确保左侧菜单不出现平台二级菜单。
- [x] 确保 hash 或 URL 对旧 `platforms` 路由有兼容跳转或提示。
- [x] 检查顶部平台切换后左侧选中状态稳定。

## M4 页面作用域基础设施

- [x] 为每个 route 增加 `scope` 元数据。
- [x] 实现当前平台页面的 wrapper。
- [x] 实现全平台页面的 `PlatformScopeFilter`。
- [x] 实现系统页面不读取 currentPlatform 作为默认过滤。
- [x] 实现统一页面标题格式，例如 `TikTok / 养号任务`。
- [x] 实现 `UnsupportedCapabilityState`。

## M5 当前平台页面改造

- [x] 账号管理按 currentPlatform 加载账号。
- [x] 账号管理新增账号时自动填入 currentPlatform。
- [x] 浏览器环境按 currentPlatform 展示 profile 绑定。
- [x] 养号任务按 currentPlatform 读取任务配置。
- [x] 养号任务基于平台能力显示支持或不支持。
- [x] 目标号互动按 currentPlatform 读取配置、水位线和统计。
- [x] 调度计划按 currentPlatform 读取调度配置和排期。
- [x] 评论素材按 currentPlatform 读取评论池。
- [x] Gmail 初始化按 currentPlatform 判断支持状态。

## M6 全平台视角页面改造

- [x] 首页默认展示全部平台总览。
- [x] 首页增加平台筛选和时间范围筛选。
- [x] 执行记录默认展示全部平台。
- [x] 执行记录增加平台、账号、任务类型、状态、时间范围筛选。
- [x] Session 日志默认展示全部平台。
- [x] Session 日志增加平台、账号、任务类型、关键词、时间范围筛选。
- [x] 统计报表默认展示全部平台。
- [x] 统计报表增加平台、账号、任务类型、时间范围筛选。
- [x] 账号筛选选项根据平台筛选联动。

## M7 系统级页面改造

- [x] 诊断工具保持系统级入口。
- [x] 诊断工具内部按需选择平台和账号。
- [x] 系统设置保持全局。
- [x] 平台设置页展示平台列表、启用状态、接入状态、能力矩阵。
- [x] 平台设置页提供平台默认配置入口。
- [x] 平台设置页提供 API / 环境说明。

## M8 配置结构改造

- [x] 设计 `platforms.<platform>` 配置结构。
- [x] 将 TikTok `defaults.daily_actions` 映射到 `platforms.tiktok.warmup`。
- [x] 将 TikTok `target_accounts` 映射到 `platforms.tiktok.target_engagement`。
- [x] 将评论池配置映射到平台配置。
- [x] 将调度配置映射到平台配置。
- [x] 读取配置时兼容旧结构。
- [x] 保存配置时明确写入 platform 维度。
- [x] 老账号缺少 platform 时默认补 `tiktok`。
- [x] 配置校验必须校验平台字段合法。

## M9 数据库和日志 platform 维度

- [x] 为新写入 action_log 增加 platform。
- [x] 为 target_engagements 增加 platform。
- [x] 为 target_follows 增加 platform。
- [x] 旧记录 platform 为空时实现兼容推导。
- [x] 新记录禁止 platform 为空。
- [x] sessions.log 新格式包含 platform。
- [x] 日志查询支持平台筛选。
- [x] 统计查询支持平台筛选和全部平台汇总。

## M10 后端 API 改造

- [x] `load_accounts` 支持 platform filter。
- [x] `save_accounts` 按 platform 保存或校验。
- [x] `save_warmup_settings` 增加 platform 参数。
- [x] `save_target_engagement_settings` 增加 platform 参数。
- [x] `query_action_logs` 增加 platform filter。
- [x] `query_target_watermarks` 增加 platform filter。
- [x] `query_stats` 增加 platform filter。
- [x] `run_platform_task` 接收 platform、taskType、accountIds、mode。
- [x] 后端统一校验 platform + capability。
- [x] 后端校验 accountIds 都属于 request.platform。

## M11 Python 平台 adapter

- [x] 新建后端 Python `src/platforms/` 目录。
- [x] 新建共享 `src/core/` 目录。
- [x] 抽离 TikTok runner。
- [x] 抽离 TikTok FYP 行为。
- [x] 抽离 TikTok 目标互动行为。
- [x] 保留旧 `src/main.py` 兼容入口。
- [x] 新增统一 runner，根据 account.platform 分发。
- [x] Instagram runner 先注册为预留，不执行。
- [x] WhatsApp runner 先注册为预留，不执行。
- [x] 抖音 runner 先注册为预留，不执行。

## M12 能力校验和不支持状态

- [x] 前端进入页面时检查 capability。
- [x] 不支持时展示统一 `UnsupportedCapabilityState`。
- [x] 启动按钮禁用时必须有原因。
- [x] 后端拒绝未支持平台执行请求。
- [x] 后端错误包含 platform、capability、accountId。
- [x] 直接 invoke 未支持平台时返回明确错误。

## M13 迁移工具与兼容

- [x] 增加配置迁移 preview。
- [x] 增加配置迁移 apply。
- [x] 老账号默认补 `platform: tiktok`。
- [x] 旧 FYP 配置迁移到 TikTok 平台配置。
- [x] 旧目标号配置迁移到 TikTok 平台配置。
- [x] 旧评论池归属 TikTok。
- [x] 旧统计记录按兼容规则推导 TikTok。
- [x] 迁移前自动备份 accounts.yaml 和 actions.db。

## M14 测试

- [x] 单测平台 registry。
- [x] 单测 capability 判断。
- [x] 单测页面 scope 判断。
- [x] 单测 currentPlatform 持久化。
- [x] 单测全平台筛选默认值。
- [x] 单测配置旧结构兼容读取。
- [x] 单测配置迁移。
- [x] 单测后端 platform + capability 校验。
- [x] 单测账号 platform 校验。
- [x] 单测 SQLite platform filter。
- [x] 集成测试 TikTok 旧配置仍可运行。
- [x] 集成测试 Instagram 预留状态不能启动。
- [x] 集成测试执行记录全平台视角和平台筛选。
- [x] 集成测试统计报表全平台视角和平台筛选。
- [x] 集成测试左侧导航不因平台切换变化。

## M15 验收

- [x] 顶部平台选择器可切换平台。
- [x] 左侧不再显示【平台管理】。
- [x] 左侧不出现平台二级菜单。
- [x] 账号管理严格跟随当前平台。
- [x] 养号任务严格跟随当前平台。
- [x] 目标号互动严格跟随当前平台。
- [x] 评论素材严格跟随当前平台。
- [x] 首页默认全平台并可筛平台。
- [x] 执行记录默认全平台并可筛平台。
- [x] Session 日志默认全平台并可筛平台。
- [x] 统计报表默认全平台并可筛平台。
- [x] 系统设置不受平台切换影响。
- [x] 平台设置可从顶部更多平台进入。
- [x] 未支持平台无法通过前端或后端启动任务。
- [x] TikTok 历史配置和历史数据兼容。
