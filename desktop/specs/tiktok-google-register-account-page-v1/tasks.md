# TikTok Google 注册入口 V1 Tasks

## M1 账号管理页面去运行化

- [x] 从 `AccountPage.tsx` 移除单账号 `runAccount` 处理函数。
- [x] 从账号行操作区移除原运行按钮。
- [x] 从批量操作区移除“运行所选”按钮。
- [x] 移除 `runSelected` 处理函数。
- [x] 移除只服务于账号管理页运行入口的 loading 状态。
- [x] 移除 `selectedRunDisabledReason` 或改为不再用于账号管理页。
- [x] 保留编辑、日志、删除、启用/停用能力。
- [x] 确认【养号任务】页面仍可启动 FYP。
- [x] 确认【目标号互动】页面仍可启动目标号互动。

## M2 账号管理页面新增注册入口

- [x] 在账号行操作区新增“注册”按钮。
- [x] 为注册按钮添加明确 tooltip：打开该账号浏览器环境并进入 TikTok 注册。
- [x] 使用合适图标，例如 `UserPlus`。
- [x] 新增 `registeringAccountId` loading 状态。
- [x] 点击注册时只让当前账号按钮进入 loading。
- [x] 注册按钮在当前已有进程运行时禁用或提示当前任务占用。
- [x] 注册按钮在账号浏览器配置不完整时禁用并显示原因。
- [x] 非 TikTok 平台账号不显示或禁用注册入口。

## M3 前端 API

- [x] 在 `desktop/src/services/api.ts` 新增 `runTikTokRegister(accountId)`。
- [x] API 调用成功后复用 `notifyProcessStarted`。
- [x] 在 `desktop/src/services/types.ts` 扩展任务类型，加入 `tiktok_register`。
- [x] 在账号管理页注册按钮点击后调用 `runTikTokRegister(account.id)`。
- [x] 成功提示使用注册语义，例如：`账号注册流程已启动，PID ...`。
- [x] 失败提示不包含敏感信息。

## M4 Tauri 命令

- [x] 在 Tauri commands 中新增 `run_tiktok_register`。
- [x] 在 `main.rs` 注册新命令。
- [x] 校验 accountId 存在。
- [x] 校验账号平台为 TikTok。
- [x] 校验 browser provider 配置可用于打开浏览器。
- [x] 复用现有进程单例限制。
- [x] taskType 设置为 `tiktok_register`。
- [x] 启动 runtime 时传入 accountId。
- [x] 不通过命令行参数传递密码或敏感凭据。
- [x] 注册任务输出进入现有运行输出面板。

## M5 Runtime 注册任务首版

- [x] 新增 TikTok 注册 runtime 入口。
- [x] 根据 accountId 加载账号配置。
- [x] 使用现有 BrowserProvider 打开对应浏览器环境。
- [x] 连接 CDP。
- [x] 选择当前 TikTok 页面或创建新页面。
- [x] 打开 `https://www.tiktok.com/login`。
- [x] 记录 `register_open_login` 日志。
- [x] 点击 TikTok 登录框里的 `Continue with Google`。
- [x] 等待 Google 登录弹窗或新页面。
- [x] 不执行 FYP 浏览、点赞、关注、评论或目标号互动。
- [x] 注册成功后必须进入 cookie/session 保存验证步骤。
- [x] 注册成功并保存登录态后自动关闭对应浏览器。
- [x] 注册需要人工接管时保持浏览器打开并等待用户处理。

## M6 注册通用模块抽象

- [x] 新增 `src/platforms/registration/base.py`。
- [x] 定义 `RegistrationAdapter` 接口。
- [x] 定义 `RegistrationResult` 结果结构。
- [x] 定义注册任务状态和稳定错误码。
- [x] 抽出浏览器打开/关闭通用 helper。
- [x] 抽出安全凭据读取 helper。
- [x] 抽出 cookie/session 持久化 helper。
- [x] 抽出人工接管事件 helper。
- [x] 抽出随机生日和随机用户名 helper。
- [x] 新增 registration adapter registry。
- [x] TikTok Google 注册实现放在 `src/platforms/tiktok/register.py`，只保留 TikTok 页面选择器和平台步骤。
- [x] 确认后续其他平台可新增 adapter 复用通用模块。

