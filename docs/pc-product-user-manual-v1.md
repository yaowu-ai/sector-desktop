# Account Matrix PC 端产品使用手册 V1

版本：V1.8
日期：2026-08-04
适用对象：负责账号配置、浏览器环境维护、TikTok 自动登录、养号任务执行、调度巡检和数据查看的运营或技术人员。

## 1. 产品概述

Account Matrix PC 端是一个运行在 Windows 云电脑上的多平台、多账号操作台。它通过桌面界面包装内置运行时和现有 Python 自动化脚本，集中管理平台能力、账号配置、浏览器提供方、TikTok Google 自动登录、FYP 养号任务、目标号互动、定时调度、评论素材、执行记录、Session 日志、统计报表、Gmail 初始化、登录保障和诊断工具。

V1 的真实自动执行能力只支持 TikTok。Instagram、WhatsApp、抖音已在界面中预留账号、浏览器环境、任务、调度和统计入口，但自动执行按钮保持禁用，后端脚本也会过滤这些预留平台账号。

当前 TikTok 浏览器环境支持两种 provider：

- `bitbrowser`：生产默认方案，使用 BitBrowser Local API 和账号的 `bitbrowser_profile_id`。
- `builtin_chromium`：生产可选方案，内置的是 Account Matrix 的 Chromium 启动适配器，会用独立用户数据目录和临时 CDP 端口启动一个 Chromium 兼容浏览器。当前安装包没有随包携带完整 Chromium 浏览器本体，因此默认需要本机已安装 Chrome、Edge、Chromium，或在系统设置中手动指定可执行文件。它不等价替代 BitBrowser 的指纹环境能力，强指纹隔离场景仍优先使用 BitBrowser。

TikTok 任务启动后会先做登录态检测。已登录时继续执行；未登录且账号开启自动登录、凭据完整时，会优先进入 TikTok 登录页并尝试 Google 登录恢复；遇到验证码、二次验证或安全检查时会进入人工接管状态，等待运营在浏览器里处理后继续检测或跳过当前账号。

账号管理页提供 TikTok `自动登录` 入口，用于打开该账号的浏览器环境并进入 TikTok Google 登录流程。流程会打开 `https://www.tiktok.com/login`，点击 `Continue with Google`，读取账号管理中保存的 Google 登录邮箱和本机安全凭据中的密码，并在需要时继续处理 TikTok 生日和用户名页面。自动登录任务不会执行 FYP 浏览、点赞、关注、评论或目标号互动；完成并确认登录态后，登录状态保留在对应浏览器 profile 中。

当前 PC 端采用顶部全局平台选择器作为多平台主入口。左侧菜单不按平台拆分，也不再显示独立的 `平台管理` 菜单；平台能力、默认配置和 API / 环境说明通过顶部 `更多平台` 按钮进入。页面按作用域分为三类：

- 当前平台页面：账号管理、浏览器环境、养号任务、目标号互动、调度计划、评论素材、Gmail 初始化，会跟随顶部当前平台。
- 全平台页面：首页、执行记录、Session 日志、统计报表，默认展示全部平台，并提供平台筛选。
- 系统级页面：诊断工具、系统设置、平台设置，不会因为顶部平台切换而改变入口或默认过滤。

核心数据源：

- 账号和任务配置：`config/accounts.yaml`
- 普通评论池：`config/comments.txt`
- 品牌评论池：`config/comments_brand.txt`
- 执行动作数据库：`data/actions.db`
- 会话日志：`data/sessions.log`
- 运行互斥锁：`data/run.lock`
- 内置 Chromium 账号数据：`data/browser/builtin_chromium/<账号>/user-data`
- TikTok 注册用户名记录：`data/tiktok_registered_usernames.json`
- 自动登录人工接管标记：`data/auth_intervention/<账号>/`

## 2. 使用前准备

### 2.1 运行环境

PC 端建议只在云电脑上运行，不要在本机和云电脑同时打开同一个 BitBrowser profile。

运行前确认：

- Windows 云电脑可用。
- 生产默认使用 BitBrowser 时，BitBrowser 已安装并登录。
- BitBrowser Local API 已开启，默认地址为 `http://127.0.0.1:54345`。
- 使用内置 Chromium 时，本机需已有 Chrome、Edge 或 Chromium 可执行文件，或已在系统设置中填写 `Chromium 可执行文件`。当前安装包未携带完整 Chromium 浏览器本体；该模式可以脱离 BitBrowser，但不能脱离可用的 Chromium 兼容浏览器可执行文件。
- 每个生产账号使用独立浏览器环境。BitBrowser 账号绑定独立 profile 和代理 IP；内置 Chromium 账号使用独立 user data dir 和可选代理。
- 使用安装包运行时，不需要安装 Python，也不需要保留源码仓库。
- 若使用开发模式启动，Python 3.13、Node.js、pnpm、Rust、WebView2 和 Python 依赖需准备好。

### 2.2 启动方式

若已有安装包，直接启动桌面应用。安装版首次启动会自动创建用户目录：

- `%APPDATA%/Account Matrix/config/`：账号配置和评论池。
- `%APPDATA%/Account Matrix/settings/local-settings.json`：本机设置，默认 `runtimeMode` 为 `bundled`。
- `%LOCALAPPDATA%/Account Matrix/data/`：`actions.db`、`sessions.log` 和运行锁。
- `%LOCALAPPDATA%/Account Matrix/logs/`：诊断日志和支持包。

安装目录只保存应用、内置 runtime 和脱敏模板，不保存密码、真实账号运行数据、SQLite、日志、用户评论池或完整 Chromium 浏览器本体。

若使用开发环境，在仓库根目录运行启动脚本：

```powershell
cd E:\YAOWU\yangHao\account-matrix
.\desktop-dev.ps1
```

如果 PowerShell 提示脚本执行策略限制，使用：

```powershell
cd E:\YAOWU\yangHao\account-matrix
powershell -ExecutionPolicy Bypass -File .\desktop-dev.ps1
```

`desktop-dev.ps1` 会自动设置当前终端的 Rust/Cargo 环境变量，并进入 `desktop/` 执行 `corepack pnpm tauri dev`。

仅启动前端预览可运行：

```powershell
cd E:\YAOWU\yangHao\account-matrix\desktop
corepack pnpm dev
```

注意：只运行 `corepack pnpm dev` 时无法调用 Tauri 后端命令，不能读取配置、启动脚本或操作 BitBrowser。

若需要重新打包 Windows 安装程序，在仓库根目录运行：

```powershell
cd E:\YAOWU\yangHao\account-matrix
.\desktop-build.ps1
```

如果当前终端找不到 Windows `py` 启动器，但项目虚拟环境已存在，可指定运行时构建使用的 Python：

```powershell
cd E:\YAOWU\yangHao\account-matrix
.\desktop-build.ps1 -Python ".runtime-build-venv\Scripts\python.exe"
```

打包成功后，NSIS 安装包位于：

```text
desktop\src-tauri\target\release\bundle\nsis\Account Matrix_0.1.0_x64-setup.exe
```

2026-08-01 重新打包产物信息：

```text
文件：desktop\src-tauri\target\release\bundle\nsis\Account Matrix_0.1.0_x64-setup.exe
大小：44,136,713 bytes
SHA256：FAB8AC28DF36E05AADED9CE1C25E92B713A2F9439BC93F143DCBFDF836F004A2
runtime：account-matrix-runtime.exe 0.1.0
```

传输到云电脑后建议先比对文件大小或 SHA256。若安装时出现 NSIS integrity check failed，通常表示安装包下载或传输不完整，需要重新复制完整安装包。

不启动 PC 端应用时，也可以在项目根目录直接运行 TikTok Python 兼容入口：

```powershell
cd E:\YAOWU\yangHao\account-matrix
python src\main.py --platform tiktok
```

只运行单个账号：

```powershell
python src\main.py --account tiktok_106
```

如果直接运行 `python src\main.py`，脚本会读取默认 `config/accounts.yaml`，运行所有 enabled 且可执行的平台账号。V1 中真实可执行平台只有 TikTok；Instagram、WhatsApp、抖音会被统一 runner 识别为预留平台并跳过。

安装版内部使用 `account-matrix-runtime.exe` 运行任务。需要从命令行排查安装版 runtime 时，可在安装资源目录或运行时目录中使用同等子命令：

