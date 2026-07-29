# 浏览器环境双 Provider 页面 V1 Requirements

## 背景

Account Matrix 已支持两种浏览器提供方：

- `bitbrowser`：生产默认推荐方案，依赖 BitBrowser Local API 和 profile。
- `builtin_chromium`：生产可选方案，使用本机 Chrome / Edge / Chromium、账号独立 user data dir 和临时 CDP 端口。

当前【浏览器环境】页面仍以 BitBrowser 单一模型组织信息，页面标题、副标题、状态卡、表格列、创建工具和账号同步都默认围绕 BitBrowser profile 展开。内置 Chromium 晋级为生产可选后，该页面需要升级为“双 Provider 浏览器环境管理”视角，避免用户误解内置 Chromium 也需要先创建 BitBrowser profile。

## 目标

- 让用户清楚看到 BitBrowser 与内置 Chromium 都是可用浏览器环境。
- 保留 BitBrowser Profile 管理、创建、同步等现有能力。
- 新增内置 Chromium 状态、自动检测、账号数据目录、诊断和清理入口。
- 将账号绑定从“只绑定 BitBrowser profile”升级为“账号浏览器环境绑定”。
- 明确 BitBrowser 仍是默认推荐，内置 Chromium 是生产可选且不等价替代指纹环境。

## 非目标

- 不改变 TikTok 养号、目标号互动和自动登录任务逻辑。
- 不改变 provider 底层启动、关闭和 CDP 连接协议。
- 不自动迁移 BitBrowser profile 到内置 Chromium。
- 不承诺内置 Chromium 提供 BitBrowser 等价指纹隔离能力。
- 不新增第三种浏览器 provider。

## 功能要求

### R1 页面定位

【浏览器环境】页面必须从 BitBrowser 单一说明改为双 Provider 说明。

验收：

- 页面标题继续遵循平台上下文，例如 `TikTok / 浏览器环境`。
- 页面副标题必须包含 BitBrowser 与内置 Chromium。
- 不再把整个页面描述为 `BitBrowser Local API、profile 管理...`。

推荐文案：

```text
管理 BitBrowser 与内置 Chromium 浏览器环境、账号绑定、代理检测和运行状态。
```

### R2 顶部状态卡

页面顶部必须展示双 Provider 状态。

验收：

- BitBrowser 状态卡展示 API 状态、API 地址、profile 总数、已打开窗口。
- 内置 Chromium 状态卡展示可用状态、自动检测到的可执行文件、数据根目录。
- 账号环境状态卡展示 BitBrowser 账号数、内置 Chromium 账号数、未配置或异常账号数。
- 内置 Chromium 未检测到可执行文件时，提示：

```text
未检测到可用 Chromium，请安装 Chrome/Edge 或手动指定可执行文件。
```

### R3 Tab 信息架构

页面 Tab 必须区分 BitBrowser 专属能力和通用账号环境能力。

验收：

- `Profile 列表` 改为 `BitBrowser Profile`。
- `单个创建`、`批量创建` 必须明确归属 BitBrowser。
- 新增 `内置 Chromium` Tab。
- `账号同步` 改为 `账号绑定` 或 `账号环境同步`。

推荐 Tab：

```text
BitBrowser Profile
内置 Chromium
账号绑定
批量工具
```

### R4 BitBrowser Profile Tab

BitBrowser Tab 保留现有 profile 列表和操作，但必须明确这些功能只作用于 BitBrowser。

验收：

- 表格继续展示窗口名称、窗口 ID、平台、状态、绑定账号、代理、分组、操作。
- 创建 profile、批量创建 profile、打开/关闭 profile 均保留。
- 该 Tab 不展示内置 Chromium 账号为 BitBrowser profile。
- 空态文案应说明当前没有 BitBrowser profile，而不是“暂无数据”。

### R5 内置 Chromium Tab

新增内置 Chromium Tab，用于展示本机 Chromium 能力和账号级环境。

验收：

- 展示 Chromium 可用状态。
- 展示可执行文件路径，默认自动检测 Chrome / Edge / Chromium。
- 展示数据根目录。
- 展示内置 Chromium 账号列表。
- 每个账号展示 user data dir、代理、最近运行记录、CDP/runtime 状态。
- 支持按账号执行诊断。
- 支持清理该账号内置 Chromium 数据。
- 清理操作必须明确不会删除 BitBrowser profile。

### R6 账号绑定视图

账号绑定必须按账号展示当前 provider，而不是只围绕 profile 绑定。

验收：

- 列表至少包含：账号、平台、浏览器提供方、环境标识、代理、状态、操作。
- BitBrowser 环境标识为 `profile_id`。
- 内置 Chromium 环境标识为 `user-data-dir`。
- 未绑定 BitBrowser profile 的 BitBrowser 账号必须清晰标注。
- 内置 Chromium 账号不应提示缺少 BitBrowser profile。

### R7 操作模型

操作按钮必须根据 provider 差异展示。

验收：

- BitBrowser 账号支持打开、关闭、复制窗口 ID、绑定 profile。
- 内置 Chromium 账号支持检测、打开、复制路径、清理数据目录。
- 不向内置 Chromium 账号展示“创建 profile”。
- 不向 BitBrowser profile 展示“清理 user data dir”。

### R8 文案与风险提示

页面必须持续表达默认推荐和风险边界。

验收：

- BitBrowser 标记为生产默认推荐。
- 内置 Chromium 标记为生产可选。
- 内置 Chromium 说明必须包含“不等价替代 BitBrowser 指纹环境能力”。
- 强指纹隔离需求场景仍推荐 BitBrowser。

### R9 兼容性

旧账号和旧 BitBrowser profile 流程必须无感继续可用。

验收：

- 旧账号缺少 `browser_provider` 时仍按 BitBrowser 展示和运行。
- 已有 BitBrowser profile 列表、打开状态、绑定账号和代理列保持可用。
- 已有单个创建、批量创建、账号同步能力不被删除，只调整归属和命名。

## 完成定义

- 用户进入【浏览器环境】后能一眼区分 BitBrowser 与内置 Chromium 的状态。
- 用户不会误以为内置 Chromium 需要创建 BitBrowser profile。
- 内置 Chromium 账号能在页面中看到环境、诊断和清理入口。
- 页面文案与当前生产可选能力一致。
- BitBrowser 原有管理能力不回退。
