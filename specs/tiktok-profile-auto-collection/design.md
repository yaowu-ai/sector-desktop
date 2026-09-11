# TikTok 账号数据自动采集设计文档

## 0. 文档状态

本文记录 TikTok 账号数据自动采集能力的实现思路。当前目标是将已有独立采集脚本纳入桌面端应用的正式运行时能力，并确保 Windows 和 macOS 安装包都包含该采集能力。

本方案约束：

- 不提供手动采集入口。
- 不提供批量手动采集入口。
- 不提供重新采集按钮。
- 采集能力作为 TikTok 养号任务的一部分自动执行。
- 桌面端新增菜单只读展示自动采集结果。
- Windows 和 macOS 必须分别打包各自平台可执行的 runtime，不能复用 Windows `.exe` 到 macOS。

## 1. 背景

当前未提交代码中已经存在 TikTok 账号数据采集雏形：

- `src/profile_stats.py`
- `src/profile_activity.py`
- `src/test_profile_stats_unit.py`
- `src/test_profile_activity_unit.py`
- `src/fixtures/activity_comment_likes.html`

这些脚本当前主要具备独立采集和测试能力，可以读取：

- TikTok handle。
- Following。
- Followers。
- Likes。
- Liked 视频数量。
- Liked 分页完整性。
- Activity 中 `liked your comment` 相关通知。
- 采集时间。

但是当前它们还不是桌面端正式功能：

- 未接入 TikTok 养号任务流程。
- 未写入 SQLite 快照表。
- 未被桌面端菜单展示。
- 未纳入 Python sidecar runtime 的稳定命令和打包清单。
- macOS 安装包不会天然拥有 Windows runtime 中的能力。

## 2. 目标

完成后，TikTok 账号数据采集应成为桌面端内置能力：

```text
TikTok 养号任务开始
→ 打开账号浏览器
→ 执行已有养号动作：浏览、点赞、评论等
→ 主任务动作正常结束
→ 自动采集账号数据
→ 保存采集快照
→ 关闭浏览器
→ 桌面端“账号数据”菜单展示结果
```

目标能力：

- 每次 TikTok 养号任务完成后自动采集。
- 采集发生在浏览器关闭之前。
- 采集结果与本次任务关联。
- 采集成功、部分成功和失败都可持久化。
- 桌面端可以查看最新数据和历史记录。
- Windows 安装包包含 Windows runtime 采集能力。
- macOS 安装包包含 macOS runtime 采集能力。
- 目标电脑不需要安装 Python 或项目源码。

## 3. 非目标

本阶段不做：

- 手动采集按钮。
- 批量采集按钮。
- 重新采集按钮。
- 独立浏览器启动采集工具。
- 趋势图高级分析。
- CSV 导出。
- 单独付费授权字段。
- 把 Windows runtime 复用到 macOS。

## 4. 总体架构

```text
Desktop React
  ↓ 只读查询
Tauri/Rust commands
  ↓ SQLite 查询
SQLite profile_stats_snapshots
  ↑ 写入快照
Python sidecar runtime
  ↑ TikTok runner 调用
TikTok 养号任务
  ↓ 任务完成后
Profile collector
  ↓ CDP / Patchright
TikTok 页面
```

生产环境中采集能力必须进入 Python sidecar runtime：

```text
Windows:
  account-matrix-runtime.exe

macOS:
  account-matrix-runtime
```

两个平台都需要在各自 GitHub Actions runner 上分别构建。macOS 包不能依赖 Windows `.exe`。

## 5. 采集数据模型

采集结果的核心结构来自现有脚本输出，示例字段如下：

```json
{
  "handle": "ralphrivera448",
  "following": 0,
  "followers": 3,
  "likes": 0,
  "raw": {
    "following": "0",
    "followers": "3",
    "likes": "0"
  },
  "approximate_fields": [],
  "liked": 21,
  "liked_loaded": 21,
  "liked_complete": true,
  "liked_status": "complete",
  "activity": {
    "has_liked_your_comment": true,
    "comment_like_notifications_count": 2,
    "notifications_scanned": 5,
    "matches": [],
    "status": "loaded_list_stable",
    "scope": "loaded_notifications",
    "complete": false,
    "comment_publish_evidence": "observed"
  },
  "collected_at": "2026-09-10T07:08:30.405593+00:00"
}
```

字段语义：

- `likes` 表示主页获赞数。
- `liked` 表示账号点赞过的视频数量。
- `liked_complete` 表示 Liked 列表分页是否完整。
- `activity.complete: false` 是合理状态，因为 Activity 只能证明已加载通知范围，不能证明完整历史。
- `comment_publish_evidence: observed` 表示观察到评论获赞证据。
- 未观察到评论获赞通知不能解释成评论失败。
- 未知数据必须保存为 `NULL`，不能保存为 `0`。

