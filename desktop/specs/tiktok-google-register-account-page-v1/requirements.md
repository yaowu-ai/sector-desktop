# TikTok Google 注册入口 V1 Requirements

## 背景

当前【账号管理】页面同时承担账号配置、账号维护和任务启动职责。每个账号行的操作区包含运行养号任务按钮，批量操作区也包含“运行所选”。这会让账号管理页和【养号任务】、【目标号互动】页面的职责重叠。

新的产品方向是：

- 【账号管理】只负责账号资料、浏览器环境、登录/注册入口、执行日志查看和启停配置。
- FYP 养号任务集中在【养号任务】页面启动。
- 目标号互动集中在【目标号互动】页面启动。
- 每个账号行的原“运行任务”入口替换为“注册”入口，用于打开该账号对应浏览器环境并进入 TikTok Google 注册流程。

本 spec 覆盖【账号管理】页面入口与 TikTok Google 注册主流程。注册入口只从【账号管理】页面触发；养号执行仍集中在【养号任务】和【目标号互动】页面。

## 目标

- 从【账号管理】页面移除单账号运行养号入口。
- 从【账号管理】页面移除批量“运行所选”入口。
- 在每个账号的操作区新增“注册”按钮。
- 点击“注册”后，针对该账号打开对应浏览器环境并跳转到 `https://www.tiktok.com/login`。
- 注册入口使用该账号已有的浏览器 provider 配置，包括 BitBrowser profile 或内置 Chromium user data dir。
- 注册任务不自动执行养号、点赞、关注、评论或目标号互动。
- 注册任务的运行状态和输出仍复用现有运行输出/进程状态展示能力。
- 点击 TikTok 登录页的 `Continue with Google`。
- 在 Google 登录弹窗中填写【账号管理】里该账号对应的邮箱和密码。
- Google 登录完成后，在 TikTok 注册页随机选择生日。
- 在 TikTok 用户名页生成并提交 15 位英文字母数字随机用户名。
- 注册成功后保存该账号对应浏览器环境的 cookie/session，确保下次任务启动时不用重新登录。
- 自动注册流程成功完成后关闭该账号对应的浏览器。
- 自动注册逻辑应单独模块化，便于后续沿用于其他平台。

## 非目标

- 不在本阶段实现完整 TikTok Google 注册细节。
- 不自动绕过验证码、二次验证、安全检查、Google 风控或 TikTok 风控。
- 不改变【养号任务】页面现有 FYP 参数配置能力。
- 不改变【目标号互动】页面现有启动能力。
- 不改变调度计划页面的调度职责。
- 不迁移、删除或重写已有账号登录凭据存储模型。
- 不在【账号管理】页面保留任何单账号养号启动入口。

## 用户角色

- 运营人员：在账号列表中选择某个账号，点击“注册”，打开对应浏览器环境完成 TikTok 注册准备。
- 技术维护人员：维护注册任务命令、Google 注册流程自动化、日志和异常状态。

## 产品需求

### R1 账号管理页面职责收敛

【账号管理】页面不得再提供养号任务启动入口。

验收：

- Given 用户打开【账号管理】页面，Then 每个账号行不显示原来的播放/运行任务按钮。
- Given 用户选择多个账号，Then 批量操作区不显示“运行所选”按钮。
- Given 用户想启动 FYP 养号，Then 应通过【养号任务】页面启动。
- Given 用户想启动目标号互动，Then 应通过【目标号互动】页面启动。

### R2 每账号注册入口

每个账号行操作区必须提供一个“注册”按钮，用于启动该账号的 TikTok 注册流程。

验收：

- Given 账号存在且平台为 TikTok，When 用户点击该账号行“注册”，Then 应启动该账号注册任务。
- Given 账号使用 BitBrowser，Then 注册任务应打开该账号配置的 BitBrowser profile。
- Given 账号使用内置 Chromium，Then 注册任务应打开该账号配置的独立用户数据目录。
- Given 当前已有任务正在运行，Then 注册按钮应遵守现有单进程运行限制，并提示当前任务占用。

### R3 注册任务首步行为

注册任务启动后，必须打开 TikTok 登录页面作为注册流程入口。

验收：

- Given 注册任务成功启动，Then 浏览器应打开 `https://www.tiktok.com/login`。
- Given 浏览器环境打开失败，Then UI 应显示失败原因，并记录执行日志。
- Given TikTok 登录页加载失败，Then 任务应记录网络或页面加载错误。
- Given 页面打开成功，Then 任务应停留在 TikTok 登录/注册入口，等待后续 Google 注册流程继续处理。

### R4 Google 注册流程

系统必须按用户提供的步骤，使用 Google 账号完成 TikTok 注册主流程。

流程：

1. 打开该账号对应浏览器环境。
2. 打开 `https://www.tiktok.com/login`。
3. 在 TikTok 登录框中点击 `Continue with Google`。
4. 等待 Google 登录弹窗或新页面出现。
5. 在 Google `Email or phone` 输入框中输入【账号管理】里该账号的登录邮箱。
6. 点击 Google `Next`。
7. 等待 Google 密码页。
8. 在 Google `Enter your password` 输入框中输入【账号管理】里该账号保存的密码。
9. 点击 Google `Next`；如果按钮不可见，先向下滚动后再点击。
10. 等待 Google 登录回跳到 TikTok。
11. 在 TikTok 生日页随机选择 `Month`、`Day`、`Year`。
12. `Year` 必须选择 2006 年之前的年份。
13. 点击 TikTok 生日页 `Next`。
14. 在 TikTok 用户名页的 `Username` 输入框中输入 15 位随机用户名。
15. 用户名只能由英文字母和数字组成。
16. 用户名不能和本地已生成/已提交过的用户名重复。
17. 点击 `Sign up` 完成注册。

