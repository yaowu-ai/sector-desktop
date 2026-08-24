# TikTok Google 注册入口 V1 Design

## 总体方案

本阶段只调整【账号管理】页面的任务入口职责：

```text
账号管理
  编辑账号
  保存登录凭据
  查看账号日志
  启用/停用账号
  启动单账号注册任务

养号任务
  启动 FYP 养号

目标号互动
  启动目标号互动
```

注册任务是一种独立 runtime 任务，不复用 FYP 养号启动按钮，不在账号管理页执行养号动作。

## 页面改动

### 账号行操作区

当前操作区包含：

- 编辑
- 运行
- 日志
- 删除

目标操作区：

- 编辑
- 注册
- 日志
- 删除

建议图标：

- 编辑：保持现有编辑图标。
- 注册：使用 `UserPlus`、`BadgePlus` 或语义接近的 lucide 图标。
- 日志：保持现有日志/文件图标。
- 删除：保持现有删除图标。

注册按钮 tooltip：

```text
打开该账号浏览器环境并进入 TikTok 注册
```

### 批量操作区

移除：

- `运行所选`

保留：

- 批量启用
- 批量停用

本 spec 不新增批量注册。原因是 Google/TikTok 注册流程高概率需要人工接管，批量注册容易造成多个浏览器窗口和多个验证码/风控状态并发，降低可控性。

## 前端状态设计

在 `AccountPage.tsx` 中，将单账号运行相关状态替换为注册相关状态。

建议命名：

```ts
const [registeringAccountId, setRegisteringAccountId] = useState<string | null>(null)
```

删除或停止使用：

```ts
runAccount(account)
runSelected()
runningAccountId === "selected"
selectedRunDisabledReason
```

新增：

```ts
registerAccount(account)
registerDisabledReason(account)
```

禁用条件：

- 当前已有进程运行。
- 账号未启用时可按产品决定是否允许注册。建议允许注册，因为注册是账号准备动作，不等同养号执行。
- 账号浏览器 provider 配置不完整时禁用，并给出 tooltip。
- 非 TikTok 平台账号禁用，或不显示注册入口。本项目当前账号管理按平台过滤，V1 可只对 TikTok 显示。

## API 设计

前端新增服务函数：

```ts
export function runTikTokRegister(accountId: string) {
  return invoke<ProcessStartResult>("run_tiktok_register", { accountId })
    .then(notifyProcessStarted)
}
```

如果希望复用通用平台任务命令，也可以扩展：

```ts
runPlatformTask({
  platform: "tiktok",
  taskType: "tiktok_register",
  mode: "single",
  accountIds: [account.id],
})
```

推荐优先使用独立命令或明确 taskType，避免和 `fyp`、`target_engagement` 混淆。

## Tauri 命令设计

新增命令：

```rust
#[tauri::command]
pub fn run_tiktok_register(
    run_state: State<'_, Arc<Mutex<RunState>>>,
    account_id: String,
) -> Result<ProcessStartResult, String>
```

职责：

1. 校验账号存在。
2. 校验账号平台为 TikTok。
3. 执行通用 preflight。
4. 使用该账号 browser provider 配置。
5. 启动 runtime 注册任务。
6. 设置 taskType 为 `tiktok_register`。
7. 复用现有进程状态、输出轮询、停止/暂停控制和脱敏逻辑。

命令参数不传 Google 密码或 TikTok 密码。后续 Google 注册细节需要凭据时，应沿用现有本机安全凭据/环境变量注入策略，且不得写入命令行参数。

## Runtime 设计

新增建议模块：

```text
src/platforms/tiktok/register.py
```

为便于后续复用于其他平台，建议同时抽出注册通用模块：

```text
src/platforms/registration/
  base.py              # RegistrationAdapter, RegistrationResult, common states
  browser_session.py   # open/close browser provider helpers
  credentials.py       # read secure account credentials for registration
  cookies.py           # persist/verify browser session state
  random_identity.py   # birthday and username helpers where reusable
  registry.py          # platform registration adapter lookup

src/platforms/tiktok/register.py
  TikTokGoogleRegistrationAdapter
  TikTok-specific selectors and steps
```

或在 TikTok runner 中新增独立任务分支：

```text
AM_TASK_TYPE=tiktok_register
```

推荐独立模块，减少和 FYP/目标号互动 runner 的耦合。

runtime 主流程：