## M7 Google 登录流程

- [x] 实现 `click_continue_with_google()`。
- [x] 实现 `wait_for_google_popup()`，兼容 popup 和新 page。
- [x] 定位 Google `Email or phone` 输入框。
- [x] 输入【账号管理】里该账号的登录邮箱。
- [x] 点击 Google `Next`。
- [x] 等待 Google 密码页。
- [x] 定位 Google `Enter your password` 密码输入框。
- [x] 读取该账号本机安全存储中的保存密码。
- [x] 输入 Google 密码，但不输出到日志。
- [x] 点击 Google `Next`。
- [x] 如果 `Next` 不可见，先向下滚动再重新定位点击。
- [x] 等待 Google 登录完成并回跳 TikTok。
- [x] 检测 Google 验证码、二次验证、安全检查并进入人工接管。

## M8 TikTok 生日选择

- [x] 检测 TikTok `When's your birthday?` 页面。
- [x] 实现随机月份选择。
- [x] 实现随机日期选择。
- [x] 实现随机年份选择，年份必须小于 2006。
- [x] 确保日期合法，二月按闰年处理。
- [x] 点击生日页 `Next`。
- [x] 生日页定位失败时返回稳定错误码。

## M9 TikTok 用户名生成与提交

- [x] 检测 TikTok `Create username` 页面。
- [x] 实现 15 位英文字母数字随机用户名生成。
- [x] 用户名字符集限定为 `A-Z`、`a-z`、`0-9`。
- [x] 在 data 目录维护本地已生成用户名记录。
- [x] 生成前检查本地记录，避免重复。
- [x] 在 username 输入框中填写随机用户名。
- [x] 点击 `Sign up`。
- [x] 如果 TikTok 提示用户名不可用，重新生成并重试。
- [x] 默认最多重试 5 次。
- [x] 注册成功或用户名提交成功后记录 username、account_id、时间。
- [x] 重试耗尽后返回 `REGISTER_USERNAME_UNAVAILABLE` 或进入人工接管。

## M10 Cookie / session 保存

- [x] 注册完成后检测 TikTok 已登录状态。
- [x] BitBrowser 账号确认登录态留存在对应 BitBrowser profile。
- [x] 内置 Chromium 账号确认登录态留存在对应 user data dir。
- [x] 等待浏览器 profile 完成 cookie/session 写盘。
- [x] 记录 `register_session_saved`。
- [x] 如果需要导出 storage state，必须加密保存到 data 目录。
- [x] 禁止将 cookie/session 明文写入 `accounts.yaml`、日志、配置备份或普通 JSON。
- [x] cookie/session 保存失败时返回 `REGISTER_SESSION_SAVE_FAILED`。

## M11 浏览器关闭

- [x] 注册成功且 session 保存完成后关闭对应浏览器。
- [x] 关闭时只关闭本次注册任务打开的浏览器环境。
- [x] 不关闭任务外用户手动打开的其他窗口。
- [x] 注册失败且不需人工接管时按现有自动关闭策略关闭浏览器。
- [x] 人工接管中保持浏览器打开。
- [x] 人工接管完成并注册成功后保存 session 并关闭浏览器。
- [x] 关闭失败时记录 `REGISTER_BROWSER_CLOSE_FAILED`，但不得丢失注册成功状态。

## M12 日志与状态

