# 内置 Chromium 生产可选方案 V1 Requirements

## 背景

Account Matrix 当前只保留两种浏览器环境：

- `bitbrowser`：TikTok 生产默认 provider。
- `builtin_chromium`：内置 Chromium provider，每个账号独立 user data dir，支持基础代理、启动、关闭和 CDP endpoint。

本 spec 的目标是定义内置 Chromium 从“实验”走向“生产可选”的专项验收路径。验收通过前，BitBrowser 仍是 TikTok 生产默认；验收通过后，用户可以主动选择内置 Chromium，但默认值仍不替代 BitBrowser。

## 目标

- 保持 TikTok 生产默认 provider 为 BitBrowser。
- 允许用户按账号选择 BitBrowser 或内置 Chromium。
- 验证内置 Chromium 在 TikTok FYP 养号和目标号互动中的完整流程。
- 增强内置 Chromium 的代理检测、启动诊断、异常恢复和日志可读性。
- 确保每个账号独立 user data dir，不串登录态、不串缓存。
- 任务页、确认框、执行记录和诊断中都能看到账号使用的浏览器环境。

## 非目标

- 不实现完整浏览器指纹系统。
- 不承诺内置 Chromium 与 BitBrowser 的指纹隔离能力等价。
- 不自动迁移 BitBrowser profile 到内置 Chromium。
- 不把任务启动时的浏览器环境做成临时随意切换。
- 不改变 TikTok 养号动作策略、点赞概率、关注策略或目标号水位线逻辑。

## 功能要求

### R1 账号级浏览器环境选择

账号管理必须允许每个 TikTok 账号选择：

- BitBrowser
- 内置 Chromium

验收：

- 新增账号默认使用 BitBrowser。
- 选择内置 Chromium 后，账号配置写入 `browser_provider: builtin_chromium`。
- 老账号只有 `bitbrowser_profile_id` 时仍显示为 BitBrowser。

### R2 内置 Chromium 独立账号环境

默认目录：

```text
<data_dir>/browser/builtin_chromium/<account_id>/user-data
```

验收：

- 两个内置 Chromium 账号 user data dir 不相同。
- 账号 A 登录态不会被账号 B 复用。
- 清理账号 A 的浏览器数据只删除账号 A 对应目录。

### R3 代理能力

内置 Chromium 支持基础代理：

- `http`
- `https`
- `socks5`

验收：

- 启动参数包含正确代理。
- 代理格式错误时提示账号和字段。
- 代理密码在 UI、日志和支持包中脱敏。

### R4 启动、关闭和异常恢复

验收：

- 启动后返回可连接 CDP endpoint。
- `auto_close_profile=true` 时只关闭应用本次启动的 Chromium。
- 端口冲突、executable 缺失、user data dir 不可写时错误信息可定位。
- 异常中断后下次运行可处理残留运行记录。

### R5 TikTok 登录与人工接管

验收：

- 已登录内置 Chromium 账号返回 `logged_in` 并继续任务。
- 未登录且配置自动登录时可自动填写账号密码并提交。
- 遇到验证码、二次验证或安全检查时暂停并提示人工处理。
- 密码只通过本机安全凭据存储和临时环境变量传递。

### R6 TikTok 任务回归

验收：

- 内置 Chromium 账号可完成 FYP 养号最小任务。
- 目标号互动可打开目标主页、读取新视频并按配置互动。
- 无新视频时正常跳过并记录水位线。
- 旧 BitBrowser 已登录账号仍按原逻辑运行。

### R7 UI 与诊断

验收：

- 账号列表显示浏览器环境、登录邮箱和登录状态。
- 养号任务执行账号区域显示账号浏览器环境。
- 目标号互动参与账号区域显示账号浏览器环境。
- 两类启动确认框显示本次运行账号和 provider。
- 诊断页支持内置 Chromium 启动、CDP、代理和 TikTok 登录状态检测。

## 完成定义

- BitBrowser 仍是 TikTok 默认生产 provider。
- 内置 Chromium 通过专项验收后可作为用户主动选择的生产可选 provider。
- UI 不再出现第三种浏览器环境。
- 配置、任务、日志和诊断都能追踪账号使用的浏览器环境。
