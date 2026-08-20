# Instagram 养号桌面端接入设计文档

## 1. 现状基线

`account-matrix` 已经是一个 Tauri + React 的桌面应用，核心链路分成三层：

- 前端桌面壳：`desktop/src/*`
- Rust/Tauri 命令层：`desktop/src-tauri/src/commands/*`
- Python runtime：`src/*`

当前 Instagram 在桌面端已经有平台入口，但能力矩阵仍标记为预留，`run_platform_task` 也仍然只允许 TikTok 自动执行。Python runtime 里虽然已经有 `src/platforms/instagram.py`，但只是一个 reserved stub，没有真正的养号实现。

`account-matrix-ins` 里则有完整的 Instagram 执行侧代码，包括：

- CLI 和调度入口
- BitBrowser/CDP 会话编排
- 页面动作与风控检测
- 会话日志、SQLite 记录和冷却

## 2. 选型

采用“把执行能力并入 `account-matrix` runtime，桌面端只调用 runner”的方式，不接入 `account-matrix-ins` 的界面层。

### 2.1 Python 侧

- 将 Instagram 执行逻辑整理为 `src/platforms/instagram_runner/` 目录下的独立包。
- 保留 `src/platforms/instagram.py` 作为兼容薄层，只负责导出 `InstagramRunner`。
- Instagram runner 复用现有 runtime 的锁、日志、路径解析、BitBrowser 接入和 SQLite 工具。
- runner 只负责执行，不负责桌面 UI。

### 2.2 桌面端侧

- 平台页将 Instagram 从 `reserved` 改为 `supported`。
- 任务页按平台切换表单：TikTok 保持现有 FYP 表单，Instagram 使用 Instagram 养号表单。
- Rust 命令层放开 Instagram 的 `warmupTask` 执行权限。
- 账号页、调度页、日志页和统计页继续复用现有结构，只是数据范围扩展到 Instagram。

## 3. 运行链路

1. 用户在桌面端切到 Instagram 平台。
2. 任务页读取 Instagram warm-up 配置并选择账号。
3. 前端调用 `run_platform_task`，传入 `platform=instagram` 和 warm-up 任务类型。
4. Tauri 命令层校验：平台、账号、BitBrowser profile、代理、当前任务锁。
5. Rust 启动 Python runtime 的 Instagram runner。
6. Runner 读取 `accounts.yaml`、BitBrowser profile 和本地数据目录，执行 ins 风格的浏览、点赞、评论、关注、快拍或 Reels 流程。
7. 任务过程写入 `actions.db`、`sessions.log` 和状态对象。
8. 风控页/验证码/异常代理触发时，runner 写入冷却并终止该账号会话。

## 4. 配置与数据设计

### 4.1 配置

Instagram 需要独立于 TikTok 的 warm-up 配置块，建议放在 `platforms.instagram.warmup` 下，字段与 ins 脚本保持一致或等价：

- `duration`
- `sessions_per_day`
- `one_per_window`
- `active_hours`
- `like_prob`
- `max_likes_per_day`
- `max_comments_per_day`
- `comment_prob`
- `max_comments_per_session`
- `gap`
- `block_cooldown_hours`
- `require_proxy`
- `no_like`
- `no_save`
- `no_comment`
- `no_follow`
- `no_stories`
- `no_reels`
- `no_explore`

账号级配置继续放在 `accounts[]`，包括 `id`、`platform`、`enabled`、`profile`、`proxy`、`scheduled` 和 `active_hours`。

### 4.2 持久化

复用现有 `actions.db`，新增或复用以下持久化责任：

- `action_log`：记录 Instagram 任务结果和关键动作摘要。
- `scheduler_job_runs`：记录 Instagram 调度触发。
- `risk_cooldown`：记录账号冷却截止时间和原因。

不引入独立的 `account-matrix-ins` 数据库文件。

## 5. 前端设计

### 5.1 平台页

Instagram 行展示为已支持执行，能力列里 `warmupTask` 变成支持状态。目标号互动仍保持预留，除非后续单独开故事。

### 5.2 任务页

Instagram 平台下的任务页不再显示 TikTok 的 FYP 字段，而显示 Instagram warm-up 字段。页面仍保留账号选择、执行确认和运行输出面板。

### 5.3 账号页与调度页

- 账号页继续复用当前账号管理与 BitBrowser 绑定逻辑。
- 调度页继续复用现有计划模型，只是 Instagram 账号也能参与排期。
- 记录页和统计页按 platform 过滤即可看到 Instagram 数据。

## 6. 后端设计

### 6.1 Tauri 命令层

- `ensure_platform_can_execute` 放开 Instagram 的 warm-up 执行。
- `run_platform_task` 接受 Instagram 的 warm-up task type。
- 配置保存接口支持按平台写入 Instagram warm-up 段。
- 任务状态、终止、恢复、日志读取逻辑保持共用。

### 6.2 Python runtime

Instagram runner 需要具备以下职责：

- profile 解析和 BitBrowser 接管
- 页面动作执行
- 风控检测与冷却写入
- 会话级日志和动作摘要落盘
- 支持单次运行和调度运行

推荐复用的现有能力：

- `core/runtime.py` 的 DB、锁、路径和日志能力
- 现有 `human_mouse` 拟人鼠标
- 现有 BitBrowser 接口
- 现有账号/代理配置和平台规范

## 7. 兼容性与风险

- TikTok 现有运行路径必须完全保留。
- Instagram 的新增配置不能破坏旧配置迁移。
- 冷却与风控必须是持久化的，重启后仍有效。
- 不允许桌面端在未完成 profile / proxy 校验时直接发起 Instagram 自动化。