```powershell
account-matrix-runtime.exe version --json
account-matrix-runtime.exe diagnostic --config "%APPDATA%\Account Matrix\config\accounts.yaml" --data-dir "%LOCALAPPDATA%\Account Matrix\data" --json
account-matrix-runtime.exe run --platform tiktok --config "%APPDATA%\Account Matrix\config\accounts.yaml" --data-dir "%LOCALAPPDATA%\Account Matrix\data"
account-matrix-runtime.exe scheduler --host 127.0.0.1 --port 9601 --config "%APPDATA%\Account Matrix\config\accounts.yaml" --data-dir "%LOCALAPPDATA%\Account Matrix\data"
```

源码开发模式下也可以使用等价入口：

```powershell
python src\runtime_cli.py version --json
python src\runtime_cli.py diagnostic --json
python src\runtime_cli.py run --platform tiktok
```

正常通过 PC 端启动任务、调度、诊断或通知测试时，内置 runtime 会在后台运行，不会弹出独立黑色控制台窗口。只有手动在 PowerShell 或命令提示符中直接执行 `account-matrix-runtime.exe` 时，才会在当前终端显示输出。

### 2.3 首次检查

打开 PC 端后先看顶部状态栏：

- `BitBrowser API 在线`：说明 PC 端能访问 BitBrowser Local API。
- `BitBrowser API 不可用`：先打开 BitBrowser，确认 Local API 地址与系统设置一致。
- `当前任务空闲`：可以启动任务。
- `当前任务：running`：已有任务在运行，不要重复启动同类任务。

界面左侧菜单固定在窗口左侧，不会跟随页面内容滚动；点击左侧菜单切换页面时，右侧内容区域会自动回到页面顶部。`sessions.log` 不再展示在所有页面底部，请通过左侧 `Session 日志` 菜单集中查看。

## 3. 首页

首页用于日常快速查看多平台账号状态和启动当前可执行任务。

主要信息：

- `可执行启用账号`：当前可执行平台中的启用账号数量。V1 中等于 TikTok 启用账号数。
- `BitBrowser API`：BitBrowser Local API 是否在线。
- `今日计划任务`：调度器当天已排期数量。
- `今日完成账号`：当天成功完成的账号数。
- `今日失败账号`：当天失败账号数。
- `今日目标互动`：当天目标号互动数量。
- `平台账号概览`：按 TikTok、Instagram、WhatsApp、抖音展示账号总数、启用数和平台执行状态。

常用操作：

- `运行全部可执行账号`：启动所有当前可执行平台的启用账号执行任务。V1 中只会运行 TikTok 账号。
- 选择账号后点 `运行`：只运行单个账号。
- `启动调度服务`：启动 `src/scheduler.py`，按账号班次自动执行。
- `今日排期`：跳转到调度计划。
- `同步账号`：跳转到浏览器环境的账号同步。
- `评论池`：跳转到评论素材。

页面底部的 `脚本输出` 会显示当前任务的 PID、队列、已完成账号、命令、stdout、stderr。鼠标悬停在 `stdout` 或 `stderr` 标签上会显示含义说明：

- `stdout`：标准输出，程序正常输出的信息。
- `stderr`：标准错误，程序错误、警告或诊断信息。

`脚本输出` 同时提供：

- `暂停后续`：当前账号执行完后停止后续队列。
- `强制停止`：直接终止当前 Python 进程。仅在任务卡死时使用，日志和数据库记录可能不完整。

安装版从界面启动任务时，runtime 子进程会隐藏 Windows 控制台窗口。任务输出仍会被 PC 端捕获并展示在 `任务运行输出`、`执行记录` 和 `Session 日志` 中。

任务启动后，PC 端会监听运行时输出的浏览器预览事件。如果账号浏览器已打开并返回 CDP endpoint，页面会弹出 `浏览器预览`，持续显示当前账号浏览器画面。该预览只用于观察任务状态，不替代在真实浏览器窗口中的人工操作。

如果任务进入登录人工接管状态，`脚本输出` 会显示账号、登录状态和页面 URL，并提供：

- `我已完成，继续检测`：运营在浏览器里处理验证码、二次验证或安全检查后点击，运行时会重新检测登录态。
- `跳过当前账号`：放弃当前账号，继续后续队列。
- `停止任务`：终止当前批次。

## 4. 更多平台 / 平台设置

点击顶部 `更多平台` 进入平台设置页。该入口不放在左侧菜单中，用于查看平台能力矩阵、默认配置、自动执行状态和 API / 环境说明。

V1 状态：

- TikTok：已支持账号配置、浏览器环境、FYP 养号、目标号互动、调度运行、记录统计和真实自动执行。
- Instagram：已预留账号、浏览器环境、养号任务、目标号互动、调度和统计入口，自动执行入口禁用。
- WhatsApp：已预留账号、浏览器环境、养号任务、目标号互动、调度和统计入口，自动执行入口禁用。
- 抖音：已预留账号、浏览器环境、养号任务、目标号互动、调度和统计入口；现有 `src/douyin-fetcher` 暂不接入 PC 端自动执行。

使用原则：只有显示为可执行的平台账号可以启动任务。V1 中只有 TikTok 可执行；Instagram、WhatsApp、抖音可以维护账号和 profile，但不会作为生产自动化入口。

平台设置页包含：

- 能力矩阵：按账号配置、浏览器环境、养号任务、目标号互动、调度、评论素材、记录、统计、Gmail 初始化、诊断工具展示支持状态。
- 默认配置：查看 registry 中的平台默认配置。TikTok 有完整默认 FYP 和目标互动配置；预留平台当前为空配置或占位配置。
- API / 环境说明：每个平台以说明卡片展示接入状态、账号前缀、浏览器环境、执行入口和环境依赖。TikTok 的 `src/main.py`、`src/test_like.py`、`src/test_comment.py`、`src/scheduler.py` 是当前可用入口；预留平台显示为不可执行。

如果从旧地址或 hash 打开 `#platforms`，系统会进入同一个平台设置页。

## 5. 账号管理

账号管理用于维护 `config/accounts.yaml` 中的账号列表。

账号管理严格跟随顶部当前平台。切换顶部平台后，账号表只展示该平台账号；新增账号时会自动写入当前平台字段，并使用该平台账号前缀生成建议 ID。

### 5.1 查看账号

账号表包含：

- 账号 ID
- 平台
- 是否启用
- IP 分组
- 运行班次
- 浏览器环境
- 登录邮箱
- 登录状态
- BitBrowser `profile_id`
- profile 状态
- 最近执行时间
- 最近结果
- 备注

可以通过搜索框按账号、平台、profile、登录邮箱或备注搜索。

### 5.2 新增账号

点击 `新增账号`，填写：

- `账号 ID`：建议按平台前缀命名，例如 `tiktok_106`、`instagram_106`、`whatsapp_106`、`douyin_106`。
- `平台`：账号所属平台。当前页面会锁定为顶部当前平台，新增账号时自动写入该平台。
- `启用`：打开后该账号可被养号任务、目标号互动和调度使用；关闭后仅保留配置，不自动执行。
- `IP 分组`：同一代理 IP 的账号填写相同编号，用于调度冲突检查。
- `运行班次`：例如上午班 `[9, 12]`，晚上班 `[19, 23]`。
- `浏览器提供方`：默认 `BitBrowser`。可改为 `内置 Chromium`，但需要确认它是生产可选方案，不等价替代 BitBrowser 指纹环境能力。
- `BitBrowser 窗口 ID`：当浏览器提供方为 `BitBrowser` 时填写，对应 `bitbrowser_profile_id` 或 `browser.profile_id`。
- 如果本机没有安装 BitBrowser，且 BitBrowser API 当前不可用，表单中的 `下载 BitBrowser` 会通过系统默认浏览器打开 `https://www.bitbrowser.cn/download`。Windows 安装版会隐藏用于打开外部浏览器的临时控制台窗口。
- `代理协议`、`代理`、`用户数据目录`：当浏览器提供方为 `内置 Chromium` 时填写。代理支持 `http`、`https`、`socks5`；用户数据目录可留空，系统会自动使用 `data/browser/builtin_chromium/<账号>/user-data`。
- `自动登录`：开启后任务启动前会尝试保障平台登录态。
- `登录邮箱/用户名`：自动登录开启时必填，可填写邮箱、用户名或手机号。
- `登录密码`：只通过 `保存密码` 写入本机安全凭据存储，不写入 `accounts.yaml`。
- `备注`：记录 IP、班次、账号来源等说明。

保存后 PC 端会写回 `config/accounts.yaml`，并自动备份旧配置。

登录信息保存规则：