## 6. SQLite 快照表

建议新增表：

```text
profile_stats_snapshots
```

建议字段：

```text
id
platform
account_id
task_run_id
handle
following
followers
likes
raw_following
raw_followers
raw_likes
approximate_fields_json
liked
liked_loaded
liked_complete
liked_status
activity_has_liked_your_comment
activity_comment_like_notifications_count
activity_notifications_scanned
activity_status
activity_scope
activity_complete
comment_publish_evidence
activity_matches_json
status
error
result_json
collected_at
created_at
```

保存规则：

- 每次 TikTok 养号任务结束后写入一条快照。
- 成功、部分成功、失败都记录。
- 部分成功时保存已知字段。
- 失败时保存失败状态和错误原因。
- 未知数值字段保存 `NULL`。
- `activity_matches_json` 限制条数和文本长度。
- `result_json` 保存结构化结果摘要。
- 不保存 Cookie、密码、完整接口响应或浏览器敏感状态。

## 7. 桌面端菜单设计

新增菜单建议命名：

```text
TikTok 账号数据
```

页面性质：

- 只读看板。
- 只展示自动采集结果。
- 不出现手动采集、批量采集或重新采集按钮。

### 7.1 顶部概览

展示：

- TikTok 账号总数。
- 已采集账号数。
- 最近 24 小时采集数。
- 采集成功数。
- 部分成功数。
- 采集失败数。
- 有评论获赞证据的账号数。
- 总 Followers。
- 总 Likes。
- 总 Liked。

页面文案必须明确：

```text
Likes = 主页获赞
Liked = 账号点赞过的视频
```

### 7.2 最新数据表

建议列：

```text
账号
Handle
Following
Followers
Likes
Liked
评论获赞证据
Liked 完整性
Activity 状态
采集状态
最近采集时间
关联任务
操作
```

操作列仅允许：

```text
查看详情
查看历史
```

### 7.3 详情抽屉

展示：

- 基础信息。
- 主页统计。
- Liked 数据。
- Activity 数据。
- 命中的评论获赞通知。
- 失败原因。
- 原始结构化结果摘要。

Activity 通知最多展示有限条数，例如 5 条或 10 条。

### 7.4 历史记录

展示每次养号任务后的采集快照：

```text
采集时间
任务 ID
Following
Followers
Likes
Liked
评论获赞通知数
Liked 完整性
采集状态
失败原因
```

首期先做历史表格，趋势图后续再做。

## 8. 分阶段实现

### 阶段 1：整理采集核心模块

目标：把当前独立脚本整理成可被 TikTok runner 内部调用的 collector。

主要工作：

- 保留 `profile_stats.py` 和 `profile_activity.py` 的采集能力。
- 提供内部调用函数，例如：

```python
collect_profile_snapshot(browser, account, timeout)
```

- 接收当前养号任务已经打开的浏览器会话。
- 不重新打开浏览器。
- 不关闭整个浏览器。
- 只创建和关闭采集用临时页面。
- 统一返回结构化结果。
- 使用项目现有 Patchright runtime 封装。
- 限制 Activity 通知文本长度和数量。

验收：

- 可以在已打开的 TikTok 浏览器会话内完成采集。
- 采集结果结构稳定。
- 采集失败能返回结构化错误。
- 当前采集相关单元测试继续通过。

### 阶段 2：接入 TikTok 养号任务收尾流程

目标：每次正常 TikTok 养号任务完成后自动采集。

推荐顺序：

```text
启动浏览器会话
→ 连接 CDP
→ 执行浏览、点赞、评论等养号动作
→ 自动采集账号数据
→ 保存采集快照
→ 关闭页面/浏览器
→ 关闭 provider session
```

主要工作：

- 在 TikTok runner 主任务完成后、关闭浏览器前调用 collector。
- 设置独立采集超时。
- 捕获采集异常。
- 确保无论采集成功、失败或超时，最后都执行浏览器清理。
- 记录采集阶段日志。
- 将采集状态与本次任务关联。

采集状态建议：

```text
success
partial_success
failed
skipped
timeout
```

验收：

- 跑完一次 TikTok 养号任务后自动触发采集。
- 采集发生在浏览器关闭之前。
- 采集失败后浏览器仍然关闭。
- 主任务成功但采集失败时，有明确日志和状态。

### 阶段 3：增加 SQLite 采集快照

目标：把自动采集结果保存下来，供桌面端展示。

主要工作：

- 在 runtime 数据库初始化中创建 `profile_stats_snapshots`。
- 新增保存函数，例如 `save_profile_snapshot()`。
- 写入成功、部分成功和失败记录。
- 保持老数据库兼容。
- 不将采集结果写入 `action_log` 替代快照表。

