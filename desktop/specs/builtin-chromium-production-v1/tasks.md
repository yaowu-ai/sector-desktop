# 内置 Chromium 生产可选方案 V1 Tasks

## M1 基线盘点与验收口径

- [x] 盘点当前 `builtin_chromium` provider 已实现能力。
- [x] 记录当前 capability matrix 中内置 Chromium 的状态和风险标签。
- [x] 盘点账号管理、养号任务、目标号互动、诊断页中浏览器环境展示是否完整。
- [x] 确认 TikTok 生产默认 provider 仍为 BitBrowser。
- [x] 确认旧 `accounts.yaml` 不新增字段仍按 BitBrowser 运行。
- [x] 定义内置 Chromium 晋级为生产可选的验收清单。
- [x] 新增专项 validation 文档模板。

## M2 账号隔离与目录管理

- [x] 确认每个账号默认使用独立 user data dir。
- [x] 确认默认目录位于 data dir 下的账号独立路径。
- [x] 增加或完善 `runtime.json` / 等价运行记录，记录账号、PID、端口和最近 CDP endpoint。
- [x] 运行两个内置 Chromium 账号，验证登录态和缓存不串。
- [x] 验证清理账号浏览器数据只删除该账号目录。
- [x] 验证应用升级或 runtime 重建不会默认删除 user data dir。
- [x] 在诊断中显示账号 user data dir 路径和读写状态。

## M3 代理能力与网络诊断

- [x] 校验 `http` 代理启动参数。
- [x] 校验 `https` 代理启动参数。
- [x] 校验 `socks5` 代理启动参数。
- [x] 支持代理格式错误时阻止启动并指向账号字段。
- [x] 支持代理密码脱敏展示。
- [x] 增加代理连通性诊断，至少检查 host/port 可达。
- [x] TikTok 页面 `ERR_CONNECTION_RESET`、超时、DNS、代理失败时输出可区分错误。
- [x] 执行日志不得包含代理密码明文。

## M4 启动、CDP 与关闭稳定性

- [x] 使用随机可用端口启动内置 Chromium。
- [x] 启动前检查端口占用。
- [x] 启动后轮询 `/json/version` 获取 CDP 状态。
- [x] 连接 Patchright 前校验 endpoint 可用。
- [x] 启动失败时输出 account_id、provider、port、executable、user data dir、proxy 摘要。
- [x] 任务结束时只关闭应用启动的 Chromium 进程。
- [x] 关闭时校验 PID 和账号运行记录匹配。
- [x] 浏览器已退出时关闭操作返回可理解结果。
- [x] 异常中断后再次运行同账号，能处理残留端口或残留进程。

## M5 TikTok 登录与人工接管验收

- [x] 使用内置 Chromium 已登录账号运行登录状态检测。
- [x] 未登录账号开启自动登录时，能填写账号密码并提交。
- [x] 自动登录成功后继续进入原任务。
- [x] 验证码场景进入人工接管。
- [x] 二次验证场景进入人工接管。
- [x] 安全检查场景进入人工接管。
- [x] 人工处理后点击继续检测，登录成功则继续任务。
- [x] 密码只通过本机安全凭据存储和临时环境变量传递。
- [x] 密码不出现在 accounts.yaml、备份、命令行、stdout、stderr、sessions.log。

## M6 TikTok 任务回归

- [x] 内置 Chromium 账号执行 FYP 养号最小任务。
- [x] 验证 FYP 浏览动作写入 `action_log`。
- [x] 验证点赞动作成功或失败都有清晰日志。
- [x] 验证关注动作不因 provider 差异直接失败。
- [x] 验证评论关闭时不执行评论。
- [x] 验证评论开启时评论池读取和阈值判断正常。
- [x] 内置 Chromium 账号执行目标号互动。
- [x] 验证目标主页打开和新视频读取。
- [x] 验证无新视频时正常跳过。
- [x] 验证发现新视频时按配置点赞、评论和关注。
- [x] 验证水位线写入和下次跳过逻辑。
- [x] 验证旧 BitBrowser 已登录账号仍按原逻辑运行。
- [x] 验证 BitBrowser 与内置 Chromium 账号混合队列能逐个执行。

## M7 UI 与产品状态晋级

- [x] 账号列表显示内置 Chromium provider 和 user data dir 摘要。
- [x] 新增/编辑账号表单中内置 Chromium 字段全中文。
- [x] 养号任务执行账号区域显示账号浏览器环境。
- [x] 目标号互动参与账号区域显示账号浏览器环境。
- [x] 两类启动确认框显示账号浏览器环境。
- [x] 执行记录或 Session 日志能追踪 provider。
- [x] 诊断页支持账号级内置 Chromium 启动和 CDP 检测。
- [x] provider 能力矩阵将内置 Chromium 状态从 `experimental` 改为 `production_optional`。
- [x] UI 移除“内置 Chromium（实验）”中的“实验”字样。
- [x] 设置页仍保留 BitBrowser 为默认推荐。
- [x] 发布说明明确：内置 Chromium 是生产可选，不等价替代 BitBrowser 指纹能力。

## M8 打包与跨电脑验收

- [x] 确认安装包包含内置 Chromium 所需二进制或明确依赖来源。
- [x] 在无源码目录的新电脑安装应用。
- [x] 验证不依赖系统 Python。
- [x] 新电脑通过 UI 新增内置 Chromium 账号。
- [x] 保存本机登录密码凭据。
- [x] 执行账号浏览器诊断。
- [x] 执行 TikTok 登录检测。
- [x] 执行 FYP 养号最小任务。
- [x] 执行目标号互动最小任务。
- [x] 验证安装包中 BitBrowser 默认行为仍正常。
- [x] 输出最终 validation 文档。

## 建议实施顺序

1. 先做基线盘点，明确当前内置 Chromium 还差哪些验收项。
2. 优先补启动、端口、代理和诊断错误信息。
3. 再做 TikTok 登录和人工接管真实回归。
4. 完成 FYP 与目标号互动专项验收。
5. 最后修改 capability 和 UI 文案，移除“实验”标记。
6. 重新打包，并在无源码的新电脑环境做完整验证。

## 不通过时的处理规则

- 如果代理、启动、CDP 或关闭任一基础能力不稳定，继续保留“实验”标记。
- 如果 TikTok 登录态检测不稳定，继续保留“实验”标记。
- 如果 FYP 或目标号互动无法完成最小任务，继续保留“实验”标记。
- 如果旧 BitBrowser 回归失败，不允许发布该变更。
- 如果密码或代理密码出现在配置、备份、命令行或日志中，不允许发布该变更。