- `accounts.yaml` 只保存 `login.enabled`、`login.method`、`login.username` 和 `login.credential_ref`。
- 密码通过本机安全凭据存储保存，页面只显示凭据状态，不回显明文。
- Windows 版本使用当前 Windows 用户上下文的 DPAPI 加密凭据文件；macOS 构建使用系统 Keychain 保存同一 `credential_ref` 对应的密码。跨系统复制 `accounts.yaml` 时，需要在目标机器重新保存密码。
- 开启自动登录前必须先保存账号并保存密码，否则启动任务时会提示缺少凭据。
- `检查凭据` 只验证本机凭据是否存在且可读取；真实网页登录状态会在任务运行时检测。
- `删除密码` 会删除本机保存的凭据。Windows 版本会删除凭据文件；macOS 构建会同步删除 Keychain 中对应项目；该操作不删除账号配置。

### 5.3 编辑账号

账号表格右侧操作列显示小尺寸按钮。鼠标悬停在图标上会显示功能名称，例如 `编辑`、`自动登录`、`日志`、`删除`。点击编辑图标后，修改账号信息并保存。

常见修改：

- 临时停用账号：关闭 `启用`。
- 调整班次：修改 `active_hours`。
- 换 BitBrowser 窗口：更新 `BitBrowser profile_id`。
- 切换浏览器环境：在 `BitBrowser` 和 `内置 Chromium` 之间选择。旧账号缺少 `browser_provider` 时默认按 BitBrowser 处理。
- 更新自动登录：维护登录用户名、保存或删除本机密码。
- 清理内置 Chromium 数据：只删除该账号在 Account Matrix 内置 Chromium 下的 user data dir，不删除 BitBrowser profile。
- 共享 IP 错峰：同一 `ip_group` 的两个账号设置不同时间段。

### 5.4 TikTok Google 自动登录

账号管理页不再提供单账号养号运行按钮，也不再提供 `运行所选` 批量按钮。FYP 养号请进入 `养号任务`，目标号互动请进入 `目标号互动`。

TikTok 账号行会显示 `自动登录` 按钮，表格上方也提供 `批量自动登录`。点击后系统会：

1. 校验账号平台为 TikTok，且浏览器 provider 配置可用。
2. 复用当前任务单例限制；如果已有任务运行、暂停等待或人工接管中，会拒绝启动第二个自动登录任务。
3. 打开该账号对应的 BitBrowser profile 或内置 Chromium user data dir。
4. 进入 `https://www.tiktok.com/login`，点击 `Continue with Google`。
5. 使用账号管理中保存的登录邮箱和本机安全凭据中的密码完成 Google 登录。密码通过环境变量传给 runtime，不会进入命令行参数、日志或 `accounts.yaml`。
6. 如果账号首次进入 TikTok 注册补全流程，自动处理 TikTok `When's your birthday?` 页面，随机选择合法生日，年份小于 2006。页面选择器已兼容英文和中文生日页。
7. 如果出现 TikTok `Create username` 页面，自动生成 15 位英文字母数字用户名。系统会先检查 `data/tiktok_registered_usernames.json`，避免重复使用本地已记录用户名；如 TikTok 提示用户名不可用，默认最多重试 5 次。
8. 自动登录或注册补全成功并确认 TikTok 登录态后，等待浏览器 profile 写入 cookie/session，记录 `register_session_saved`，再关闭本次任务打开的浏览器环境。

如果 Google 验证码、二次验证、安全检查或 TikTok 页面状态无法自动完成，任务会进入人工接管。此时保持浏览器打开，运营在真实浏览器窗口中处理后，再回到任务输出面板点击 `我已完成，继续检测`。点击 `跳过当前账号` 会结束该账号自动登录流程并保留当前状态。

自动登录任务只用于创建或恢复登录态，不会执行 FYP 浏览、点赞、关注、评论或目标号互动。完成后，后续从 `养号任务` 或 `目标号互动` 启动同一账号时，会复用对应浏览器 profile 中保留的 TikTok 登录态。

自动登录过程中的主要动作日志包括：

- `login_google_start`
- `login_google`
- `register_open`
- `register_open_login`
- `register_google_start`
- `register_google_email`
- `register_google_password`
- `register_birthday`
- `register_username`
- `register_session_saved`
- `register_browser_closed`
- `register_complete`
- `register_manual_required`
- `register_error`

稳定错误码会出现在 `login_google` 或 `register_error` 详情中，例如 `REGISTER_GOOGLE_POPUP_NOT_FOUND`、`REGISTER_TIKTOK_BIRTHDAY_FORM_NOT_FOUND`、`REGISTER_USERNAME_UNAVAILABLE`、`REGISTER_SESSION_SAVE_FAILED`、`REGISTER_BROWSER_CLOSE_FAILED`。

### 5.5 查看账号日志

点击账号行的 `日志`，可查看该账号最近动作记录，包括时间、动作、状态和详情。

## 6. 浏览器环境

浏览器环境页面从 BitBrowser 单一管理升级为双 Provider 浏览器环境控制台。页面顶部展示三张状态卡：BitBrowser 状态（生产默认推荐）、内置 Chromium 状态（生产可选）和账号环境概览。页面按 Tab 分区：

- `BitBrowser Profile`：BitBrowser profile 列表和打开/关闭操作。
- `内置 Chromium`：Chromium 环境信息、内置 Chromium 账号列表、检测和清理。
- `账号绑定`：统一展示所有账号的浏览器提供方、环境标识和操作。
- `批量工具`：BitBrowser 单个创建、批量创建和账号环境同步。

浏览器 provider 区别：

- `BitBrowser`：通过 BitBrowser Local API 打开、关闭 profile，依赖 `bitbrowser_profile_id`，适合生产默认使用。
- `内置 Chromium`：通过 Chrome、Edge 或 Chromium 可执行文件启动独立账号环境，依赖 `browser.proxy`、`browser.user_data_dir` 和 Chromium 可执行文件路径。当前安装包没有随包携带完整 Chromium 浏览器本体，默认会自动查找本机 Chrome、Edge、Chromium；也可以在系统设置中手动指定一个独立 Chromium / Chrome for Testing 路径。该模式适合作为生产可选或专项验证使用，不等价替代 BitBrowser 指纹环境能力，强指纹隔离场景请继续优先使用 BitBrowser。

旧账号缺少 `browser_provider` 字段时，页面默认按 BitBrowser 展示和运行。

### 6.1 BitBrowser Profile

`BitBrowser Profile` Tab 展示当前平台下的 BitBrowser profile：

- profile 名称
- 窗口 ID，可复制
- 平台
- 是否打开
- 绑定账号
- 代理
- BitBrowser 分组 ID

可以对 BitBrowser profile 执行打开或关闭操作。执行任务前，通常不需要手动打开窗口，脚本会根据账号配置打开对应浏览器环境。

BitBrowser API 离线时，该 Tab 内会展示错误提示，但其他 Tab（内置 Chromium、账号绑定、批量工具）不受影响，仍可查看。

空态展示：`暂无 BitBrowser Profile。可通过批量工具创建并绑定账号。`

对于内置 Chromium 账号，不会在 BitBrowser profile 列表中生成窗口 ID。需要检查该账号环境时，请到 `内置 Chromium` Tab 或 `账号绑定` Tab 查看。

### 6.2 内置 Chromium

`内置 Chromium` Tab 展示 Chromium 启动能力和账号级环境信息。这里的“内置”指内置启动、隔离和清理能力；当前安装包未携带完整 Chromium 浏览器本体。

顶部展示 Chromium 环境信息：

- 可执行文件路径（可复制）。系统会按配置项、环境变量和本机默认安装目录查找。未检测到时展示 `未检测到可用 Chromium，请安装 Chrome/Edge 或手动指定可执行文件。`
- 数据根目录（可复制）。

表格按账号列出 `browserProvider=builtin_chromium` 的账号，每行展示：

- 账号
- 代理
- User Data Dir（截断展示，可复制）
- 运行状态
- 操作：`检测`、`复制路径`、`清理数据`

操作说明：

- `检测`：复用浏览器诊断能力，弹窗展示 provider 状态、Chromium 可执行文件、代理、用户数据目录和运行记录检查结果。
- `复制路径`：复制该账号 user data dir 到剪贴板。
- `清理数据`：删除该账号在内置 Chromium 下的 user data dir，复用 `cleanup_builtin_chromium_data`。清理前弹出二次确认，说明 `只会删除该账号在 Account Matrix 内置 Chromium 下的本地用户数据，不会删除 BitBrowser profile`。

内置 Chromium 账号为空时展示引导：`暂无内置 Chromium 账号。可在账号管理中将浏览器提供方设为内置 Chromium。`

### 6.3 账号绑定

`账号绑定` Tab 统一展示所有账号与浏览器环境的关系。

表格列：

