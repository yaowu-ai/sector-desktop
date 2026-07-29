# 内置 Chromium 生产可选方案 V1 基线盘点

盘点日期：2026-07-28

## 结论

当前代码已经把浏览器 provider 收敛为 `bitbrowser` 与 `builtin_chromium` 两种，并且 TikTok runner 已通过统一 provider adapter 获取 CDP endpoint。`builtin_chromium` 已具备基础启动、关闭、CDP endpoint、每账号 user data dir、基础代理参数和后端账号诊断能力，但仍标记为实验，不满足直接晋级为生产可选的验收口径。

TikTok 生产默认 provider 当前仍是 BitBrowser。旧 `accounts.yaml` 在缺少 `browser_provider` 和 `browser` 字段时，仍会解析为 BitBrowser 并沿用 `bitbrowser_profile_id`。

## 当前 provider 能力

| 能力项 | 当前状态 | 证据 |
| --- | --- | --- |
| provider 枚举 | 已限制为 `bitbrowser`、`builtin_chromium` | `src/browser_providers.py`、`src/platform_config.py`、`desktop/src-tauri/src/commands/config.rs` |
| 默认 provider | BitBrowser | `DEFAULT_BROWSER_PROVIDER = "bitbrowser"`，桌面本地设置默认值也是 `bitbrowser` |
| TikTok runner 集成 | 已走 `provider_for_account(account, config)` | `src/platforms/tiktok/runner.py` |
| 内置 Chromium 启动 | 已实现 | `BuiltinChromiumProvider.start_session` 使用本机 Chromium executable、随机空闲端口、`--user-data-dir` 和 `--remote-debugging-port` |
| CDP endpoint | 已实现基础等待和 `/json/version` 检测 | `wait_for_cdp`、`test_cdp_endpoint` |
| 账号隔离目录 | 已实现默认目录解析 | `<data_dir>/browser/builtin_chromium/<account_id>/user-data` |
| 运行记录 | 已有等价记录，但文件名/字段与设计不完全一致 | 当前为 `session.json`，包含 provider、account_id、pid、cdp_endpoint、user_data_dir、executable、started_at |
| 基础代理启动参数 | 已实现格式到 `--proxy-server` 的转换 | 支持 `http`、`https`、`socks5`，支持 `host:port` 和 `host:port:username:password` |
| 关闭 | 已实现基础 PID 关闭 | `close_session` 关闭 session 中 process_id 并清理 session 记录 |
| 诊断后端 | 已实现账号级诊断命令 | Tauri `diagnose_account_browser` 可检查 capability、executable、user data dir 和 session 记录 |
| 清理本地数据 | 已实现账号级清理命令 | Tauri `cleanup_builtin_chromium_data` 删除该账号 user data dir 并清 session 记录 |

## Capability Matrix 当前状态

| Provider | implemented | production_ready | can_launch | can_close | provides_cdp_endpoint | requires_profile_id | supports_tiktok | risk_level |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `bitbrowser` | true | true | true | true | true | true | true | `stable` |
| `builtin_chromium` | true | false | true | true | true | false | true | `experimental` |

M1 只记录当前状态，不把 `builtin_chromium` 改为 `production_optional`。该状态变更必须等 M2-M6 验收和 BitBrowser 回归通过后，在 M7 执行。

## UI 展示盘点