验收：

- 老数据库自动创建新表。
- 每次任务后写入一条快照。
- 同一账号多次任务形成历史记录。
- 采集失败也留下排查记录。
- 数据库中没有敏感凭据。

### 阶段 4：纳入 Python sidecar runtime

目标：确保 Windows 和 macOS 安装包都包含采集能力。

主要工作：

- 更新 runtime 入口或 manifest，使采集模块成为正式 runtime 能力。
- 确保 `profile_stats`、`profile_activity` 及其依赖被 PyInstaller 包含。
- 保证 TikTok runner 在打包环境中可以 import collector。
- 保证采集逻辑不依赖项目源码路径。
- 保证采集逻辑不依赖系统 Python。

建议保留一个内部 runtime 命令：

```text
profile-stats
```

该命令可以不暴露给 UI，但用于：

- CI 冒烟验证。
- 打包验证。
- 售后排障。
- 确认 runtime 已包含采集模块。

验收：

- 源码模式可以执行。
- Windows sidecar 可以执行。
- macOS sidecar 可以执行。
- 目标电脑没有 Python 和源码也能运行。

### 阶段 5：Windows 和 macOS 分平台打包

目标：GitHub Actions 产出的 Windows 和 macOS 包都具备采集能力。

Windows 构建：

```text
Windows GitHub runner
→ PyInstaller 打包 account-matrix-runtime.exe
→ Tauri Windows 包包含 account-matrix-runtime.exe
```

macOS 构建：

```text
macOS GitHub runner
→ PyInstaller 打包 account-matrix-runtime
→ Tauri macOS 包包含 account-matrix-runtime
```

主要工作：

- 按平台构建 Python sidecar。
- 按平台包含 Patchright 依赖和 driver 资源。
- 按平台配置 Tauri resources。
- 按平台验证 runtime 可执行权限。
- 避免 macOS 包内只有 Windows `.exe`。

验收：

- Windows 安装包中包含 Windows runtime。
- macOS 安装包中包含 macOS runtime。
- 两个平台的 runtime 都能 import 采集模块。
- 两个平台的 TikTok 养号任务结束后都能自动采集。

### 阶段 6：增加 Tauri 只读查询接口

目标：桌面端页面能读取 SQLite 中的采集结果。

不新增：

```text
run_profile_stats
manual_collect
batch_collect
```

只新增只读查询接口，例如：

```text
query_profile_stats_latest
query_profile_stats_history
query_profile_stats_detail
query_profile_stats_summary
```

查询能力：

- 查询所有 TikTok 账号最新快照。
- 查询单账号历史快照。
- 查询某次任务对应的采集结果。
- 查询概览统计。
- 查询失败记录。

验收：

- 表不存在时返回空数据，不影响应用启动。
- 能正确返回最新数据。
- 能按账号和时间查询历史。
- 能区分成功、部分成功、失败、未采集。
- 前端不需要解析 Python stdout。

### 阶段 7：新增桌面端只读菜单

目标：新增 `账号数据` 页面。

主要工作：

- 新增平台能力，例如 `profileStats`。
- TikTok 标记为 supported。
- 其他平台标记为 unsupported 或隐藏。
- 新增只读页面。
- 接入最新快照、详情和历史记录查询。
- 补充空状态、失败状态和部分成功状态。

页面不包含：

- 手动采集按钮。
- 批量采集按钮。
- 重新采集按钮。
- 独立打开浏览器按钮。

验收：

- TikTok 平台能进入页面。
- 非 TikTok 平台不会误展示 TikTok 数据。
- 页面打开后能看到最新自动采集数据。
- 未采集账号显示“未采集”。
- 采集失败显示失败原因。
- 历史记录能追溯每次任务后的快照。

### 阶段 8：端到端和跨平台验收

目标：验证完整交付链路。

Windows 验收：

```text
安装 Windows 包
→ 没有系统 Python
→ 执行 TikTok 养号任务
→ 自动采集
→ 自动关闭浏览器
→ 页面展示数据
```

macOS 验收：

```text
安装 macOS 包
→ 没有系统 Python 依赖
→ 执行 TikTok 养号任务
→ 自动采集
→ 自动关闭浏览器
→ 页面展示数据
```

共同验收：

- BitBrowser profile 能正常连接。
- 采集失败不会卡住任务。
- 浏览器最终会关闭。
- 未知值不会显示成 0。
- Liked 不完整有明确状态。
- Activity 未观察到时不显示“评论失败”。
- 日志不泄露 Cookie、密码或完整接口响应。
- 安装目录不包含用户数据。
- 重启应用后历史数据仍然存在。

## 9. Product BDD