- 账号
- 平台
- 浏览器提供方（BitBrowser 绿色 Tag / 内置 Chromium 金色 Tag）
- 环境标识：BitBrowser 账号显示 `profile_id`（可复制），缺少时标注 `待绑定`；内置 Chromium 账号显示 `user-data-dir`（可复制），不显示缺少 profile_id 的错误。
- 登录邮箱
- 代理
- 状态
- 操作：根据 provider 分流。BitBrowser 账号显示打开/关闭按钮；内置 Chromium 账号显示检测和清理按钮。

### 6.4 批量工具

`批量工具` Tab 集中 BitBrowser 创建和账号环境同步工具。

#### BitBrowser 单个创建

用于创建单个 BitBrowser profile。

填写：

- `窗口名称`：例如 `tiktok_26`、`instagram_26`、`whatsapp_26`、`douyin_26`。
- `代理协议`：支持 `socks5`、`http`、`https`。
- `代理`：格式为 `host:port:用户名:密码`。
- `BitBrowser 分组 ID`：可选。
- `跳过代理检测`：只在确认代理格式和可用性时使用。
- `允许复用已使用代理`：只在明确需要多个窗口共用同一代理时使用。

建议先点 `检测代理`，确认格式和复用状态，再点 `BitBrowser 创建 profile`。

#### BitBrowser 批量创建

用于按代理列表批量创建 profile。

填写：

- `窗口前缀`：例如 `tiktok`。
- `平台模板`：选择 TikTok、Instagram、WhatsApp 或抖音后，会自动带出建议窗口前缀。
- `代理协议`。
- `BitBrowser 分组 ID`：可选。
- `代理列表`：每行一个 `host:port:用户名:密码`。

`代理列表` 支持手动粘贴，也支持点击 `导入文件` 从本地导入。支持格式：

- `.txt`、`.log`：按文本读取，每行一个代理。
- `.csv`、`.tsv`：每行一个代理；如果一行拆成多列，会按 `:` 拼成 `host:port:用户名:密码`。
- `.xlsx`：按表格行读取；一行一个单元格时直接作为代理，多列时按 `:` 拼接。
- `.docx`：按段落提取文本，每段一行。

旧版二进制 `.doc`、`.xls` 暂不支持，请另存为 `.docx`、`.xlsx`、`.csv` 或 `.txt` 后再导入。空行和 `#` 开头的注释行会被忽略。创建结果会区分成功、跳过和失败。

#### 账号环境同步

账号环境同步用于把 BitBrowser profile 批量同步为账号配置。同步只处理 BitBrowser profile 绑定，内置 Chromium 账号无需创建 profile，同步预览中不会提示内置 Chromium 需要创建 profile。

填写：

- `窗口前缀`：例如 `tiktok`。
- `平台模板`：选择平台后自动带出建议窗口前缀，例如 `tiktok`、`instagram`、`whatsapp`、`douyin`。
- `起始`、`结束`：账号编号范围。
- `上午起`、`上午止`：上午班时间。
- `晚上起`、`晚上止`：晚上班时间。
- `首个 IP 组`：起始 IP 分组编号。

同步会按 BitBrowser 精确窗口名生成缺失账号并补齐 profile 绑定，例如 `tiktok_21`、`instagram_21`。先点 `dry-run`，确认将新增账号、已有账号、缺失 profile、重复 profile。确认无误后再 `apply`，写入前会备份 `accounts.yaml`。

### 6.5 内置 Chromium 账号数据

内置 Chromium 账号默认数据目录为：

```text
data/browser/builtin_chromium/<账号>/user-data
```

使用原则：

- 每个账号独立目录，不共用登录态、缓存和本地存储。
- 可在账号编辑中填写自定义 `用户数据目录`；相对路径会按 data 目录解析。
- 代理密码会在 UI、日志和支持包中脱敏。
- 任务异常退出后，系统会根据该账号的 runtime 记录处理残留进程或陈旧记录。
- 浏览器环境页面的 `清理数据` 或账号管理中的 `清理内置 Chromium 数据` 会终止匹配的应用启动进程、删除运行记录并移除该账号 user data dir。

清理前确认该账号没有正在运行的任务。清理操作不会删除 BitBrowser profile，也不会删除 `actions.db` 或 `sessions.log`。
## 7. 养号任务

养号任务页面严格跟随顶部当前平台。当前页面只作为 FYP 养号入口；TikTok FYP 可以真实执行，Instagram、WhatsApp、抖音会显示统一的不支持状态，启动按钮保持禁用。TikTok 目标号互动已独立放在 `目标号互动` 页面执行。

### 7.1 FYP 参数

可配置：

- `FYP 浏览时长范围（分钟）`：单次浏览时长区间。
- `点赞概率`：每个视频被点赞的概率。
- `每 session 关注数量范围`：单次执行关注数量范围。
- `评论开关`：是否启用评论。
- `每 session 评论数量范围`：单次评论数量范围。
- `评论概率`：命中候选视频后尝试评论的概率。
- `评论数门槛`：只对评论数大于该门槛的视频尝试评论。
- `评论池`：固定使用 `comments.txt`，内容从 `评论素材` 页面维护。

修改后点击 `保存配置`，会写入 `config/accounts.yaml`。

### 7.2 执行账号

可以选择单个账号或多个账号执行。账号选择列表只允许选择当前可执行平台的启用账号；预留平台账号会显示为未适配并禁用。页面会显示：

- 可执行账号数量。
- 本次 FYP 账号数量。
- 当前 FYP 配置摘要。

点击启动前会弹出确认框，确认任务类型、账号数量、执行账号、FYP 时长、点赞概率、关注数、评论参数和风险提示。

确认框和执行账号区域会显示账号浏览器环境。若账号使用 `内置 Chromium`，启动前会提示它是生产可选方案，并强调 BitBrowser 仍是默认推荐。

页面的 `可执行任务` 表当前只展示当前平台的 FYP 养号任务。预留平台不会出现在可执行任务列表中；即使直接调用后端 `run_platform_task`，后端也会校验 platform、capability 和 accountIds，拒绝未适配平台执行。

### 7.3 任务运行输出

页面下方的 `任务运行输出` 显示当前任务的实时 stdout 和 stderr：

- `stdout` 用于查看程序正常输出的信息。
- `stderr` 用于查看错误、警告或诊断信息。

鼠标悬停在 `stdout` 或 `stderr` 标签上会显示对应含义。完整会话日志请进入左侧菜单 `Session 日志` 查看。

任务运行前会执行 TikTok 登录保障流程：

1. 打开账号浏览器环境。
2. 进入 TikTok 页面并检测登录状态。
3. 已登录时继续 FYP。
4. 未登录且自动登录开启、凭据完整时，尝试打开 TikTok 登录页并执行 Google 登录恢复。
5. 遇到验证码、二次验证、安全检查或无法稳定判断的页面时，进入人工接管或跳过当前账号。

登录状态会写入执行记录中的 `login_check` 动作，也会写入 Session 日志；密码不会出现在 stdout、stderr、Session 日志或命令行参数中。

TikTok 自动登录任务也使用同一个 `任务运行输出` 面板。启动后任务类型显示为 `tiktok_register`，stdout/stderr、浏览器预览、人工接管按钮和停止按钮复用现有运行输出能力。自动登录任务的输出重点关注 `login_google*` 和 `register_*` 动作，不会产生 `fyp_browse`、`like`、`follow`、`comment` 或目标号互动记录。

如果自动登录任务进入人工接管，先在已打开的浏览器里处理 Google 验证、TikTok 安全检查或页面异常，再点击 `我已完成，继续检测`。如果不准备继续该账号登录，点击 `跳过当前账号`。人工接管期间不要手动关闭该账号浏览器，否则 runtime 无法继续保存 session。

点赞动作会验证点击后按钮状态是否变为已点赞。若点赞尝试没有成功，执行记录中的 `like fail` 会按原因拆分显示：

- `reason=button_not_found count=N`：未找到当前视频的点赞按钮，可能是页面结构变化、页面未聚焦或视频区域定位失败。
- `reason=already_liked count=N`：当前视频已经处于已点赞状态，系统不会重复点赞。
- `reason=state_unchanged count=N`：点击后按钮状态没有变为已点赞，常见于网络慢、点击被遮挡、账号互动受限或 TikTok 页面未及时更新状态。
- `reason=click_failed count=N`：模拟点击动作本身失败，常见于按钮不可见、坐标不可点击或页面切换中。

这些 `like fail` 不代表整个 session 失败。只要 `fyp_browse`、`session` 或 `close` 仍为 `ok`，说明本次浏览流程已完成，只是部分点赞尝试未成功。

## 8. 目标号互动

