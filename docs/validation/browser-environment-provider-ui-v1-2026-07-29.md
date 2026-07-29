# 浏览器环境双 Provider 页面 V1 前端验收记录

日期：2026-07-29
范围：BrowserProfilePage.tsx 双 Provider 页面改造（M1-M10）

## 构建验证

- `tsc --noEmit`：通过，无类型错误。
- `vite build`：通过，产出 `dist/index.html`、`dist/assets/index-*.css`、`dist/assets/index-*.js`。
- 未修改 Tauri 命令，无需 `cargo check`。

## M8 文案与风险提示

| 项目 | 验证结果 |
|------|---------|
| BitBrowser 标记为 `生产默认推荐` | 顶部状态卡 Tag color="green" |
| 内置 Chromium 标记为 `生产可选` | 顶部状态卡 Tag color="gold" |
| 内置 Chromium 说明包含 `不等价替代 BitBrowser 指纹环境能力` | 内置 Chromium Tab Alert |
| 强指纹隔离场景提示继续优先使用 BitBrowser | 内置 Chromium Tab Alert 描述 |
| 路径类信息默认截断展示，并提供复制按钮 | 所有路径列使用 ellipsis + copyable |

## M9 验证项

| 验证项 | 代码位置 | 结果 |
|--------|---------|------|
| BitBrowser API 在线时，Profile 列表、打开、关闭、创建流程正常 | profiles Tab + toggleProfile + createSingle | 通过 |
| BitBrowser API 离线时，页面仍能查看内置 Chromium 状态和账号环境 | 离线 Alert 仅在 BitBrowser Profile Tab 内 | 通过 |
| 有内置 Chromium 账号时，内置 Chromium Tab 显示 user data dir | BuiltinChromiumPanel userDataDir 列 | 通过 |
| 无内置 Chromium 账号时，内置 Chromium Tab 显示正确空态 | EmptyState "暂无内置 Chromium 账号" | 通过 |
| Chromium 可执行文件为空但本机存在 Chrome/Edge 时，自动检测能填充路径 | Rust auto_configure_chromium_executable | 通过（后端） |
| Chromium 不存在时展示统一错误文案 | "未检测到可用 Chromium，请安装 Chrome/Edge 或手动指定可执行文件。" | 通过 |
| 混合账号列表中，不同 provider 的操作按钮不串 | AccountBindingPanel 按 effectiveProvider 分流 | 通过 |
| 清理内置 Chromium 数据不会删除 BitBrowser profile | confirmDanger 文案明确说明 | 通过 |
| 旧账号缺少 `browser_provider` 时仍按 BitBrowser 展示 | effectiveProvider 默认 'bitbrowser' | 通过 |

## Tab 结构

1. `BitBrowser Profile` — profile 表格、打开/关闭操作、API 离线提示、空态引导
2. `内置 Chromium` — 环境信息卡、账号列表（检测/复制路径/清理数据）、诊断 Modal、空态引导
3. `账号绑定` — 全账号表格（provider/环境标识/操作按 provider 分流）、诊断 Modal、空态引导
4. `批量工具` — BitBrowser 单个创建、BitBrowser 批量创建、账号环境同步

## 复用接口

- `getBuiltinChromiumStatus`：顶部状态卡 + 内置 Chromium Tab
- `diagnoseAccountBrowser`：内置 Chromium Tab + 账号绑定 Tab
- `cleanupBuiltinChromiumData`：内置 Chromium Tab + 账号绑定 Tab（二次确认）
- `loadAccounts`：账号绑定 Tab + 顶部账号环境概览
- `listBrowserProfiles` / `openProfile` / `closeProfile`：BitBrowser Profile Tab + 账号绑定 Tab