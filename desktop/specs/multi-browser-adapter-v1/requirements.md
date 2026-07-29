# Multi Browser Adapter V1 Requirements

## 背景

Account Matrix 的 TikTok 任务需要通过统一浏览器适配层获取可连接的浏览器环境。当前目标只保留两种浏览器环境：

- `bitbrowser`：TikTok 生产默认方案，复用 BitBrowser Local API 和现有 `bitbrowser_profile_id`。
- `builtin_chromium`：内置 Chromium 方案，每个账号独立 user data dir，由应用启动、关闭并返回 CDP endpoint。

旧 `accounts.yaml` 不新增字段也必须继续按 BitBrowser 逻辑运行。

## 目标

- 抽象统一 `BrowserProvider` 接口。
- TikTok 任务启动统一通过 provider 获取 CDP endpoint。
- BitBrowser 仍是 TikTok 生产默认，不被内置 Chromium 替代。
- 内置 Chromium 作为用户可选浏览器环境。
- UI、诊断、任务确认框和执行账号区域只展示 BitBrowser 与内置 Chromium。

## 非目标

- 不实现第三方或用户自备 CDP endpoint 连接模式。
- 不在任务启动时临时切换账号浏览器环境。
- 不改变 TikTok 养号和目标号互动的业务动作策略。
- 不迁移 BitBrowser profile 到内置 Chromium。

## 功能要求

### R1 账号级浏览器环境

每个账号可以配置浏览器环境：

- BitBrowser
- 内置 Chromium

验收：

- 老账号缺少 `browser_provider` 时默认 BitBrowser。
- BitBrowser 账号继续支持 `bitbrowser_profile_id`。
- 内置 Chromium 账号写入 `browser_provider: builtin_chromium` 及对应 `browser` 配置。

### R2 Provider 能力矩阵

系统设置和诊断必须展示 provider 能力矩阵，仅包含 BitBrowser 和内置 Chromium。

验收：

- BitBrowser 标记为生产默认。
- 内置 Chromium 标记为实验或生产可选，取决于专项验收状态。
- 矩阵不展示任何第三种 CDP 高级模式。

### R3 任务执行

TikTok FYP 养号和目标号互动运行前必须通过 provider 启动或连接浏览器。

验收：

- BitBrowser provider 通过 Local API 打开 profile 并返回 CDP endpoint。
- 内置 Chromium provider 启动本地 Chromium 并返回 CDP endpoint。
- 任务确认框和执行账号区域展示当前账号浏览器环境。
- BitBrowser 已登录账号按原逻辑继续运行。

### R4 内置 Chromium

内置 Chromium 必须满足基础运行能力：

- 每个账号独立 user data dir。
- 支持基础代理参数。
- 支持启动、关闭和 CDP endpoint 检测。
- 关闭时只关闭应用启动并记录的进程。

### R5 安全与兼容

- 密码不写入配置、备份、命令行或日志。
- 日志中的代理密码等敏感信息必须脱敏。
- 旧 BitBrowser 配置可无感继续运行。

## 完成定义

- 代码和 UI 中只存在 BitBrowser、内置 Chromium 两个浏览器环境选项。
- 文档不再描述第三种浏览器 provider。
- Provider 能力矩阵和诊断入口完成。
- TikTok 生产默认仍为 BitBrowser。