目标号互动严格跟随顶部当前平台，用于让当前平台的参与账号检查品牌目标号的新视频，并按概率点赞、评论和可选关注。V1 中只有 TikTok 可以执行真实目标号互动。

### 8.1 配置项

在 `目标号配置` 中填写：

- `启用`：打开后才能执行目标号互动。
- `评论池文件`：固定使用 `comments_brand.txt`。右侧 `导入` 按钮可选择本地 `.txt` 文件，系统会把内容写入项目内的品牌评论池 `config/comments_brand.txt`；文件名字段不再允许手动改成其他路径，评论内容从 `评论素材` 页面维护。
- `目标号 handles`：输入目标号用户名，支持带 `@` 或不带 `@`。
- `参与账号`：选择执行互动的可执行平台启用账号。V1 中只可选择 TikTok 账号。
- `首次运行处理最新视频数`：账号对目标号无历史记录时处理几条最新视频。
- `单次每目标最大视频数`：单次运行每个目标最多处理几条新视频。
- `点赞概率`：对新视频点赞的概率。
- `评论概率`：对新视频评论的概率。
- `关注目标号`：是否执行关注目标号。
- `关注概率`：遇到未关注目标号时执行关注的概率。

保存后配置写入 `config/accounts.yaml`。

### 8.2 立即执行

确认目标号互动已启用、目标号和参与账号不为空后，点击执行按钮。系统会先弹窗确认目标号、参与账号、单目标最大视频数、点赞概率、评论概率和关注策略。

### 8.3 水位线

水位线记录每个执行账号对每个目标号已经处理过的最大 `video_id`。只有 `video_id` 大于水位线的视频才会被视为新视频。

重置水位线会让系统重新建立处理起点。只在目标号配置错误、测试数据污染或明确需要重新检测时使用。

### 8.4 统计

页面展示：

- 按账号统计：每个执行账号处理的视频、点赞、评论、关注数量。
- 按目标号统计：每个目标号被处理的视频、点赞、评论、关注数量。

两张统计表支持横向滚动，字段较多或窗口较窄时可左右滑动查看完整列。

## 9. 调度计划

调度计划包装 `src/scheduler.py`，根据账号的 `active_hours` 和全局 `fires_per_day` 生成当天排期。当前只会把可执行平台账号纳入排期，V1 中即 TikTok 启用账号；预留平台账号即使启用也不会被 scheduler 排入真实任务。

### 9.1 启动和停止

操作：

- `启动调度`：启动调度服务。
- `停止调度`：停止后续排期，不等于立刻停止已经触发的账号任务。
- `刷新`：刷新调度服务、BitBrowser API、排期、任务锁、冲突状态和运行历史。

调度服务健康地址默认为 `http://127.0.0.1:9601/health`。

### 9.2 调度配置

`每账号每日触发次数` 对应 `fires_per_day`。例如 20 个可执行启用账号、`fires_per_day = 3`，当天预计排期为 60 次。V1 中可执行启用账号等于 TikTok 启用账号。

修改后点击 `保存配置`。保存账号或调度配置后，正在运行的调度器会在约 10 秒内自动重建剩余排期；如果检测到旧版本、健康检查接口异常或配置路径不一致的调度进程，再停止并重新启动调度服务。

### 9.3 账号班次与 IP 分组

表格可修改每个账号的：

- `参与调度`
- `IP 分组`
- `活跃时段`

同一 `ip_group` 代表共用同一代理 IP。推荐同 IP 账号错峰，例如一个上午班 `[9, 12]`，一个晚上班 `[19, 23]`。

页面会检测同 `ip_group` 班次是否重叠：

- `未检测到同 ip_group 班次重叠`：配置正常。
- `检测到同 ip_group 班次冲突`：先调整班次再启动调度。

### 9.4 当前任务和运行历史

调度页会按顶部当前平台展示：

- `当前任务`：当前平台内已经排期的 job，包含任务 ID、账号、下次执行时间和状态。状态会显示为 `已排期`、`运行中`、`已暂停` 或 `异常`。
- `运行历史`：最近 1 天或 3 天的调度执行记录，包含任务 ID、账号、运行开始时间、运行结束时间、运行结果和运行详情。

运行结果会显示为 `未运行`、`运行中`、`成功运行`、`运行失败`。失败、跳过或未运行的记录会展示详情，成功记录默认不展开详情。

### 9.5 run.lock

`run.lock` 用于防止手动任务和调度任务同时运行。

状态说明：

- `无`：没有锁。
- `存在但 PID 不活跃`：可能是上次异常退出遗留，可确认无任务运行后清理。
- `活跃`：有任务正在运行，不要清理。

`清理任务锁` 只在确认没有养号脚本运行时使用。活跃 PID 锁会被后端拒绝。

## 10. 评论素材

评论素材页面严格跟随顶部当前平台。切换顶部平台后，会读取并保存该平台对应的评论池配置。TikTok 继续兼容旧全局评论文件：

- 普通评论池：`config/comments.txt`
- 品牌评论池：`config/comments_brand.txt`

其他预留平台默认使用平台维度评论文件，例如：

- Instagram：`config/comments_instagram.txt`、`config/comments_instagram_brand.txt`
- WhatsApp：`config/comments_whatsapp.txt`、`config/comments_whatsapp_brand.txt`
- 抖音：`config/comments_douyin.txt`、`config/comments_douyin_brand.txt`

保存评论素材时，PC 端会把文件名写入 `platforms.<platform>.comments`。旧 TikTok 配置仍会按兼容规则归属到 `platforms.tiktok.comments`。

每行一条评论。空行和 `#` 开头行会被识别为非有效评论。

操作：

- `新增`：添加单条评论。新增行会插入到当前评论池第一条，并自动切回第 1 页，方便立即编辑。
- `批量粘贴`：每行粘贴一条评论。
- `删除`：删除某条评论。
- `恢复`：放弃当前未保存修改。
- `保存`：写入文件，并生成备份。

页面会显示有效评论数、重复项、原注释行、原空行和文件路径。保存前建议处理明显重复项。

## 11. 执行记录

执行记录读取 `data/actions.db`，默认展示全部平台视角。

如果页面提示 `actions.db 尚未创建`，说明还没有成功运行过养号任务。运行一次任务后数据库会自动创建。

可筛选：

- 平台：默认 `全部平台`，可切换 TikTok、Instagram、WhatsApp、抖音。
- 账号
- 动作
- 状态
- 时间范围

包含三个页签：

- `动作记录`：普通养号动作，例如 `fyp_browse`、`like`、`follow`、`comment`。
- `目标互动`：目标号视频互动记录，包括执行账号、目标号、`video_id`、是否点赞、是否评论。
- `目标关注`：目标号关注记录。

详情字段支持复制，方便排查失败原因。

点赞失败会在详情字段中显示原因，例如 `reason=button_not_found count=1`、`reason=already_liked count=2`、`reason=state_unchanged count=3` 或 `reason=click_failed count=1`。目标号互动中的 `target_like fail` 也会带 `reason=...`，用于判断是找不到按钮、已点赞、点击未生效还是点击动作失败。

## 12. Session 日志

`Session 日志` 页面集中展示 `data/sessions.log` 的原始运行日志，不再在每个页面底部重复展示。新日志行包含 platform 字段，页面默认展示全部平台，并可按平台、账号、任务类型、关键词和时间范围筛选。

页面包含：

- `重新读取`：从文件开头重新读取当前 `sessions.log` 内容。
- `清空日志`：清空 `sessions.log` 文件内容。该操作不会删除 `data/actions.db` 中的执行记录。
- `sessions.log` 卡片：自适应右侧内容区域高度，日志内容在卡片内部滚动，并按固定间隔增量读取新内容。

`sessions.log` 适合查看批次启动、批次结束、账号运行摘要和脚本级错误。结构化查询、筛选和复制详情请使用 `执行记录` 页面。

## 13. 统计报表

统计报表用于汇总普通养号和目标号互动数据。

筛选范围：

- 平台：默认 `全部平台`，可切换 TikTok、Instagram、WhatsApp、抖音。
- 全部
- 今天
- 最近若干天
- 自定义时间范围

主要指标：

- 账号数
- OK
- ERR
- SKIP
- 普通视频
- 目标视频

报表区域：

- `普通养号统计`：按账号汇总普通 FYP 浏览、点赞、关注、评论等数据。
- `目标号按账号统计`：按执行账号汇总目标互动。
- `目标号按目标号统计`：按目标号汇总互动效果。

目标号相关统计表支持横向滚动，字段较多时可左右滑动查看完整列。

点击 `导出 CSV` 可导出当前筛选范围内的统计数据。若当前筛选范围没有数据，导出会被拒绝并提示。

## 14. Gmail 初始化

