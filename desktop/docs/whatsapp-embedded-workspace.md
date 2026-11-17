# WhatsApp 网页嵌入

WhatsApp 业务仍属于 `h-wa-account-manager`，独立发布和运行。桌面端只负责导航、主题和连接状态，通过 iframe 加载该服务的 `/embed` 页面。没有复制账号、规则、任务或发送逻辑，也不经过 Account Matrix 的本地 Python 执行器。

## 配置真实服务

1. 发布包含嵌入适配的 `h-wa-account-manager` 版本。设置环境变量：

   ```dotenv
   HOSTED_EMBED_ORIGINS=tauri://localhost,http://tauri.localhost,https://tauri.localhost,http://127.0.0.1:1420,http://localhost:1420
   ```

   按实际桌面构建保留所需来源。未配置时 `/embed` 禁止访问。普通网页入口 `/` 继续禁止被嵌入。

2. 桌面前端可在构建时设置 `VITE_WHATSAPP_WORKSPACE_URL=https://your-wa-service.example.com`，或在 WhatsApp → 连接设置中输入站点地址。连接设置会显示当前 WebView 的实际来源，用于核对服务端白名单。
3. 启动桌面端，平台选择 WhatsApp。未启用统一登录时使用原养号服务组织账号；启用后，首次验证原 WA 邮箱和密码绑定，之后直接进入。桌面端不会向 iframe 传密码或长期访问令牌。统一登录配置见下方说明。

前端和服务端需一起发布；旧网页仍有禁止嵌入的响应头，桌面端会在 15 秒内显示重连和修改地址入口。反向代理也不能额外给 `/embed` 添加 `X-Frame-Options: DENY` 或 `frame-ancestors 'none'`。

## 导航和会话

- 总览、账号管理、养号任务、规则模板、执行记录、运行管理、经验分享、工作空间设置在原桌面导航中显示。
- 原网页侧栏在嵌入模式隐藏，保留空间切换、账号详情、扫码/配对弹窗、表单和原有业务权限。
- iframe 实例在页面与平台切换时保留，主题通过桥接同步。只有修改服务地址或重新连接才重新加载网页。
- 桥接传导航、主题、刷新、少量状态，以及统一登录使用的挑战和一次性票据；双方校验消息来源和窗口身份，不传桌面密码、accessToken、refreshToken 或业务数据。
- 为兼容限制第三方 Cookie 的桌面 WebView，WA 会话只保存在养号页面自身内存/sessionStorage，按父来源和每次桌面登录生成的随机上下文隔离；原 Cookie 的 `HttpOnly; SameSite=Strict` 策略保持。刷新中央 accessToken 保留上下文，退出或换号不恢复上一用户的上下文。
- 桌面退出会先发起 WA 会话撤销并立即清除 iframe 的本地令牌，最多等待3秒；网络失败时服务器会话仍按原12小时失效。请求晚返回时禁止重新写入旧 WA 或桌面登录状态。
- 原网页下载使用 iframe 的下载能力；系统文件选择和原网页弹窗继续由浏览器/WebView 处理。

## 本地交互 Demo

三个仓库 `account-matrix`、`h-wa-account-manager`、`h-sector` 保持当前并列目录；可用 `WA_MANAGER_ROOT` / `SECTOR_ROOT` 指定绝对路径。先在 h-sector 安装依赖并用隔离占位数据库地址执行 `prisma generate`（步骤见其 `docs/whatsapp-sso.md`）：

```sh
cd account-matrix/desktop
pnpm install --frozen-lockfile
pnpm demo:whatsapp
```

打开 `http://127.0.0.1:1420/demo.html`。WA 示例服务为 `127.0.0.1:8789`，直接读取原网页资源、Workspace 模型和 SSO 认证适配；`127.0.0.1:8790` 运行真实中央票据路由、Facade 和 Service。Redis/MySQL 使用明确的内存替身，桌面产品会话为假账号。不会启动 Worker 或连接真实 WhatsApp、Redis、MySQL。

桌面初始假用户为 `sector-operator`，首次绑定 WA 示例账号 `demo@account-matrix.local` / `DemoOnly2026!`；绑定后退出再登录会自动进入。右下角可切换到 `sector-observer`，绑定 `viewer@account-matrix.local` / `DemoOnly2026!` 后保留 WA 原观察员权限。也可“重置绑定演示”回到首次绑定流程。两边用户名不同，展示身份绑定而非密码同步。

已移除旧 Demo 注入 `/demo-session.js` 自动登录的方式。当前 Demo 会经过真实票据签发和兑换、WA 显式绑定流程，但仍不代表真实数据库/Redis或线上登录验收。生产构建不包含 Demo 入口和假账号。

可体验平台切换、账号搜索/详情/新增、任务检查/暂停、规则、记录、主题及刷新。未启用的操作会明确提示演示限制。Demo 是独立入口，生产 `vite build` 只打包 `index.html`，不会打包演示入口或原生桥接 mock。