| 页面/区域 | 当前状态 | 缺口归属 |
| --- | --- | --- |
| 账号管理列表 | 已显示浏览器环境、登录邮箱、登录状态；内置 Chromium 显示 user data dir 摘要 | 文案仍标“实验”，M7 处理 |
| 新增/编辑账号表单 | 已支持 BitBrowser 与内置 Chromium；内置 Chromium 字段包含代理类型、代理、用户数据目录、自动登录配置 | 文案仍标“实验”，M7 处理 |
| 养号任务执行账号区域 | 已显示本次 FYP 账号浏览器环境和目标号浏览器环境 | 风险提示仍写“打开 BitBrowser profile”，M7 处理 |
| 养号任务启动确认框 | 已显示浏览器环境 | 风险提示仍写“打开 BitBrowser profile”，M7 处理 |
| 目标号互动参与账号区域 | 已显示参与账号浏览器环境 | 无 M1 阻塞 |
| 目标号互动启动确认框 | 已显示浏览器环境 | 无 M1 阻塞 |
| 诊断页 | 点赞/评论诊断仍按 BitBrowser profile 过滤账号，文案也写 BitBrowser | M7 需接入账号级内置 Chromium 启动/CDP 诊断 UI |
| 设置页能力矩阵 | 已展示 provider capability matrix；默认 provider 选择仍包含 BitBrowser 和内置 Chromium | 默认值保持 BitBrowser；内置 Chromium 文案仍实验，M7 处理 |

## 默认 provider 与旧配置兼容性

- Runtime 默认：`src/browser_providers.py` 中 `DEFAULT_BROWSER_PROVIDER = BITBROWSER`。
- 平台配置默认：`src/platform_config.py` 中 `DEFAULT_BROWSER_PROVIDER = "bitbrowser"`。
- Tauri 配置默认：`desktop/src-tauri/src/commands/config.rs` 中 `DEFAULT_BROWSER_PROVIDER = "bitbrowser"`。
- 本地设置默认：`desktop/src-tauri/src/commands/config.rs` 的测试/默认路径中 `default_browser_provider: "bitbrowser"`。
- 旧账号兼容：账号缺少 `browser_provider` 时，后端按配置默认值解析；当前默认值为 BitBrowser。账号仅有 `bitbrowser_profile_id` 时，`bitbrowser_profile_id()` / `account_browser_profile_id()` 均能读取旧字段。

## 晋级为生产可选的验收清单

`builtin_chromium` 只有同时满足以下条件后，才能从 `experimental` 晋级为生产可选：

- M2 账号隔离通过：两个内置 Chromium 账号 user data dir、登录态、缓存、清理操作互不影响，升级或 runtime 重建不删除 user data dir。
- M3 代理与网络诊断通过：`http`、`https`、`socks5` 启动参数正确；格式错误能定位账号字段；代理密码在 UI、日志、支持包中脱敏；TikTok 网络错误可区分。
- M4 启动、CDP 与关闭稳定性通过：随机端口、启动前端口检查、`/json/version` 轮询、Patchright 连接前校验、失败诊断、PID 匹配关闭、残留处理均稳定。
- M5 TikTok 登录与人工接管通过：已登录检测、自动登录、验证码、二次验证、安全检查、人工继续流程均可回归；密码只经本机凭据和临时环境变量传递。
- M6 TikTok 任务回归通过：FYP 最小任务、目标号互动、水位线、点赞/评论/关注日志、BitBrowser 旧逻辑和混合队列均通过。
- M7 UI 与产品状态通过：所有展示面能追踪 provider，诊断页接入账号级内置 Chromium 检测，能力矩阵改为生产可选，UI 去除“实验”字样，同时设置页仍保留 BitBrowser 为默认推荐。
- M8 打包与跨电脑验收通过：安装包或依赖来源明确，新电脑无源码目录可运行，不依赖系统 Python，BitBrowser 默认行为仍正常，最终 validation 文档完成。

## M1 风险记录

- 后端运行记录当前为 `session.json`，设计文档写 `runtime.json`。M2 需要决定是迁移命名还是明确 `session.json` 为等价运行记录。
- `proxy_server_arg` 会生成包含代理密码的启动参数；M3 必须验证日志、命令展示和支持包不会泄漏该明文。
- `start_session` 启动失败时当前异常上下文不包含完整 account_id、provider、port、executable、user data dir、proxy 摘要；M4 需要补强。
- `close_session` 当前只按 session process_id 关闭，尚未校验 PID 与账号运行记录匹配；M4 需要补强。
- 诊断页没有暴露 `diagnose_account_browser`，也不能选择无 BitBrowser profile 的内置 Chromium 账号；M7 需要补齐。