Gmail 初始化包装 `gmail_setup.py`，用于打开 BitBrowser 窗口并辅助完成 Google 登录、条款确认和密码处理流程。

### 14.1 单账号

填写：

- `BitBrowser 窗口名称`：例如 `tiktok_25`。
- `Google 邮箱`：为空时只打开 Google 登录页。
- `当前密码`：通过环境变量传给脚本，不进入命令行参数。
- `新密码`：为空时脚本按自身默认策略处理。
- `搜索词`：默认 `gmail`。
- `页面超时（秒）`。
- `条款页超时（秒）`。

点击 `启动` 后确认信息，再启动脚本。

### 14.2 批量文件

填写：

- `起始 BitBrowser 窗口名称`：例如 `tiktok_25`，后续窗口名自动递增。
- `邮箱文件`：每行格式为 `账号----密码----备注`。
- `失败时保留窗口`：遇到失败是否保留窗口便于人工检查。
- `搜索词`、页面超时、条款页超时。

密码从邮箱文件读取，日志不展示密码。

### 14.3 运行状态

运行状态会显示：

- 任务类型
- 状态
- PID
- 开始时间
- 结束时间

如果检测到额外验证、人工检查、Workspace 条款或 challenge，页面会提示 `需要人工处理`。此时请在 BitBrowser 当前窗口完成验证或检查页面状态，再根据日志决定是否重试。

## 15. 诊断工具

诊断工具用于排查浏览器环境、点赞动作和评论动作是否可用。当前诊断脚本只接入 TikTok；预留平台会显示诊断脚本未接入。

### 15.1 浏览器环境诊断

选择 TikTok 启用账号后点击 `运行环境诊断`。系统会根据账号的浏览器提供方检查：

- `accountConfig`：账号配置是否满足浏览器提供方要求。
- `providerStatus`：BitBrowser API 或 Chromium 可执行文件是否可用。
- `proxyConfig`：内置 Chromium 账号的代理格式和脱敏结果。
- `proxyConnectivity`：内置 Chromium 账号代理主机和端口是否可连。
- `userDataDir`：内置 Chromium 账号用户数据目录是否存在、可读、可写。
- `runtimeRecord`：内置 Chromium 账号是否已有运行记录、PID、端口和 CDP endpoint。
- `cdpEndpoint`：已有内置 Chromium 运行记录是否还能访问 CDP。

BitBrowser 账号重点检查 `profile_id` 和 Local API；内置 Chromium 账号重点检查 Chromium 可执行文件、代理、用户数据目录和运行记录。

诊断结果面板会用中文展示主要状态：

- `空闲`：当前没有诊断任务。
- `启动中` / `运行中`：诊断脚本正在启动或执行。
- `已完成`：诊断任务已结束。
- `失败` / `部分失败` / `已停止`：诊断任务未完整完成，需要查看下方脚本输出。
- 浏览器环境检查中的 `正常`、`警告`、`异常` 分别对应检查通过、存在风险和检查失败。

安装版 runtime 诊断还会检查 Patchright driver 启动能力：

- `patchrightDriver`：验证内置 Patchright Node driver 是否能启动并保持等待协议连接。正常时会显示 `driver stayed alive`。
- `patchrightStartup`：验证 Patchright sync API 是否能完整启动并拿到 Chromium browser type。

如果这两项失败，优先复制诊断详情排查。常见原因包括安装包传输不完整、安全软件拦截 `node.exe`、云电脑权限策略限制子进程管道、或 Windows 长路径前缀导致 Node 入口脚本解析失败。

### 15.2 点赞诊断

选择 TikTok 启用账号后运行。脚本会验证点赞动作是否能执行，并在输出中显示过程和结果。

诊断摘要会展示：

- `策略`：当前测试的点击策略。
- `结果`：`状态已变化` 表示点击后点赞状态发生变化，`无变化` 表示点击未改变页面状态。
- `点击`：点击动作的执行结果。
- `点击前` / `点击后`：点赞按钮在点击前后的状态。

### 15.3 评论诊断

选择 TikTok 启用账号后填写：

- `评论数阈值`：候选视频评论数阈值。对应脚本内部参数 `min_comments`。
- `最大滚动次数`：最多滚动多少次寻找候选视频。对应脚本内部参数 `max_scroll`。
- `只定位不发布`：开启后只定位评论入口，不实际发布测试评论。

若关闭 `只定位不发布`，启动前会二次确认，因为脚本会尝试发布内置测试评论。

评论诊断摘要会展示：

- `扫描视频数`：本次扫描过的视频数量。
- `最高评论数`：扫描结果中的最高评论数。
- `评论输入框`：是否已输出评论输入框 HTML。
- `发布按钮`：是否已输出评论发布按钮 HTML。
- 明细表中的 `视频序号` 和 `评论数`：对应脚本扫描到的视频顺序和评论数。

脚本 stdout / stderr 中仍可能出现 `comment-input`、`post button`、`comment_count`、`--no-post` 等英文关键字，这些是底层诊断脚本和日志解析标记；PC 端摘要和表单会以中文显示。

## 16. 系统设置

系统设置用于调整 PC 端运行路径、运行模式、浏览器 provider、BitBrowser API、Chromium、日志轮询和通知。

### 16.1 运行环境

页面顶部会展示 `浏览器提供方能力矩阵`：

- `BitBrowser`：已实现、稳定、生产默认，提供 CDP endpoint，支持 TikTok。
- `内置 Chromium`：已实现、生产可选，提供 CDP endpoint，支持 TikTok；当前安装包内置启动适配器但未携带完整 Chromium 浏览器本体，仍需要本机 Chrome/Edge/Chromium 或手动指定可执行文件，且不等价替代 BitBrowser 的指纹环境能力。

可配置：

- `运行模式`：安装版默认 `内置运行时`；开发调试可切换为 `源码开发模式`。
- `项目根目录`
- `Python 可执行文件`：默认可用 `py`，也可填绝对路径。
- `默认浏览器提供方`：支持 `BitBrowser` 和 `内置 Chromium`。建议生产默认保持 `BitBrowser`，只对明确需要的账号单独切到内置 Chromium。
- `Chromium 可执行文件`：仅内置 Chromium 使用，可填写 Chrome、Edge、Chromium 或 Chrome for Testing 的 `exe` 路径。留空时系统会自动查找本机常见安装位置；找不到时内置 Chromium 账号无法启动。
- `BitBrowser API 地址`
- `data 目录`
- `accounts.yaml 路径`
- `comments.txt 路径`
- `comments_brand.txt 路径`
- `任务结束自动关闭 profile`
- `日志轮询间隔`

保存后刷新页面，确认当前生效路径是否正确。

系统设置右侧会显示当前设置文件、运行模式、运行时清单、运行时版本和初始化应用版本。安装版应优先保持 `内置运行时`；只有需要直接调试源码时才切到 `源码开发模式`。

### 16.2 通知

通知默认关闭。支持：

- ServerChan
- Bark
- Webhook

配置后可点击 `发送测试` 验证。

### 16.3 危险操作

`清空 sessions.log` 会清理会话日志。该操作不会删除 `actions.db`，但会影响 `Session 日志` 页面中的原始日志回溯。

这些危险操作只影响本地运行环境，不会删除 BitBrowser profile，也不会删除内置 Chromium 账号的 user data dir。清理内置 Chromium 数据请在账号管理中按账号执行。

### 16.4 多平台配置迁移

系统设置页提供 `多平台配置迁移` 工具，用于把旧 TikTok 配置迁移到新的多平台结构。

迁移内容包括：

- 缺少 `platform` 的老账号显式写入 `platform: tiktok`。
- 旧 `defaults.daily_actions` 复制到 `platforms.tiktok.warmup`。
- 旧 `target_accounts` 复制到 `platforms.tiktok.target_engagement`。
- 旧 `comments.txt` / `comments_brand.txt` 归属到 `platforms.tiktok.comments`。
- 旧 `actions.db` 中 `action_log`、`target_engagements`、`target_follows` 的空 platform 记录补为 `tiktok`。

使用方式：

1. 点击 `刷新预览`，查看哪些项目仍需迁移。
2. 若显示 `需要迁移`，点击 `应用迁移`。
3. 系统会先备份 `accounts.yaml` 和 `actions.db`，再写入新结构。
4. 迁移后旧结构仍保留兼容读取，但后续保存会优先写入平台维度。

## 17. 日常操作流程

日常操作流程按平台能力分为两类：当前多平台预留形态下的操作流程，以及后续多个平台都接入真实自动执行后的通用流程。

### 17.1 当前多平台预留形态下的操作流程