```text
1. 读取 account_id。
2. 根据账号配置打开浏览器环境。
3. 连接 CDP。
4. 选择或创建页面。
5. page.goto("https://www.tiktok.com/login")。
6. 点击 TikTok 登录框里的 Continue with Google。
7. 等待 Google 登录弹窗或新 page。
8. 在 Google Email or phone 输入框中输入账号邮箱。
9. 点击 Google Next。
10. 在 Google 密码页输入账号保存的密码。
11. 点击 Google Next；如果按钮不可见，先滚动再点击。
12. 等待 Google 登录完成并回到 TikTok。
13. 在 TikTok 生日页随机选择 Month、Day、Year。
14. Year 必须选择 2006 年之前的年份。
15. 点击生日页 Next。
16. 在用户名页生成 15 位英文字母数字用户名。
17. 输入用户名并点击 Sign up。
18. 检测注册完成或人工接管状态。
19. 注册成功后持久化 cookie/session。
20. 关闭本次注册任务打开的对应浏览器。
```

建议函数拆分：

```text
open_tiktok_login_page()
click_continue_with_google()
wait_for_google_popup()
enter_google_email(email)
enter_google_password(password)
wait_for_tiktok_signup()
select_random_birthday()
generate_unique_username()
submit_tiktok_username()
detect_registration_complete()
persist_registration_session()
close_registration_browser()
detect_manual_intervention()
```

## 注册模块复用边界

适合抽成通用模块的能力：

- 根据 accountId 打开对应浏览器环境。
- 读取账号邮箱和本机安全保存的密码。
- taskType、日志、错误码和人工接管状态。
- 注册成功后的 cookie/session 持久化。
- 注册完成后的浏览器关闭策略。
- 随机生日、随机用户名等通用数据生成器。

必须保留在平台 adapter 中的能力：

- 平台页面 URL。
- 页面选择器。
- 点击路径。
- 注册完成判定。
- 平台特有风控和人工接管识别。

V1 推荐实现 TikTok adapter，同时建立通用 registration 基类。这样后续 Instagram、WhatsApp 或其他平台接入时，只新增 adapter，不需要改【账号管理】页面注册入口。

## 页面定位策略

TikTok 登录入口：

```text
button:has-text("Continue with Google")
[role="button"]:has-text("Continue with Google")
text=/Continue with Google/i
```

Google 邮箱页：

```text
input[type="email"]
input[autocomplete="username"]
input[aria-label*="Email" i]
text=/Email or phone/i
button:has-text("Next")
```

Google 密码页：

```text
input[type="password"]
input[autocomplete="current-password"]
input[aria-label*="password" i]
button:has-text("Next")
```

如果 `Next` 不可见：

```text
page.mouse.wheel(0, 600)
重新定位 Next
```

TikTok 生日页：

```text
text=/When's your birthday/i
button 或 combobox: Month
button 或 combobox: Day
button 或 combobox: Year
button:has-text("Next")
```

TikTok 用户名页：

```text
input[name="username"]
input[placeholder*="Username" i]
input[autocomplete="username"]
button:has-text("Sign up")
```

选择器必须集中维护在 TikTok register 模块中，不散落在页面启动代码里。

## 随机数据策略

### 生日

生日生成规则：

```text
year = random integer between 1985 and 2005
month = random month 1..12
day = valid day for month/year
```

说明：

- 年份必须早于 2006。
- 日期必须合法，二月需要考虑闰年。
- 不要求保存生日到 `accounts.yaml`，除非后续需要审计或复现。

### 用户名

用户名生成规则：

```text
alphabet = A-Z + a-z + 0-9
length = 15
```

本地去重：

- 在数据目录维护已生成用户名记录，例如 `data/tiktok_registered_usernames.json`。
- 生成前读取记录。
- 新用户名不在记录中才可使用。
- 注册成功或提交用户名后记录该用户名、account_id、时间。

TikTok 反馈不可用时：

- 重新生成用户名。
- 清空输入框。
- 再次提交。
- 默认最多重试 5 次。
- 超过重试次数后返回 `REGISTER_USERNAME_UNAVAILABLE` 或进入人工接管。

## 状态与事件

任务类型：

```text
tiktok_register
```

建议 action log：

```text
register_open
register_open_login
register_google_start
register_google_email
register_google_password
register_birthday
register_username
register_session_saved
register_browser_closed
register_manual_required
register_complete
register_error
```

人工接管事件可复用现有 auth intervention 机制，但事件 reason 应区分注册：

