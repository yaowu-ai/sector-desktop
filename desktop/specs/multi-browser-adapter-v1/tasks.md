# Multi Browser Adapter V1 Tasks

## M1 Provider 基础

- [x] 抽象 `BrowserProvider`、`BrowserSession` 和 provider registry。
- [x] 保留 BitBrowser 为默认 provider。
- [x] 旧 `accounts.yaml` 缺少 provider 字段时继续按 BitBrowser 运行。
- [x] 完成 provider 能力矩阵。

## M2 BitBrowser Provider

- [x] 将现有 BitBrowser 打开、关闭、状态检测接入 provider。
- [x] 通过 BitBrowser Local API 获取 CDP endpoint。
- [x] 保持 TikTok 已登录 BitBrowser 账号原运行逻辑。
- [x] API 不可用时错误指向 Local API 地址。

## M3 UI 与诊断

- [x] 账号管理显示浏览器环境。
- [x] 系统设置显示 provider 能力矩阵。
- [x] 诊断入口支持按账号检查浏览器环境。
- [x] 养号任务和目标号互动显示当前账号浏览器环境。
- [x] 启动确认框显示本次运行账号的浏览器环境。

## M4 内置 Chromium 实验版

- [x] 实现 `builtin_chromium` provider。
- [x] 每个账号独立 user data dir。
- [x] 支持基础代理配置。
- [x] 支持启动、关闭和 CDP endpoint。
- [x] UI 明确标记实验。
- [x] 不替代 BitBrowser 作为 TikTok 生产默认。

## M5 验收

- [ ] 运行完整回归。
- [ ] 验证旧 BitBrowser 已登录账号仍按原逻辑运行。
- [ ] 验证内置 Chromium 账号可启动并获取 CDP endpoint。
- [ ] 验证任务日志和执行记录能追踪 provider。
- [ ] 验证密码不出现在配置、备份、命令行或日志。

## 完成标准

- 浏览器环境只保留 BitBrowser 和内置 Chromium。
- UI、配置模型、后端命令、Python runtime 和文档都不再暴露第三种 provider。
- TikTok 生产默认仍是 BitBrowser。
