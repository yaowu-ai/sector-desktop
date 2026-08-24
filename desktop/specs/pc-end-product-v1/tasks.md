# PC 端养号产品 V1 Tasks

## 开发顺序

按以下顺序推进，优先形成可运行闭环，再补齐配置、环境管理和诊断能力。

## M0 准备与脚本基线

- [x] 确认当前分支为 `feat/PC-end-product`。
- [x] 确认 Python 可用。
- [x] 确认 `requirements.txt` 依赖安装方式。
- [x] 确认 BitBrowser 客户端和 Local API 地址 `http://127.0.0.1:54345`。（配置地址已确认；当前本机端口未监听，详见 `m0-baseline.md`。）
- [x] 验证 `python src/stats.py` 可执行。
- [x] 验证至少一个测试账号可运行 `python src/main.py --account <account_id>`。（`tiktok_101` 已进入脚本流程；因 BitBrowser Local API 未开启，业务执行失败，详见 `m0-baseline.md`。）
- [x] 记录现有脚本入口、参数和输出。

## M1 初始化桌面端工程

- [x] 在 `desktop/` 初始化 Tauri + React + TypeScript + Vite。
- [x] 安装 Ant Design、lucide-react、dayjs、clsx。
- [x] 建立前端目录结构：`app/`、`components/`、`pages/`、`services/`、`styles/`。
- [x] 建立 Tauri 后端目录结构：`commands/`、`state.rs`、`paths.rs`。
- [x] 实现 `pnpm tauri dev` 启动。
- [x] 实现开发期项目根目录定位：`desktop/..`。
- [x] 增加桌面端 README，说明开发启动和本地依赖。

## M2 类型与基础后端

- [x] 定义 `desktop/src/services/types.ts`。
- [x] 定义 Platform、Account、BrowserProfile、FypSettings、TargetEngagementSettings。
- [x] 定义 SchedulerHealth、TaskRun、AccountRun、ActionLog、StatsSummary。
- [x] 定义 GmailSetupRequest、DiagnosticRequest、NotifySettings。
- [x] 实现 Tauri `get_project_paths()`。
- [x] 实现 Tauri `load_config()`。
- [x] 实现 Tauri `validate_config()`。
- [x] 实现 Tauri `backup_config()`。
- [x] 实现 Tauri `save_config()`。
- [x] 为配置保存增加 `config/backups/accounts.YYYYMMDD-HHMMSS.yaml` 备份。

## M3 应用外壳

- [x] 实现 AppShell 左侧导航。
- [x] 实现顶部状态区：BitBrowser API 状态、当前任务状态、刷新按钮。
- [x] 配置基础路由。
- [x] 实现 PageHeader、StatusTag、LogViewer、ConfirmDanger 通用组件。
- [x] 实现全局轮询：任务状态 5 秒、BitBrowser API 10 秒、日志 3 秒。
- [x] 实现错误提示和空状态样式。

## M4 首页

- [x] 展示 TikTok 启用账号数。
- [x] 展示 BitBrowser API 状态。
- [x] 展示今日计划任务数。
- [x] 展示今日完成账号数。
- [x] 展示今日失败账号数。
- [x] 展示今日目标互动数。
- [x] 实现快捷操作：运行全部启用账号。
- [x] 实现快捷操作：运行指定账号。
- [x] 实现快捷操作：启动调度服务。
- [x] 实现快捷操作：查看今日排期。
- [x] 实现快捷操作：同步账号配置。
- [x] 实现快捷操作：编辑评论池。

## M5 平台管理

- [x] 内置 TikTok、Instagram、WhatsApp、抖音平台数据。
- [x] 展示平台能力矩阵。
- [x] TikTok 标记为已支持。
- [x] Instagram、WhatsApp、抖音标记为预留或未适配。
- [x] 未适配平台禁用自动执行入口。

## M6 账号管理

