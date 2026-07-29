# PC 端养号产品 V1 Requirements

## 来源与范围

本规格结合仓库根目录的 `PC端养号产品方案_脚本功能完整版.md` 和 `PC端养号产品V1开发步骤.md` 整理，用于指导 `desktop/` PC 桌面端 V1 开发。

V1 的目标不是重写现有自动化逻辑，而是把当前 Python 脚本产品化为可视化、可配置、可监控、可交付的桌面应用。现有 `src/douyin-fetcher/` 不纳入 V1 范围。

## 产品边界

V1 必须支持真实可执行的 TikTok 脚本能力：

- TikTok 账号管理、启用停用、IP 分组、active_hours 班次、BitBrowser profile 绑定。
- BitBrowser Local API 检测、profile 打开、关闭、状态检测、创建、代理检测、账号配置同步。
- TikTok FYP 浏览、点赞、关注、评论任务配置和运行。
- 目标品牌号新视频检测、点赞、评论、可选关注和水位线记录。
- FastAPI + APScheduler 调度服务启动、停止、健康检查和今日排期展示。
- 评论素材池读取、编辑和保存。
- SQLite 执行记录、目标互动记录、目标关注记录和统计展示。
- Gmail 初始化、批量邮箱处理、点赞诊断、评论诊断。
- ServerChan、Bark、Webhook 通知配置。

V1 不承诺以下能力：

- TikTok 视频发布、关键词搜索养号、收藏动作。
- Instagram、WhatsApp、抖音自动执行。
- 云端后台、团队权限、跨设备同步、审批流。
- 精准中途暂停和完整断点恢复。
- Chrome、Edge 或自定义浏览器自动执行。

Instagram、WhatsApp、抖音仅作为平台占位和扩展结构存在，不能在 UI 中显示为可执行任务。

## 用户角色

- 运营人员：通过桌面界面维护账号、配置任务、启动运行、查看日志和统计。
- 技术维护人员：配置 Python 路径、BitBrowser API、数据目录，诊断执行失败原因。

## 功能需求

### R1 应用外壳与导航

应用必须提供固定左侧导航和顶部状态区。

导航包含：

- 首页
- 平台管理
- 账号管理
- 浏览器环境
- 养号任务
- 目标号互动
- 调度计划
- 评论素材
- 执行记录
- 统计报表
- Gmail 初始化
- 诊断工具
- 系统设置

验收：

- Given 桌面应用启动成功，When 用户进入应用，Then 左侧导航完整展示上述页面。
- Given BitBrowser API 或当前任务状态变化，When 顶部状态区刷新，Then 用户能看到最新 API 状态、当前执行状态和刷新入口。
- Given 平台为 Instagram、WhatsApp 或抖音，When 用户查看平台能力，Then UI 只展示占位或未适配状态，不允许启动自动任务。

### R2 系统设置与本地路径

应用必须支持配置项目根目录、Python 可执行文件、BitBrowser API 地址、配置文件路径、数据目录、评论池路径、日志轮询间隔和通知配置。

验收：

- Given 默认开发环境，When 应用读取路径，Then `desktop/..` 被识别为项目根目录。
- Given `config/accounts.yaml` 不存在或解析失败，When 应用启动或刷新配置，Then 页面展示失败路径和错误原因。
- Given 用户修改设置，When 保存成功，Then 后续命令使用新的路径和配置。

### R3 账号管理

应用必须读取并展示 `config/accounts.yaml` 中的账号配置。

账号字段：

- 账号 ID
- 平台
- 启用状态
- IP 分组
- active_hours
- BitBrowser profile_id
- profile 打开状态
- 最近执行时间
- 最近执行结果
- 备注

操作：

- 新增账号
- 编辑账号
- 启用或停用
- 批量启用或停用
- 检测 profile 状态
- 打开 profile
- 关闭 profile
- 运行该账号
- 查看该账号日志

保存校验：

- 账号 ID 非空且不重复。
- enabled 必须是布尔值。
- bitbrowser_profile_id 非空时不能重复。
- active_hours 为 `[start, end]` 数组，`start < end`，小时范围 0-24。
- 同一 ip_group 下启用账号的 active_hours 不得重叠；重叠时至少告警，建议阻止保存。
- target_accounts.participants 必须引用已存在账号。