当前版本已经可以维护 TikTok、Instagram、WhatsApp、抖音的平台结构、账号和 BitBrowser profile。只有 TikTok 可以启动真实养号、目标号互动和调度任务；其他平台只作为预留入口，不会被脚本真实执行。

#### 17.1.1 新增一批平台账号

1. 默认生产方案下，在 BitBrowser 中准备 profile 和代理，或在 `浏览器环境` 中批量创建 profile。
2. 进入 `浏览器环境 > 批量创建`，选择 `平台模板`，确认窗口前缀，例如 `tiktok`、`instagram`、`whatsapp`、`douyin`。
3. 进入 `浏览器环境 > 账号同步`，选择 `平台模板`，填写窗口前缀、编号范围、班次和 IP 组。
4. 点击 `预览同步`，确认新增账号、已有账号、缺失 profile 和重复 profile。
5. 应用同步，写入 `config/accounts.yaml`。
6. 进入 `账号管理`，按平台筛选检查账号启用状态、浏览器环境、profile_id、IP 分组和班次。
7. 如需使用内置 Chromium，只对明确验证过的 TikTok 账号把 `浏览器提供方` 改为 `内置 Chromium`，并配置代理或自定义用户数据目录。
8. 如需自动登录，先保存账号，再保存登录密码，并确认凭据状态正常。
9. 对新 TikTok 账号，先在账号管理中点击 `自动登录` 完成 TikTok Google 登录或首次注册补全，并保存登录态。
10. 自动登录成功后，进入 `养号任务` 先选择 1 个账号执行单账号 FYP，确认日志、浏览器预览和登录检测正常，再小批量运行。
11. 对 Instagram、WhatsApp、抖音账号，只维护配置、profile 和备注，不启动生产任务。

#### 17.1.2 TikTok Google 自动登录

1. 确认顶部当前任务为空闲。若账号使用 BitBrowser，顶部需显示 `BitBrowser API 在线`。
2. 进入 `账号管理`，确认顶部当前平台为 TikTok。
3. 检查该账号的浏览器环境。BitBrowser 账号需要绑定正确的 `profile_id`；内置 Chromium 账号需要可用 Chromium 可执行文件和独立 user data dir。
4. 检查该账号的 `登录邮箱/用户名` 和本机保存密码状态。自动登录流程会用这些凭据登录 Google。
5. 点击账号行的 `自动登录`，或勾选多个 TikTok 账号后点击 `批量自动登录`。
6. 观察 `任务运行输出` 和 `浏览器预览`。正常流程会依次打开 TikTok 登录页、点击 `Continue with Google`、填写 Google 邮箱和密码，并在需要时回到 TikTok 注册补全页。
7. 如出现 Google 验证码、二次验证、安全检查或 TikTok 页面异常，保持浏览器打开，在浏览器里完成处理后点击 `我已完成，继续检测`。
8. 如果进入首次注册补全流程，系统会自动选择生日、生成用户名并提交。用户名记录保存在 `data/tiktok_registered_usernames.json`，避免本地重复。
9. 自动登录完成后，系统会确认 TikTok 已登录，等待 profile 写入 cookie/session，记录 `register_session_saved`，再关闭本次任务打开的浏览器环境。
10. 完成后进入 `执行记录` 或账号行 `日志`，查看 `login_google`、`register_complete`、`register_username`、`register_session_saved` 等动作是否为 `ok`。

自动登录任务不会做养号动作。不要把自动登录入口当作 FYP 或目标号互动入口；自动登录完成后的账号再从 `养号任务` 或 `目标号互动` 页面启动后续任务。

#### 17.1.3 手动执行 TikTok 养号

1. 确认当前任务为空闲。若执行账号包含 BitBrowser provider，顶部需显示 `BitBrowser API 在线`。
2. 进入 `养号任务`，检查 FYP 参数。
3. 在执行账号区域选择 `全部可执行平台账号`、单账号或多账号。V1 中可执行平台账号只包含 TikTok。
4. 检查账号浏览器环境；内置 Chromium 账号会触发生产可选提示。
5. 点击 `启动 FYP 养号` 并确认任务摘要。
6. 观察 `任务运行输出` 和 `浏览器预览`；如出现登录人工接管，先在浏览器里完成验证，再点 `我已完成，继续检测`。
7. 需要查看完整批次日志时进入 `Session 日志`。
8. 完成后进入 `执行记录` 或 `统计报表` 查看结果。

#### 17.1.4 查看预留平台能力

1. 点击顶部 `更多平台`，进入平台设置页查看 TikTok、Instagram、WhatsApp、抖音的能力矩阵。
2. 切换到 Instagram、WhatsApp、抖音后进入 `养号任务`、`目标号互动` 或 `调度计划`，页面会显示该平台暂不支持自动执行。
3. 对 Instagram、WhatsApp、抖音，只维护账号和 profile；不要把这些平台当作可执行任务入口。
4. 若预留平台账号已启用，`运行全部可执行账号` 和 scheduler 仍只会运行 TikTok，不会执行预留平台。

#### 17.1.5 启动 TikTok 自动调度

1. 进入 `调度计划`。
2. 检查任务锁和同 IP 班次冲突；如果 TikTok 队列中有 BitBrowser 账号，也要检查 `BitBrowser API`。
3. 设置 `fires_per_day`。
4. 检查 TikTok 账号的 `ip_group` 和 `active_hours`。
5. 点击 `保存配置`。
6. 点击 `启动调度`。
7. 查看 `当前 Jobs` 和下一次执行时间。V1 中 Jobs 只会包含 TikTok 账号。

#### 17.1.6 更新 TikTok 目标号互动

1. 进入 `评论素材`，维护品牌评论池。
2. 进入 `目标号互动`，填写 TikTok 目标号 handles 和参与账号。
3. 设置首次处理数量、单次最大视频数、点赞概率、评论概率和关注策略。
4. 保存配置。
5. 先小范围立即执行。
6. 查看水位线、按账号统计和按目标号统计。

### 17.2 多个平台都接入真实执行后的操作流程

当系统后续支持 TikTok、Instagram、WhatsApp、抖音等多个平台的真实自动执行能力后，日常操作先按平台拆分，再在每个平台内部执行账号、任务和调度流程。

#### 17.2.1 确认平台能力

1. 点击顶部 `更多平台`，进入平台设置页确认目标平台的能力状态。
2. 只对显示为已适配、可执行的平台启动自动化任务。
3. 对仍处于预留状态的平台，只维护账号、profile 和备注，不启动生产任务。

#### 17.2.2 新增多平台账号

1. 按平台在 BitBrowser 中准备 profile 和代理，例如 TikTok、Instagram、WhatsApp、抖音分别使用清晰的窗口前缀。
2. 进入 `浏览器环境 > 账号同步`，按平台分别选择 `平台模板`，填写窗口前缀、编号范围、班次和 IP 组。
3. 点击 `预览同步`，确认新增账号、已有账号、缺失 profile 和重复 profile。
4. 应用同步后进入 `账号管理`，按平台筛选检查账号配置。
5. 确认每个账号的平台、profile_id、启用状态、IP 分组、班次和备注。

#### 17.2.3 分平台配置任务

1. 进入对应平台的任务配置页面。
2. 配置该平台独立的浏览、互动、评论、关注或消息参数。
3. 维护对应平台的评论素材、目标号或联系人列表。
4. 保存配置后，先选择该平台 1 个账号做单账号验证。
5. 验证日志和执行记录正常后，再扩大到小批量账号。

#### 17.2.4 分平台手动执行

1. 确认顶部 `BitBrowser API 在线`，且没有冲突任务正在运行。
2. 进入对应平台的任务页面。
3. 只选择同一平台下的启用账号。
4. 点击执行并确认任务摘要，重点检查平台、账号数、任务类型和风险提示。
5. 观察任务输出；完成后进入 `执行记录` 或 `统计报表` 按平台筛选结果。

#### 17.2.5 分平台启动调度

1. 进入 `调度计划`。
2. 按平台检查账号班次、IP 分组和每日触发次数。
3. 避免同一 `ip_group` 下不同平台账号在同一时间段同时运行。
4. 保存调度配置。
5. 启动调度后查看各平台 `当前 Jobs` 和下一次执行时间。
6. 通过 `Session 日志` 和 `统计报表` 持续观察各平台执行情况。

#### 17.2.6 多平台运行后的复盘

1. 进入 `执行记录`，按平台、账号、动作和时间范围筛选失败记录。
2. 进入 `统计报表`，分别查看各平台账号产出和异常比例。
3. 对失败率高的平台，先暂停该平台调度，再检查 profile、代理、登录状态和任务参数。
4. 调整后先单账号验证，再恢复小批量和自动调度。