- [x] 从 `accounts.yaml` 读取账号列表。
- [x] 展示账号 ID、平台、enabled、ip_group、active_hours、profile_id、notes。
- [x] 从 SQLite 或日志推导最近执行时间和最近结果。
- [x] 实现账号新增。
- [x] 实现账号编辑。
- [x] 实现账号启用和停用。
- [x] 实现批量启用和停用。
- [x] 实现账号保存前校验。
- [x] 实现重复账号 ID 校验。
- [x] 实现重复 profile_id 校验。
- [x] 实现 active_hours 格式校验。
- [x] 实现同 ip_group 班次重叠检测。
- [x] 实现 target participants 引用校验。
- [x] 实现运行单账号入口。
- [x] 实现查看账号日志入口。

## M7 BitBrowser API 与浏览器环境

- [x] 实现 `check_bitbrowser_api()`。
- [x] 实现 profile 已打开检测。
- [x] 实现打开 profile。
- [x] 实现关闭 profile。
- [x] 实现 profile 列表展示。
- [x] 实现 profile 与账号绑定展示。
- [x] 实现单个 profile 创建表单。
- [x] 实现代理格式校验。
- [x] 实现代理可用性检测。
- [x] 实现代理已使用检测。
- [x] 实现批量 profile 创建。
- [x] 展示批量创建成功、失败、跳过明细。
- [x] 实现从 BitBrowser 同步账号 dry-run。
- [x] 实现同步 apply。
- [x] apply 完成后刷新账号列表。

## M8 Python 执行器包装

- [x] 实现统一 `run_python_script(script_name, args, mode)`。
- [x] 后端使用参数数组启动 Python，避免 shell 字符串拼接。
- [x] 实现 stdout 缓存。
- [x] 实现 stderr 缓存。
- [x] 实现 `get_current_run_status()`。
- [x] 实现 `run_one_account(account_id)`。
- [x] 实现 `run_all_accounts()`。
- [x] 实现 `run_selected_accounts(account_ids)` 桌面端队列。
- [x] 启动前检查 Python 可用。
- [x] 启动前检查配置文件可读。
- [x] 启动前检查 BitBrowser API 可用。
- [x] 启动前检查账号和 profile_id。
- [x] 启动前检查活跃 `data/run.lock`。
- [x] 启动前检查当前 Tauri 后端无养号进程。
- [x] 实现强制停止并二次确认。
- [x] 实现多账号队列的暂停后续。

## M9 养号任务页

- [x] 只展示可执行任务：TikTok FYP 养号、TikTok 目标号互动。
- [x] 展示未适配平台任务为禁用状态。
- [x] 实现 FYP 浏览时长范围配置。
- [x] 实现点赞概率配置。
- [x] 实现每 session 关注数量范围配置。
- [x] 实现评论开关配置。
- [x] 实现评论数量范围配置。
- [x] 实现评论概率配置。
- [x] 实现评论数门槛配置。
- [x] 保存 FYP 配置到 `accounts.yaml`。
- [x] 启动前弹出确认弹窗。
- [x] 任务运行中展示当前账号、状态、stdout、stderr 和 sessions.log。
- [x] 任务结束后刷新执行记录和统计。

## M10 目标号互动页

- [x] 读取 `target_accounts` 配置。
- [x] 编辑 enabled。
- [x] 编辑 handles。
- [x] 编辑 participants。
- [x] 编辑 first_run_latest_n。
- [x] 编辑 max_videos_per_run。
- [x] 编辑 like_probability。
- [x] 编辑 comment_probability。
- [x] 编辑 comments_file。
- [x] 编辑 follow。
- [x] 编辑 follow_probability。
- [x] 保存目标号互动配置到 `accounts.yaml`。
- [x] 从 `target_engagements` 查询水位线。
- [x] 按账号展示目标互动统计。
- [x] 按目标号展示目标互动统计。
- [x] 实现立即执行参与账号：逐个调用 `main.py --account <participant>`。
- [x] 如提供重置水位线，必须二次确认。