验收：

- Given 当前配置有 20 个 TikTok 账号，When 用户打开账号管理页，Then 页面展示全部账号及其 enabled、ip_group、active_hours、profile_id。
- Given 用户保存账号配置，When 校验通过，Then 应用先备份原 `accounts.yaml`，再写回新配置。
- Given 配置存在重复账号 ID 或重复 profile_id，When 用户保存，Then 保存失败并指出冲突字段。

### R4 浏览器环境与代理管理

V1 默认执行环境必须是 BitBrowser Local API。

应用必须支持：

- 检测 BitBrowser API 是否可用。
- 列出 BitBrowser profile。
- 检测 profile 是否已打开。
- 打开 profile。
- 关闭 profile。
- 创建单个 profile。
- 批量按代理文件创建 profile。
- 检测代理格式、可用性和是否已被其他窗口使用。
- 从 BitBrowser 窗口列表同步账号配置。

验收：

- Given BitBrowser 客户端未启动，When 用户检测 API，Then 页面展示连接失败并阻止启动任务。
- Given profile 已打开，When 用户启动对应账号任务，Then 按脚本语义跳过账号并记录 skip。
- Given 用户批量创建 profile，When 执行结束，Then 页面展示成功、失败、跳过明细。
- Given 用户执行账号同步，When dry-run 成功，Then 页面展示将追加或修改的账号配置，用户确认后才写入。

### R5 TikTok FYP 养号任务

应用必须提供 TikTok FYP 养号任务配置和启动能力。

配置字段：

- 任务名称
- 执行账号：全部启用、单账号、多账号
- FYP 浏览时长范围
- 点赞概率
- 每 session 关注数量范围
- 评论开关
- 每 session 评论数量范围
- 评论触发概率
- 评论数门槛
- 评论池
- 账号间隔时间
- 任务结束是否关闭 BitBrowser

执行规则：

- 运行全部启用账号调用 `python src/main.py`。
- 运行单账号调用 `python src/main.py --account <account_id>`。
- 多账号 V1 可由桌面端队列逐个调用 `main.py --account`。
- 启动前必须检查 Python、配置文件、BitBrowser API、run.lock、账号和 profile_id。
- 同一时间只允许一个养号执行进程。

验收：

- Given 用户选择单个账号，When 点击运行并确认，Then 后端启动 `main.py --account <account_id>`。
- Given 存在活跃 `data/run.lock`，When 用户启动任务，Then 应用阻止重复启动并展示当前 PID 或锁文件状态。
- Given 任务运行中，When 用户打开任务详情，Then 能看到当前账号、动作进度、stdout/stderr、sessions.log 增量和结果统计。

### R6 目标号互动

应用必须支持配置和查看目标品牌号互动。

配置字段：

- enabled
- handles
- participants
- first_run_latest_n
- max_videos_per_run
- like_probability
- comment_probability
- comments_file
- follow
- follow_probability

规则：

- 新视频以目标主页 `/video/<video_id>` 里的 `video_id` 判断。
- 每个执行账号和每个目标号独立维护水位线。
- 无历史记录时只处理最新 `first_run_latest_n` 条。
- 有历史记录时只处理 `video_id > 水位线` 的新视频。
- 单次每目标号最多处理 `max_videos_per_run` 条。
- 目标号互动由 `main.py` 在 FYP 后触发，V1 不单独调用 `target_engage.py`。

验收：

- Given 用户打开目标号互动页，When 数据加载完成，Then 页面展示目标号、参与账号、概率、评论池和最近水位线。
- Given 用户启动参与账号，When 执行任务，Then 桌面端逐个运行参与账号的 `main.py --account`。
- Given 用户查看水位线，When 查询完成，Then 页面按执行账号和目标号展示最大 video_id、最近时间、点赞数、评论数。
- Given 用户触发重置水位线，When UI 提供该能力，Then 必须二次确认。

### R7 调度计划

应用必须包装 `src/scheduler.py`。

功能：

- 启动调度服务。
- 停止调度服务。
- 展示 scheduler 进程状态。
- 调用 `GET http://127.0.0.1:9601/health`。
- 展示今日排期、下一次执行账号、下一次执行时间、run.lock 状态、BitBrowser API 状态。
- 编辑 `scheduler.fires_per_day`、账号 active_hours 和 ip_group。

