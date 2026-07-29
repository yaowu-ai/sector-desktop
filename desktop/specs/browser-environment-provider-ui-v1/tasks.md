# 浏览器环境双 Provider 页面 V1 Tasks

## M1 基线盘点

- [x] 盘点当前 `BrowserProfilePage` 中 BitBrowser API 状态、profile 列表、创建、批量创建和账号同步的实现位置。
- [x] 盘点已有 `getBuiltinChromiumStatus`、`diagnoseAccountBrowser`、`cleanupBuiltinChromiumData` 等接口是否可复用。
- [x] 确认账号模型中 `browserProvider`、`browser.profileId`、`browser.userDataDir`、`browser.proxy` 字段可满足页面展示。
- [x] 确认旧账号缺少 `browser_provider` 时 UI 按 BitBrowser 展示。
- [x] 确认当前 BitBrowser profile 创建流程没有被其他页面强依赖。

## M2 页面标题与状态卡

- [x] 修改【浏览器环境】页面副标题，覆盖 BitBrowser 与内置 Chromium。
- [x] 将顶部 BitBrowser API / Profile 总数 / 已打开窗口调整为 BitBrowser 状态区。
- [x] 新增内置 Chromium 状态卡，展示可用状态、可执行文件和数据根目录。
- [x] 新增账号环境状态卡，统计 BitBrowser 账号、内置 Chromium 账号和待处理账号。
- [x] 内置 Chromium 未检测到时展示统一错误文案。
- [x] 保留页面右上角刷新按钮，并刷新双 Provider 状态。

## M3 Tab 信息架构

- [x] 将 `Profile 列表` 改名为 `BitBrowser Profile`。
- [x] 新增 `内置 Chromium` Tab。
- [x] 将 `账号同步` 改名为 `账号绑定` 或 `账号环境同步`。
- [x] 将 `单个创建`、`批量创建` 迁移或标注为 BitBrowser 专属能力。
- [x] 确认 Tab 切换后不触发不必要的 BitBrowser API 调用。

## M4 BitBrowser Profile Tab

- [x] 保留现有 profile 表格列和分页。
- [x] 保留打开、关闭、复制窗口 ID、绑定账号等操作。
- [x] 将空态改为 `暂无 BitBrowser Profile。可通过批量工具创建并绑定账号。`
- [x] BitBrowser API 离线时展示可理解错误，不影响其他 Tab。
- [x] 创建 profile 相关按钮和表单明确标注 BitBrowser。

## M5 内置 Chromium Tab

- [x] 展示 Chromium 可执行文件状态和自动检测结果。
- [x] 展示内置 Chromium 数据根目录。
- [x] 按账号列出 `browserProvider=builtin_chromium` 的账号。
- [x] 每行展示账号、代理、user data dir、runtime 记录、最近 CDP、最近运行状态。
- [x] 增加账号级 `检测` 操作，复用浏览器诊断能力。
- [x] 增加 `复制路径` 操作，复制 user data dir。
- [x] 增加 `清理数据` 操作，复用 `cleanupBuiltinChromiumData`。
- [x] 清理数据前弹出二次确认，说明不会删除 BitBrowser profile。
- [x] 内置 Chromium 账号为空时展示引导去账号管理配置 provider。

## M6 账号绑定视图

- [x] 新增或改造账号绑定表格，按账号展示 provider。
- [x] 表格列包含账号、平台、浏览器提供方、环境标识、登录邮箱、代理、状态、操作。
- [x] BitBrowser 环境标识显示 profile_id。
- [x] 内置 Chromium 环境标识显示 user-data-dir。
- [x] BitBrowser 账号缺少 profile_id 时标注待绑定。
- [x] 内置 Chromium 账号不显示缺少 profile_id 的错误。
- [x] 操作按钮根据 provider 分流。

## M7 批量工具

- [x] 将单个创建表单归到 BitBrowser 创建工具。
- [x] 将批量创建表单归到 BitBrowser 批量创建工具。
- [x] 将账号同步改造成账号环境同步。
- [x] 账号环境同步必须区分 BitBrowser profile 绑定和内置 Chromium provider 补齐。
- [x] 同步预览中不要展示内置 Chromium 需要创建 profile 的提示。

## M8 文案与风险提示

- [x] BitBrowser 标记为 `生产默认推荐`。
- [x] 内置 Chromium 标记为 `生产可选`。
- [x] 内置 Chromium 说明中包含 `不等价替代 BitBrowser 指纹环境能力`。
- [x] 强指纹隔离场景提示继续优先使用 BitBrowser。
- [x] 路径类信息默认截断展示，并提供复制按钮。

## M9 验证

- [x] BitBrowser API 在线时，Profile 列表、打开、关闭、创建流程正常。
- [x] BitBrowser API 离线时，页面仍能查看内置 Chromium 状态和账号环境。
- [x] 有内置 Chromium 账号时，内置 Chromium Tab 显示 user data dir。
- [x] 无内置 Chromium 账号时，内置 Chromium Tab 显示正确空态。
- [x] Chromium 可执行文件为空但本机存在 Chrome/Edge 时，自动检测能填充路径。
- [x] Chromium 不存在时，展示 `未检测到可用 Chromium，请安装 Chrome/Edge 或手动指定可执行文件。`
- [x] 混合账号列表中，不同 provider 的操作按钮不串。
- [x] 清理内置 Chromium 数据不会删除 BitBrowser profile。
- [x] 旧账号缺少 `browser_provider` 时仍按 BitBrowser 展示。

## M10 文档与回归

- [x] 更新产品手册中【浏览器环境】章节。
- [x] 更新内置 Chromium 生产可选发布说明中对页面入口的描述。
- [x] 补充前端组件测试或手工验收记录。
- [x] 运行 `tsc --noEmit`。
- [x] 运行前端生产构建。
- [x] 如修改 Tauri 命令，运行 `cargo check`。

## 建议实施顺序

1. 先改标题、副标题和顶部状态卡，让页面定位正确。
2. 再把现有 Profile 列表迁移为 `BitBrowser Profile` Tab。
3. 新增 `内置 Chromium` Tab，只做状态、账号列表、检测和清理。
4. 改造账号同步为账号绑定视图。
5. 最后整理批量创建工具和文案风险提示。

## 不通过时处理规则

- 如果 BitBrowser 原 profile 管理能力回退，不允许发布。
- 如果内置 Chromium 账号仍被提示缺少 BitBrowser profile，不允许发布。
- 如果清理操作可能误删 BitBrowser profile，不允许发布。
- 如果页面无法区分生产默认和生产可选，不允许发布。