```gherkin
Feature: TikTok 养号任务后自动采集账号数据

  Rule: TikTok 养号任务正常完成动作后，系统自动采集账号数据

    Scenario: P1 养号任务完成后生成账号数据快照
      Given 一个已配置浏览器环境的 TikTok 账号
      When 该账号完成一次正常养号任务
      Then 系统在关闭浏览器前自动采集主页统计、Liked 状态和 Activity 状态
      And 系统保存一条与本次任务关联的采集快照
      And 桌面端账号数据菜单展示该账号的最新采集结果

  Rule: 自动采集不提供人工触发入口

    Scenario: P2 用户只能查看采集结果
      Given 用户进入 TikTok 账号数据菜单
      When 页面展示账号数据
      Then 页面不提供手动采集、批量采集或重新采集按钮
      And 用户只能查看自动采集产生的最新结果和历史记录

  Rule: 采集失败不阻断浏览器关闭

    Scenario: P3 采集超时后仍然关闭浏览器
      Given 一个 TikTok 养号任务已经完成主要动作
      When 自动采集阶段发生超时
      Then 系统保存采集失败或部分成功记录
      And 系统继续关闭本次任务打开的浏览器
      And 桌面端展示最近采集失败原因

  Rule: Windows 和 macOS 安装包都必须包含平台对应采集 runtime

    Scenario: P4 macOS 安装包包含 macOS 采集能力
      Given GitHub Actions 在 macOS runner 上构建桌面端安装包
      When 用户安装 macOS 包并执行 TikTok 养号任务
      Then macOS 包内的平台 runtime 能执行采集模块
      And 任务结束后能自动保存采集快照
```

## 10. Technical BDD

```gherkin
Scenario: T1 TikTok runner 在关闭浏览器前调用 profile collector
  # Proof: Server
  # Surface: src/platforms/tiktok/runner.py
  # Entry: TikTok 养号任务主流程
  # Covers: P1, P3

  Given TikTok runner 已经完成浏览、点赞、评论等主任务动作
  When runner 进入浏览器清理前阶段
  Then runner 调用 collect_profile_snapshot(browser, account, timeout)
  And collector 返回结构化采集结果或结构化错误
  And runner 在 finally 清理路径中继续关闭浏览器

Scenario: T2 自动采集结果写入 SQLite 快照表
  # Proof: Server
  # Surface: src/core/runtime.py, profile_stats_snapshots
  # Entry: save_profile_snapshot()
  # Covers: P1, P3

  Given collector 返回成功、部分成功或失败结果
  When save_profile_snapshot() 保存本次结果
  Then profile_stats_snapshots 写入 account_id、platform、status、collected_at 和 result_json
  And 未知数值字段保持 NULL
  And task_run_id 关联本次养号任务

Scenario: T3 桌面端只读展示自动采集结果
  # Proof: UI
  # Surface: desktop ProfileStatsPage
  # Entry: query_profile_stats_latest
  # Covers: P2

  Given SQLite 中存在 TikTok 账号采集快照
  When 用户打开 TikTok 账号数据菜单
  Then 页面展示最新快照和历史记录
  And 页面不存在手动采集入口

Scenario: T4 Windows 和 macOS runtime 分别包含 profile collector
  # Proof: Acceptance
  # Surface: runtime/pyinstaller, GitHub Actions, Tauri resources
  # Entry: desktop package build
  # Covers: P4

  Given Windows runner 和 macOS runner 分别构建 Python sidecar runtime
  When Tauri 将平台对应 runtime 打入安装包
  Then Windows 包包含 account-matrix-runtime.exe
  And macOS 包包含 account-matrix-runtime
  And 两个平台的 runtime 都能 import profile_stats 和 profile_activity
```

## 11. 风险与取舍

- 采集会增加每次 TikTok 养号任务耗时，需要独立超时控制。
- TikTok 页面和接口不稳定，采集失败不能阻塞浏览器清理。
- Activity 采集只能证明已加载通知范围，不能证明完整历史。
- macOS 需要单独构建 runtime，不能复用 Windows `.exe`。
- BitBrowser 是外部依赖，安装包不会内置 BitBrowser 本身。
- 页面必须避免将“未观察到评论获赞通知”展示为“评论失败”。

## 12. 首期交付范围

首期做：

- 自动采集。
- SQLite 快照。
- Python sidecar runtime 包含采集模块。
- Windows 和 macOS 分平台 runtime 打包。
- Tauri 只读查询接口。
- `TikTok 账号数据` 只读菜单。
- 最新数据表。
- 详情抽屉。
- 历史记录表。

首期暂缓：

- 手动采集。
- 批量采集。
- 重新采集。
- 趋势图。
- 高级筛选。
- CSV 导出。
- 单独授权。