验收：

- Given 调度服务未启动，When 用户打开调度计划页，Then 页面显示 stopped 状态。
- Given 调度服务已启动，When 健康检查成功，Then 页面展示 jobs、next_run 和 lock_held_externally。
- Given 用户停止调度服务，When 当前有账号任务已经被触发，Then UI 明确提示停止调度服务不等于立刻停止当前账号任务。
- Given 用户查看调度时间，Then UI 明确当前 V1 使用运行机器本地时间。

### R8 评论素材

应用必须读写：

- `config/comments.txt`
- `config/comments_brand.txt`

规则：

- 每行一条评论。
- 空行忽略。
- `#` 开头的行忽略。
- 保存后现有 Python 脚本仍可直接读取。

验收：

- Given 用户打开评论素材页，When 文件读取成功，Then 页面分区展示通用评论池和品牌评论池。
- Given 用户保存素材，When 校验通过，Then 文件按兼容 txt 格式写回。
- Given 用户输入重复或空评论，When 保存，Then 页面给出提醒或阻止。

### R9 执行记录与统计

应用必须读取 `data/actions.db` 和 `data/sessions.log`。

SQLite 表：

- action_log
- target_engagements
- target_follows

统计范围：

- 全部
- 今日
- 最近 N 天
- 自定义时间范围

验收：

- Given `actions.db` 存在，When 用户打开执行记录，Then 页面展示账号、动作、状态、详情和时间。
- Given 用户查看统计，When 选择今日或最近 N 天，Then 统计逻辑与 `src/stats.py` 等价。
- Given 用户查看实时日志，When `sessions.log` 增长，Then 日志面板按增量追加展示。

### R10 Gmail 初始化

应用必须支持单账号和批量 Gmail 初始化。

单账号字段：

- BitBrowser 窗口名称
- Google 邮箱
- 当前密码
- 新密码
- 搜索词
- 页面超时
- 条款页超时

批量字段：

- 邮箱文件
- 起始 BitBrowser 窗口名称
- 页面超时
- 条款页超时
- 失败时保留窗口

安全要求：

- 密码字段隐藏输入。
- 优先通过 `--password-env` 和 `--new-password-env` 传递密码。
- 密码、代理密码、邮箱文件中的密码不得进入普通日志。

验收：

- Given 用户运行单账号 Gmail 初始化，When 后端启动脚本，Then 密码通过环境变量传递，不出现在命令行参数中。
- Given 登录出现人工验证，When 脚本返回或停留，Then 页面展示需要人工处理的状态。

### R11 诊断工具

应用必须支持点赞诊断和评论诊断。

点赞诊断：

- 执行 `python src/test_like.py --account <account_id>`。
- 展示策略执行结果、点赞前后状态、stdout 和 stderr。

评论诊断：

- 执行 `python src/test_comment.py --account <account_id> --min <n> --max-scroll <n>`。
- 支持只定位不发布。
- 展示扫描视频数、评论数、选择器 HTML、输入框定位结果和发布结果。

验收：

- Given 用户选择账号并运行诊断，When 脚本执行结束，Then 页面展示结构化结果或完整脱敏日志。

### R12 通知与安全

应用必须支持通知配置：

- enabled
- type: serverchan / bark / webhook
- serverchan.sendkey
- bark.url
- webhook.url
- 测试发送

安全要求：

- 敏感字段默认隐藏。
- 代理密码、Google 密码、Webhook secret 不写入普通日志。
- 删除账号不默认删除 BitBrowser profile。
- 清理日志、强制停止、重置水位线等高风险操作必须二次确认。

验收：

- Given 通知配置启用，When 用户点击测试发送，Then 页面展示发送成功或失败原因。
- Given 日志包含敏感字段，When 前端展示日志，Then 敏感值被脱敏。

## 完成定义

V1 完成必须满足：

- 不用命令行也能完成当前 Python 脚本主要操作。
- 所有当前脚本能力都有对应页面入口或功能按钮。
- 所有未实现平台能力不会被误认为可执行。
- 现有命令行脚本仍可单独运行。
- 桌面端异常提示能定位到账号、profile、脚本、配置或 BitBrowser API。
- 运行记录和统计可被运营人员直接查看。
- 产品配置修改后能真实影响下一次脚本运行。