## 验证

```sh
pnpm exec tsc --noEmit
pnpm exec vite build --mode test
node tests/whatsapp_workspace_checks.cjs
node tests/whatsapp_sso_checks.cjs
node tests/platform_boundary_checks.cjs
node tests/platform_stage2_checks.cjs
node tests/reserved_platform_modules_checks.cjs
node tests/platform_final_validation_checks.cjs
```

养号仓库运行：

```sh
node --test test/account-matrix-sso.test.cjs test/account-matrix-embed.test.cjs test/public-assets.test.cjs test/hosted-client.test.cjs test/hosted-origin.test.cjs
```

浏览器 Demo 验证不等于 Tauri 安装包、生产 MySQL、真实扫码和发送验收。正式接入后还需在目标 Windows/macOS WebView 与实际服务中验收登录保持、扫码、文件导入和下载。

### 2026-11-16 本地验收

- TypeScript 检查、Vite test 模式构建、5 个桌面平台/权限检查入口通过；生产前端产物确认不含 Demo 登录信息或 fixture 脚本。
- 养号侧嵌入策略、消息来源、会话传输、原站点防嵌入、资源缓存、原客户端与样式检查共 22 项通过。
- 原网页组织登录与刷新保持、账号详情、任务暂停、规则页、桌面与网页导航同步已操作检查。
- WhatsApp → TikTok → WhatsApp，以及系统页面往返，iframe 保持同一实例，观察到重载次数为 0；深色主题同步后，未提交账号名称仍保留。
- 错误地址显示连接失败提示；修改回正确地址后恢复连接。
- 桌面视口 1024×768、1280×820、1440×900 已截图测量。嵌入文档宽度分别为 816、1072、1232px，均无页面横向溢出；1024 下表格在自身容器内横向滚动。正文 14px、标题 20/28px、内容内距 24px；主按钮高度分别为 44/40/40px。没有发现字号缩放、导航重叠或主操作遮挡。以现有星域蓝色主题为参照，未提供单独 Figma 稿。
- 目标为桌面应用，沿用原窗口最小宽度 960px；不将手机尺寸作为本次桌面嵌入验收目标。

`modern-web-guidance` 的 `validate-origins` 指引用于桥接来源校验；考虑其说明 “Browser support for Origin: Limited availability.”，实现特性检测与 URL 解析回退，并拒绝不透明的 `null` 来源。

## 统一登录接入

- 中央后端是 `h-sector`，非旧规格中的仓库名。新增 `/api/desktop/whatsapp/ticket` 和仅供 WA 服务端使用的 `/api/desktop/whatsapp/exchange`；产品主体及当前订阅、设备、License 在签发和兑换时检查。
- 一次性票据60秒有效、Redis 原子消费，固定 WA 受众；WA 身份由受信中央服务器返回的 `issuer + subject` 确定。桌面只申请和传递票据，不声明 WA 用户、角色或空间权限。
- 两边配置和 WA 增量建表步骤分别见 `h-sector/docs/whatsapp-sso.md`、`h-wa-account-manager/docs/account-matrix-sso.md`。服务端兑换密钥不能出现在 `VITE_*` 配置。
- 已有 WA 用户只绑定、不迁移；没有 WA 用户或空间成员权限时走原组织邀请流程。身份绑定不等于全量实时中央会话吊销或统一管理全部 WA 权限。
- 本次代码在功能分支开发，未部署、未向线上数据库写入、未测试真实扫码或发送。

### 2026-11-16 统一登录追加验收

- 首次验证原 WA 凭据后完成绑定；错误密码被拒绝。桌面用户名与 WA 邮箱不同。
- 绑定后服务器示例会话数为1、绑定数为1；桌面退出后会话数为0、绑定仍为1；重新登录同一桌面用户后自动进入，会话恢复为1，不再要求 WA 密码。
- 使 WA 示例会话失效后手动刷新，观察到一个新的 SSO 挑战和已认证状态，自动续登成功。
- 切换另一桌面用户时不复用上一用户的 WA 会话。试图绑定已属于另一身份的 WA 账号被拒绝；绑定原观察员账号后保留只读权限，编辑和停止空间按钮隐藏。
- 返回运营员账号可免登并查看原任务。最终 Demo 为1440×900，导航高亮与任务内容一致；未发现页面横向溢出。
- 桌面 TypeScript、Vite test 构建、4项新增 SSO 测试和5个平台边界检查通过。h-sector TypeScript及17项认证/权限测试通过，WA 全量260项单元测试通过。
- 检查生产桌面入口产物，未包含 `DemoOnly2026!`、`demo-sector-*`、演示服务密钥或旧 `/demo-session.js`。
- 以上使用本机隔离存储替身。真实 MySQL/Redis、多副本、Windows/macOS 安装包及发布后的登录仍待联调。