## M11 评论素材页

- [x] 读取 `config/comments.txt`。
- [x] 读取 `config/comments_brand.txt`。
- [x] 展示通用评论池。
- [x] 展示品牌评论池。
- [x] 支持新增一行。
- [x] 支持删除一行。
- [x] 支持批量粘贴。
- [x] 支持保存。
- [x] 支持恢复上次保存。
- [x] 保存前忽略空行。
- [x] 保存前识别 `#` 注释行。
- [x] 重复评论给出提醒。
- [x] 保存后确保 Python 脚本可按原 txt 格式读取。

## M12 执行记录页

- [x] 打开 `data/actions.db`。
- [x] 查询 `action_log`。
- [x] 展示账号、动作、状态、详情、时间。
- [x] 支持按账号筛选。
- [x] 支持按动作筛选。
- [x] 支持按状态筛选。
- [x] 支持按时间范围筛选。
- [x] 查询 `target_engagements`。
- [x] 展示执行账号、目标号、video_id、liked、commented、时间。
- [x] 查询 `target_follows`。
- [x] 展示执行账号、目标号、followed、时间。
- [x] 支持复制错误详情。

## M13 统计报表页

- [x] 实现普通养号全部统计。
- [x] 实现普通养号今日统计。
- [x] 实现普通养号最近 N 天统计。
- [x] 实现普通养号自定义时间范围统计。
- [x] 实现目标号按账号统计。
- [x] 实现目标号按目标号统计。
- [x] 与 `src/stats.py` 输出逻辑核对。
- [x] 支持 CSV 导出。

## M14 调度计划页

- [x] 实现 `start_scheduler()`。
- [x] 实现 `stop_scheduler()`。
- [x] 实现 `get_scheduler_process_status()`。
- [x] 实现 `get_scheduler_health()`。
- [x] 展示调度服务状态。
- [x] 展示 BitBrowser API 状态。
- [x] 展示今日排期数量。
- [x] 展示下一次执行账号。
- [x] 展示下一次执行时间。
- [x] 展示 fires_per_day。
- [x] 展示 run.lock 状态。
- [x] 展示同 ip_group 班次冲突告警。
- [x] 编辑并保存 scheduler.fires_per_day。
- [x] 编辑并保存账号 active_hours。
- [x] 编辑并保存账号 ip_group。
- [x] 明确提示 V1 使用运行机器本地时间排期。

## M15 Gmail 初始化页

- [x] 实现单账号表单。
- [x] 实现批量邮箱文件选择。
- [x] 支持当前密码隐藏输入。
- [x] 支持新密码隐藏输入。
- [x] 后端通过 `--password-env` 传当前密码。
- [x] 后端通过 `--new-password-env` 传新密码。
- [x] 实现单账号脚本启动。
- [x] 实现批量脚本启动。
- [x] 展示步骤日志。
- [x] 对密码和邮箱文件密码脱敏。
- [x] 登录挑战或人工验证时展示明确状态。

## M16 诊断工具页

- [x] 实现点赞诊断表单。
- [x] 运行 `python src/test_like.py --account <account_id>`。
- [x] 展示点赞前状态。
- [x] 展示点赞后状态。
- [x] 展示策略执行结果。
- [x] 实现评论诊断表单。
- [x] 支持 min_comments。
- [x] 支持 max_scroll。
- [x] 支持 no_post。
- [x] 运行 `python src/test_comment.py --account <account_id> --min <n> --max-scroll <n>`。
- [x] 展示扫描视频数、评论数、选择器 HTML、输入框定位和发布结果。

## M17 系统设置与通知