验收：

- Given TikTok 登录页显示 `Continue with Google`，When 用户点击账号行“注册”，Then 自动点击该按钮。
- Given Google 登录弹窗显示 `Email or phone`，Then 自动输入该账号在【账号管理】中配置的邮箱并点击 `Next`。
- Given Google 密码页显示 `Enter your password`，Then 自动输入该账号保存的密码并点击 `Next`。
- Given Google 密码页 `Next` 按钮当前不可见，Then 自动向下滚动后再次定位并点击。
- Given Google 登录完成并进入 TikTok 生日页，Then 自动随机选择生日，其中年份必须早于 2006 年。
- Given TikTok 进入用户名页，Then 自动生成 15 位英文字母数字用户名并填写。
- Given 生成的用户名已在本地注册记录中使用过，Then 重新生成直到不重复。
- Given 用户名填写完成，Then 自动点击 `Sign up`。
- Given Google 或 TikTok 出现验证码、二次验证、安全检查，Then 注册任务应能进入人工接管状态。
- Given 注册流程成功完成，Then 应记录注册完成状态，但不自动启动养号任务。

### R5 随机生日规则

生日必须自动随机生成，并满足 TikTok 注册年龄要求。

验收：

- Given 需要选择生日，Then `Month` 在 12 个月中随机选择。
- Given 需要选择生日，Then `Day` 根据所选月份和年份选择合法日期。
- Given 需要选择生日，Then `Year` 必须小于 2006。
- Given 同一批账号连续注册，Then 生日应分散随机，不固定同一天。

### R6 随机用户名规则

系统必须自动生成 TikTok 用户名。

验收：

- Given 进入用户名页，Then 生成 15 位用户名。
- Given 生成用户名，Then 只能包含 `A-Z`、`a-z`、`0-9`。
- Given 本地记录中已有相同用户名，Then 不使用该用户名。
- Given TikTok 页面提示用户名不可用，Then 最多重试生成并提交新用户名。
- Given 多次重试仍失败，Then 进入人工接管或返回明确错误。

### R7 状态、日志和脱敏

注册任务必须使用清晰的任务类型和日志动作，不与 FYP 养号混淆。

验收：

- Given 用户点击注册，Then 当前进程状态的 taskType 应能区分注册任务，例如 `tiktok_register`。
- Given 注册任务输出日志，Then 日志动作应使用注册相关名称，例如 `register_open_login`、`register_google_start`、`register_manual_required`、`register_ok`。
- Given 日志、运行输出或错误信息包含账号凭据，Then 必须脱敏或不输出。
- Given 注册任务结束，Then 执行记录可追踪账号 ID、任务类型、状态和时间。

### R8 Cookie / session 持久化

注册成功后，系统必须保存该账号的登录态，避免后续养号或目标号互动任务再次登录。

验收：

- Given TikTok 注册成功，Then 对应浏览器 profile 必须保留 TikTok cookie/session。
- Given 账号使用 BitBrowser，Then 登录态应保存在该 BitBrowser profile 中。
- Given 账号使用内置 Chromium，Then 登录态应保存在该账号独立 user data dir 中。
- Given 后续启动【养号任务】或【目标号互动】，Then 应优先复用该账号已保存的浏览器登录态。
- Given 系统需要额外导出 cookie/storage state，Then 必须加密保存，不得明文写入 `accounts.yaml`、日志或普通 JSON。
- Given cookie/session 保存失败，Then 注册任务不得标记为完全成功，并应返回明确错误。

### R9 注册完成后关闭浏览器

自动注册流程成功完成后，系统必须关闭本次由注册任务打开的对应浏览器环境。

验收：

- Given 注册成功并保存登录态，Then 自动关闭该账号对应浏览器窗口。
- Given 注册流程失败且不需要人工接管，Then 按现有自动关闭策略关闭浏览器并记录错误。
- Given 注册流程进入人工接管，Then 浏览器保持打开，直到用户完成接管、跳过或停止。
- Given 人工接管后用户继续并最终注册成功，Then 保存登录态后关闭浏览器。

### R10 注册逻辑模块化与复用

自动注册逻辑应单独模块化，方便后续复用于其他平台。

验收：

- Given 后续新增其他平台注册流程，Then 可以复用浏览器打开、凭据读取、cookie/session 持久化、人工接管、日志和关闭浏览器等通用逻辑。
- Given TikTok Google 注册流程变化，Then 只需要修改 TikTok 平台注册步骤和选择器。
- Given 其他平台注册流程不同，Then 可以新增平台专属 registration adapter，而不修改【账号管理】页面注册按钮主逻辑。

### R11 与集中任务页的关系

账号注册和养号执行必须分离。

验收：

- Given 注册成功，Then 系统不自动运行 FYP 养号。
- Given 注册成功，Then 用户仍需到【养号任务】或【目标号互动】页面启动后续任务。
- Given 账号未注册或未登录，Then【养号任务】页面仍按现有登录检测/自动登录逻辑处理，不依赖账号管理页运行入口。

## 完成定义

本功能完成时，【账号管理】页面中原单账号运行按钮和批量“运行所选”入口已移除；每个 TikTok 账号行提供“注册”按钮；点击后可启动该账号注册任务并打开 `https://www.tiktok.com/login`；注册成功后保存该账号的 cookie/session 并自动关闭对应浏览器；注册任务不会执行养号动作；FYP 养号和目标号互动只从对应任务页面集中启动。