## 18. 常见问题处理

### 18.1 BitBrowser API 不可用

处理步骤：

1. 确认 BitBrowser 已启动。
2. 确认 BitBrowser Local API 已开启。
3. 进入 `系统设置`，确认 API 地址是 `http://127.0.0.1:54345` 或实际地址。
4. 点击顶部 `刷新`。
5. 如果本机尚未安装 BitBrowser，可在账号管理新增或编辑账号时点击 `下载 BitBrowser`，系统会用默认浏览器打开官方下载页。

### 18.2 启动任务失败

优先查看：

- 顶部当前任务状态。
- `任务运行输出` 的 stderr。
- `Session 日志` 页面中的 `sessions.log`。
- `系统设置` 中 Python 可执行文件是否正确。
- `config/accounts.yaml` 是否存在配置错误。

### 18.3 profile 打不开

检查：

- `BitBrowser profile_id` 是否正确。
- 该 profile 是否已经在其他机器打开。
- BitBrowser 是否登录当前账号。
- 代理是否可用。

如果账号使用 `内置 Chromium`，检查：

- 系统设置中的 `Chromium 可执行文件` 是否存在；若留空，确认本机是否安装 Chrome、Edge 或 Chromium。
- 账号代理格式是否为 `host:port` 或 `host:port:用户名:密码`。
- `data/browser/builtin_chromium/<账号>/user-data` 是否可读写。
- 诊断工具中的 `runtimeRecord` 是否显示残留 PID 或不可访问的 CDP endpoint。
- 必要时在账号管理中执行 `清理内置 Chromium 数据` 后重新登录和验证。

### 18.4 调度没有执行

检查：

- 调度服务是否 running。
- 当前时间是否在账号 `active_hours` 内。
- `fires_per_day` 是否大于 0。
- 任务锁是否被活跃 PID 持有。
- BitBrowser API 是否在线。
- 同 `ip_group` 班次是否冲突。

### 18.5 统计为空

可能原因：

- 还没有运行过任务。
- `data/actions.db` 不存在。
- 当前筛选时间范围没有数据。
- 任务失败，没有写入有效动作记录。

### 18.6 Gmail 初始化需要人工处理

出现额外验证、Workspace 条款、challenge 或页面卡住时：

1. 保持 BitBrowser 当前窗口不要关闭。
2. 按页面提示完成验证或人工检查。
3. 回到 PC 端查看步骤日志。
4. 根据日志决定继续等待或重新启动该账号初始化。

### 18.7 自动登录没有继续执行

检查：

- 账号管理中 `自动登录` 是否开启。
- `登录邮箱/用户名` 是否填写。
- `凭据状态` 是否为已保存且可读取。
- 任务输出中是否出现 `captcha`、`mfa`、`security_check` 或 `unknown`。
- 如果出现人工接管，请在浏览器里完成验证后点击 `我已完成，继续检测`；不想继续该账号时点击 `跳过当前账号`。

自动登录不会绕过验证码、二次验证或平台安全检查，也不会读取短信或邮箱验证码。

### 18.8 运行时或诊断异常

检查：

- 系统设置中的 `运行模式` 是否符合当前场景。安装版一般使用 `内置运行时`，源码调试使用 `源码开发模式`。
- `运行时清单` 是否存在，且支持 `run`、`scheduler`、`gmail`、`diagnostic`、`version`。
- 可在命令行运行 `account-matrix-runtime.exe version --json` 或 `python src\runtime_cli.py version --json` 检查版本。
- 可运行 `diagnostic --json` 查看配置路径、data 目录、评论池、浏览器 provider 能力、`patchrightDriver`、`patchrightStartup` 和账号浏览器诊断结果。

### 18.9 启动任务时弹出黑色控制台窗口

旧安装包中，启动任务、调度、诊断或通知测试时可能会弹出标题为 `account-matrix-runtime.exe` 的黑色控制台窗口。该窗口不是任务错误，而是 Windows 显示了 runtime 子进程控制台。

处理方式：

1. 更新到 2026-08-01 或之后的安装包。
2. 通过 PC 端按钮启动任务，不要手动双击 `account-matrix-runtime.exe`。
3. 若仍弹出黑框，确认正在运行的是新安装包，并在系统设置中保持 `运行模式` 为 `内置运行时`。

新安装包会在 Tauri 后台启动 runtime，并隐藏控制台窗口；stdout 和 stderr 仍会进入 PC 端任务输出与日志。

### 18.10 点赞失败如何判断

执行记录中出现 `like fail` 时，先看详情中的 `reason`：

- `button_not_found`：优先检查 TikTok 页面是否正常加载、浏览器窗口是否被遮挡、页面结构是否变化。
- `already_liked`：通常无需处理，说明候选视频已经点过赞。
- `state_unchanged`：优先检查网络、代理质量、账号互动限制和页面是否响应；可降低点赞概率或换账号验证。
- `click_failed`：优先检查云电脑分辨率、缩放比例、浏览器窗口是否可见，以及页面是否正在切换。

如果 `fyp_browse ok` 且 `close ok`，但只有少量 `like fail`，一般不需要重跑整批任务。若连续多次全部为 `button_not_found` 或 `state_unchanged`，再使用诊断工具运行点赞诊断并查看浏览器画面。

### 18.11 TikTok 自动登录没有完成

先看账号行日志或 `执行记录` 中的 `login_google`、`register_error` 详情：

- `REGISTER_GOOGLE_POPUP_NOT_FOUND`：TikTok 登录页没有稳定打开 Google 弹窗。检查页面是否加载完成、是否被弹窗策略拦截、是否已经停在其他登录方式页面。
- `REGISTER_GOOGLE_EMAIL_FIELD_NOT_FOUND` 或 `REGISTER_GOOGLE_PASSWORD_FIELD_NOT_FOUND`：Google 登录页结构异常、网络慢或账号被安全检查拦截。建议查看浏览器画面，必要时人工接管。
- `REGISTER_GOOGLE_FLOW_BLOCKED`：Google `Next`、密码页或回跳流程被阻塞。常见于二次验证、安全检查、页面加载慢。
- `REGISTER_TIKTOK_BIRTHDAY_FORM_NOT_FOUND`：TikTok 生日页选择器定位失败或页面结构变化。先人工确认页面是否仍是生日页。
- `REGISTER_USERNAME_UNAVAILABLE`：连续 5 次随机用户名都被 TikTok 判定不可用。可重新启动自动登录任务，系统会重新生成用户名。
- `REGISTER_SESSION_SAVE_FAILED`：登录或注册补全后无法确认或等待浏览器 profile 写入 session。检查浏览器是否被手动关闭、user data dir 是否可写。
- `REGISTER_BROWSER_CLOSE_FAILED`：自动登录成功但关闭浏览器失败。登录状态不会因此丢失；确认没有其他用户窗口被误关，再手动关闭对应 profile 或稍后重试。

如果任务进入 `register_manual_required` 或登录人工接管状态，不要关闭浏览器。先在浏览器里完成验证码、二次验证、安全检查或页面确认，再回到 PC 端点击 `我已完成，继续检测`。如果该账号暂不继续登录，点击 `跳过当前账号`。

## 19. 操作注意事项

- 同一个 BitBrowser profile 同一时间只能在一台机器打开。
- 批量任务运行时不要手动关闭正在执行的 profile。
- TikTok 自动登录人工接管期间不要手动关闭正在处理的 profile，否则可能无法保存 session。
- 内置 Chromium 账号运行时不要手动删除其 user data dir 或 runtime 记录。
- 不确认任务已停止时，不要清理任务锁。
- 修改调度配置后，正在运行的调度器会自动重建剩余排期；如果健康检查异常、配置路径不一致或旧版本进程未重载，再停止并重新启动调度服务。
- 目标号互动建议先小范围验证，再扩大参与账号。
- 评论素材尽量避免大量重复、过短或明显模板化。
- 自动登录密码只通过本机安全凭据存储维护，不要写入 `accounts.yaml`、备注或评论素材文件。
- 凭据只保证在当前操作系统用户上下文内可读。更换云电脑、Windows 用户或迁移到 macOS 后，需要重新保存账号密码。
- TikTok 自动登录不会把 cookie/session 明文写入 `accounts.yaml`、日志、配置备份或普通 JSON；如后续需要导出 storage state，必须先加密后再保存到 data 目录。
- TikTok 自动登录入口只负责登录、首次注册补全和保存登录态；FYP 养号、点赞、关注、评论和目标号互动必须从对应任务页面启动。
- V1 仅 TikTok 支持真实自动执行，其他平台不要作为生产任务入口。