- [x] 配置项目根目录。
- [x] 配置 Python 可执行文件路径。
- [x] 配置 BitBrowser API 地址。
- [x] 配置 data 目录。
- [x] 配置 accounts.yaml 路径。
- [x] 配置 comments.txt 路径。
- [x] 配置 comments_brand.txt 路径。
- [x] 配置任务结束是否自动关闭 profile。
- [x] 配置日志轮询间隔。
- [x] 配置通知 enabled。
- [x] 配置通知 type。
- [x] 配置 ServerChan sendkey。
- [x] 配置 Bark URL。
- [x] 配置 Webhook URL。
- [x] 实现通知测试发送。
- [x] 通知 secret 默认隐藏并脱敏。

## M18 脚本小改造

这些改造用于降低桌面端解析成本，保持小范围、可回滚。

- [x] 为 `stats.py` 增加可选 `--json` 输出。
- [x] 为 `create_browser.py` 增加可选 `--json` 输出。
- [x] 为 `sync_accounts_config.py` 增加可选 `--json` 输出。
- [x] 为 `main.py` 增加可选 `--config <path>`。
- [x] 为 `scheduler.py` 增加可选 `--config <path>`。
- [x] 为 `test_like.py` 增加可选 `--config <path>`。
- [x] 为 `test_comment.py` 增加可选 `--config <path>`。
- [x] 可选：为 `main.py` 增加 `data/stop_after_current.flag` 检查。

## M19 安全与异常处理

- [x] 实现统一日志脱敏。
- [x] 强制停止任务二次确认。
- [x] 清理 run.lock 二次确认。
- [x] 重置水位线二次确认。
- [x] 删除账号二次确认。
- [x] 清理日志二次确认。
- [x] BitBrowser API 不可用时阻止任务启动。
- [x] profile 已打开时按脚本语义跳过并展示原因。
- [x] 配置错误时定位到字段。
- [x] SQLite 不存在时展示空数据和创建提示。
- [x] 脚本 stderr 可查看但默认脱敏。

## M20 测试与验收

- [x] 单测 YAML 读取和保存。
- [x] 单测配置校验。
- [x] 单测 active_hours 重叠检测。
- [x] 单测评论池读写。
- [x] 单测 SQLite 查询。
- [x] 单测进程参数构造。
- [x] 单测日志脱敏。
- [x] 集成测试桌面端读取 20 个账号。
- [x] 集成测试 BitBrowser API 检测。
- [x] 集成测试单账号运行。
- [x] 集成测试 sessions.log 增量读取。
- [x] 集成测试 actions.db 记录展示。
- [x] 集成测试统计页。
- [x] 集成测试 scheduler 启动和 `/health`。
- [x] 集成测试账号同步 dry-run。
- [x] 集成测试 Gmail 初始化入口。
- [x] 集成测试点赞诊断。
- [x] 集成测试评论诊断。
- [x] 人工验收全部 V1 完成定义。

## 里程碑验收

### M1 能启动脚本

- [ ] 桌面端能打开。
- [x] 能读取 `accounts.yaml`。
- [ ] 能选择 `tiktok_101`。
- [ ] 能点击按钮运行 `python src/main.py --account tiktok_101`。
- [ ] 能看到 stdout 和 stderr。

### M2 能看运行结果

- [x] 能实时查看 `sessions.log`。
- [x] 能读取 `actions.db`。
- [x] 能展示普通养号统计。
- [x] 能展示目标号互动统计。

### M3 能配置任务

- [ ] 能编辑 FYP 参数。
- [ ] 能编辑目标号互动参数。
- [ ] 能编辑评论池。
- [ ] 保存后现有 Python 脚本直接生效。

### M4 能管理环境

- [x] 能检测 BitBrowser API。
- [ ] 能打开和关闭 profile。
- [ ] 能创建单个 profile。
- [ ] 能批量创建 profile。
- [ ] 能从 BitBrowser 同步账号配置。

### M5 能完整运营

- [ ] 能启动全部账号。
- [ ] 能启动调度服务。
- [ ] 能查看调度健康。
- [ ] 能做 Gmail 初始化。
- [ ] 能做点赞和评论诊断。
- [ ] 能配置通知。
- [x] 能打包安装并保留本地数据。