```text
google_captcha
google_mfa
tiktok_security_check
tiktok_terms_required
registration_unknown
```

## 错误处理

主要错误：

- `REGISTER_ACCOUNT_NOT_FOUND`
- `REGISTER_UNSUPPORTED_PLATFORM`
- `REGISTER_BROWSER_PROVIDER_INVALID`
- `REGISTER_BROWSER_OPEN_FAILED`
- `REGISTER_TIKTOK_LOGIN_LOAD_FAILED`
- `REGISTER_GOOGLE_POPUP_NOT_FOUND`
- `REGISTER_GOOGLE_EMAIL_FIELD_NOT_FOUND`
- `REGISTER_GOOGLE_PASSWORD_FIELD_NOT_FOUND`
- `REGISTER_GOOGLE_FLOW_BLOCKED`
- `REGISTER_TIKTOK_BIRTHDAY_FORM_NOT_FOUND`
- `REGISTER_USERNAME_FORM_NOT_FOUND`
- `REGISTER_USERNAME_UNAVAILABLE`
- `REGISTER_SESSION_SAVE_FAILED`
- `REGISTER_BROWSER_CLOSE_FAILED`
- `REGISTER_MANUAL_INTERVENTION_REQUIRED`

UI 展示原则：

- 错误说明要能指导用户下一步。
- 不输出密码、token、cookie、完整代理密码。
- 网络、代理、DNS、TikTok 页面加载错误应保留类别信息。

## 与现有页面的关系

### 养号任务页面

不需要为本 spec 做强制改动。该页面继续承接 FYP 启动。

### 目标号互动页面

不需要为本 spec 做强制改动。该页面继续承接目标号互动启动。

### 首页

本 spec 不要求修改首页。如果首页仍有快速启动任务入口，可以保留；本次只要求【账号管理】页面不再放运行养号任务功能。

## 安全与风控边界

- 不承诺自动通过 Google/TikTok 验证码。
- 不绕过平台风控。
- 不把注册流程和养号动作串联为自动闭环。
- 后续 Google 凭据输入必须复用安全凭据存储或用户人工输入，不写入日志和 YAML。
- cookie/session 属于敏感登录态；优先保存在对应浏览器 profile 中，不额外明文导出。

## Cookie / session 持久化设计

主要策略：

```text
BitBrowser account:
  TikTok cookie/session persists in the BitBrowser profile.

Builtin Chromium account:
  TikTok cookie/session persists in the account user data dir.
```

注册成功后要做一次登录态验证：

```text
1. 等待 TikTok 注册完成。
2. 打开或刷新 TikTok 首页/个人入口。
3. 使用登录态检测逻辑确认已登录。
4. 等待浏览器 profile 完成 cookie/session 写盘。
5. 记录 register_session_saved。
```

如果后续需要导出 `storage_state` 或 cookies：

- 必须加密保存到 data 目录。
- 不写入 `accounts.yaml`。
- 不写入 config backups。
- 不写入普通日志。
- 不在 UI 中展示 cookie 值。
- 默认不建议导出，除非浏览器 provider 不能稳定保存登录态。

## 浏览器关闭策略

注册任务打开的浏览器必须由注册任务负责关闭。

规则：

- 注册成功并确认 cookie/session 保存后，关闭对应浏览器。
- 注册失败且不需要人工接管时，按现有自动关闭策略关闭。
- 遇到验证码、二次验证、安全检查或需要人工选择时，保持浏览器打开并进入人工接管。
- 人工接管完成后，如果注册成功，保存 cookie/session 后关闭浏览器。
- 只关闭本次任务打开的浏览器环境，不关闭用户在任务外手动打开的其他窗口。

## 验证策略

前端验证：

- 账号管理行操作中不再出现运行按钮。
- 批量操作区不再出现“运行所选”。
- 注册按钮点击后调用注册 API。
- 注册按钮 loading 只作用于当前账号。
- 当前已有进程运行时注册入口禁用或提示占用。

后端验证：

- 注册命令能根据 accountId 打开正确 browser provider。
- 注册任务 taskType 与 FYP/target 区分。
- 打开 TikTok 登录页成功。
- 错误和日志脱敏。

人工验证：

- BitBrowser 账号点击注册后打开对应 profile。
- 内置 Chromium 账号点击注册后使用对应用户数据目录。
- 浏览器停留在 `https://www.tiktok.com/login`。
- 不发生点赞、关注、评论或目标号互动动作。