- [x] action log 支持 `tiktok_register` 任务语义。
- [x] 注册打开浏览器时记录 `register_open`。
- [x] TikTok 登录页打开成功时记录 `register_open_login`。
- [x] Google 流程启动时记录 `register_google_start`。
- [x] Google 邮箱输入成功时记录 `register_google_email`，不得记录完整邮箱以外的敏感信息。
- [x] Google 密码输入阶段记录 `register_google_password`，不得记录密码。
- [x] 生日选择阶段记录 `register_birthday`，可只记录阶段成功，不强制记录具体生日。
- [x] 用户名提交阶段记录 `register_username`，可记录最终用户名。
- [x] cookie/session 保存成功时记录 `register_session_saved`。
- [x] 浏览器关闭成功时记录 `register_browser_closed`。
- [x] 人工接管时记录 `register_manual_required`。
- [x] 注册完成时记录 `register_complete`。
- [x] 注册失败时记录 `register_error` 和稳定错误码。
- [x] 确认日志脱敏覆盖密码、credential、proxy password、token、cookie、session。

## M13 UI 文案与导航一致性

- [x] 账号管理页标题/说明保持账号配置语义，不再暗示可运行养号任务。
- [x] 如页面说明中存在“运行 accounts.yaml 中的账号”，改为“读取、编辑、校验 accounts.yaml 中的账号”。
- [x] 运行输出面板标题可保留，或改为更中性的“任务输出”。
- [x] 注册按钮文案统一为“注册”。
- [x] FYP 启动提示引导用户去【养号任务】页面。
- [x] 目标号互动启动提示引导用户去【目标号互动】页面。

## M14 验收测试

- [x] 打开【账号管理】页面，确认每行没有运行按钮。
- [x] 选择多个账号，确认没有“运行所选”按钮。
- [x] 点击某个 TikTok 账号的“注册”，确认调用注册任务。
- [x] 注册任务启动后浏览器打开 `https://www.tiktok.com/login`。
- [x] TikTok 登录页自动点击 `Continue with Google`。
- [x] Google 弹窗自动填写【账号管理】中的邮箱。
- [x] Google 密码页自动填写保存密码。
- [x] Google 密码页 `Next` 不可见时能滚动后点击。
- [x] Google 登录完成后进入 TikTok 生日页。
- [x] TikTok 生日页自动选择随机生日，年份小于 2006。
- [x] TikTok 用户名页自动生成并填写 15 位英文字母数字用户名。
- [x] 本地已记录用户名不会被再次使用。
- [x] 用户名不可用时会重试生成新用户名。
- [x] 注册成功后对应浏览器 profile 保存 cookie/session。
- [x] 注册成功后关闭该账号对应浏览器。
- [x] 后续从【养号任务】启动该账号时不需要重新登录。
- [x] cookie/session 不会明文出现在 `accounts.yaml`、日志或配置备份中。
- [x] 注册通用模块和 TikTok 平台 adapter 分离。
- [x] BitBrowser 账号使用对应 BitBrowser profile。
- [x] 内置 Chromium 账号使用对应 user data dir。
- [x] 当前已有任务运行时，点击注册不能启动第二个冲突进程。
- [x] 注册任务不会产生 FYP 浏览、点赞、关注、评论动作。
- [x] 【养号任务】页面仍能启动 FYP。
- [x] 【目标号互动】页面仍能启动目标号互动。

## 建议实施顺序

1. 先改【账号管理】页面，移除运行入口并新增注册按钮外观。
2. 新增前端 API 和 Tauri 命令壳，先做到点击注册能启动 `tiktok_register`。
3. 新增 registration 通用模块和 TikTok adapter。
4. 新增 runtime 首版，只打开对应浏览器并跳转 TikTok 登录页。
5. 接入 TikTok `Continue with Google` 和 Google 邮箱/密码输入。
6. 接入 TikTok 生日选择和用户名生成提交。
7. 接入 cookie/session 保存验证和注册完成后关闭浏览器。
8. 接入日志、状态和错误处理。
9. 做 BitBrowser 与内置 Chromium 的手工验证。
10. 补充验证码、二次验证、安全检查人工接管分支。
