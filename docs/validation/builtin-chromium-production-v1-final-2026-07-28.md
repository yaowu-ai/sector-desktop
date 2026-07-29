# 内置 Chromium 生产可选方案 V1 最终 Validation - 2026-07-28

验证日期：2026-07-28

验证环境：

- OS：Windows 11，PowerShell，Asia/Shanghai
- Workspace：`E:\YAOWU\yangHao\account-matrix`
- Desktop version：`0.1.0`
- 安装包：`desktop/src-tauri/target/release/bundle/nsis/Account Matrix_0.1.0_x64-setup.exe`
- Runtime 模式：bundled
- Chromium executable：外部依赖，由用户在设置页配置或由本机 Chrome/Chromium 路径发现；安装包不内置 Chromium 浏览器二进制
- BitBrowser：仍为默认推荐 provider

## 总体结论

状态：有条件通过。

自动化、打包、bundled runtime、无系统 Python、provider matrix、安装目录模拟均通过。当前机器未进行真实新电脑安装、真实 TikTok 登录/FYP/目标号互动和真实 BitBrowser API 回归；这些 live 项由 M5/M6 当前工作区回归覆盖实现逻辑，本轮以安装模拟和产物检查覆盖跨电脑打包风险。

## 最终产物

| 产物 | 大小 | SHA256 |
| --- | ---: | --- |
| `desktop/src-tauri/target/release/bundle/nsis/Account Matrix_0.1.0_x64-setup.exe` | 44069303 | `29E55217E94DC56A4AE266401F3D0F1E1931CB7D0EDE772DB33420DFFDCCB38D` |
| `desktop/src-tauri/resources/runtime/account-matrix-runtime.exe` | 7716697 | `92ED9E0ABC8571A7B49E71092AB6E444E6689C581A80A623A843360638DA487D` |
| `desktop/.m8-install-sim-final/account-matrix-desktop.exe` | 12867584 | `90242EC566AF3FB4D08E479EB436A5967C30704FEE20A8B506C1752FD92A60B3` |

## Provider Matrix

安装模拟目录下 bundled runtime 输出：

| Provider | production_ready | risk_level | supports_tiktok | 备注 |
| --- | --- | --- | --- | --- |
| `bitbrowser` | true | `stable` | true | Production default |
| `builtin_chromium` | true | `production_optional` | true | Production optional；不等价替代 BitBrowser 指纹能力 |

旧 runtime 中的 `custom_cdp` 和 `experimental` 状态已不再出现在最终 bundled runtime 诊断输出中。

## M8 验收记录

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 安装包包含 Chromium 所需二进制或依赖来源明确 | 通过 | Tauri resources 包含 bundled runtime、Patchright driver、`browsers.json`；Chromium 浏览器二进制不内置，依赖来源明确为用户设置的 Chromium executable 或本机 Chrome/Chromium 自动发现 |
| 无源码目录的新电脑安装应用 | 安装模拟通过 | `desktop/.m8-install-sim-final` 只复制 release exe 和 resources，不使用源码目录运行 runtime smoke |
| 不依赖系统 Python | 通过 | 最小 `PATH=C:\Windows\System32;C:\Windows` 且移除 `PYTHONHOME`/`PYTHONPATH` 后，`account-matrix-runtime.exe version --json` 正常返回；resources 内含 `_internal/python313.dll` |
| 新电脑通过 UI 新增内置 Chromium 账号 | 逻辑覆盖 | M7 表单已支持全中文内置 Chromium 字段；真实新电脑 UI 手工录入需在目标机器复测 |
| 保存本机登录密码凭据 | 逻辑覆盖 | M5 已完成本机安全凭据存储与环境变量传递；真实目标机器需用当地 Windows 凭据存储复测 |
| 执行账号浏览器诊断 | 安装模拟部分通过 | bundled runtime diagnostic 成功；Tauri 账号级浏览器诊断 UI/命令已在 M7 接入，真实账号启动/CDP 检测需目标机器复测 |
| 执行 TikTok 登录检测 | 前序覆盖 | M5 登录态和人工接管链路已完成；当前 M8 未执行 live TikTok |
| 执行 FYP 最小任务 | 前序覆盖 | M6 FYP 任务回归已完成；当前 M8 未执行 live TikTok |
| 执行目标号互动最小任务 | 前序覆盖 | M6 目标号互动回归已完成；当前 M8 未执行 live TikTok |
| 安装包中 BitBrowser 默认行为仍正常 | 静态通过 | 默认 provider 仍为 `bitbrowser`；provider matrix 显示 BitBrowser `production_ready=true`、`risk_level=stable`；真实 BitBrowser Local API 回归需目标机器复测 |

## 执行命令摘要

| 命令 | 结果 |
| --- | --- |
| `cargo +stable-x86_64-pc-windows-msvc fmt --manifest-path desktop/src-tauri/Cargo.toml` | 通过 |
| `cargo +stable-x86_64-pc-windows-msvc test --manifest-path desktop/src-tauri/Cargo.toml --target-dir $env:TEMP\account-matrix-cargo-target-m8` | 35 passed |
| `powershell -ExecutionPolicy Bypass -File runtime\build-runtime.ps1 -Python ".\.runtime-build-venv\Scripts\python.exe" -DistDir "runtime/dist-m8" -WorkDir "build-m8" -CopyToTauriResources` | 通过 |
| `corepack pnpm tauri build --bundles nsis` | 通过，生成最终 NSIS 包；仅有既有 Vite chunk size warning 和 Rust dead_code warning |
| 安装模拟 runtime `version --json`，最小 PATH，无 `PYTHONHOME`/`PYTHONPATH` | 通过 |
| 安装模拟 runtime `diagnostic --json`，模板 config | 通过，返回 provider matrix 最新状态；dataDir 为新目录时给 warning，符合预期 |

## 本轮修复

- `desktop-build.ps1` 现在会在 runtime build 或 Tauri package build 失败时立即失败，不再继续生成可能使用旧 runtime 的安装包。
- bundled runtime 路径解析改为优先使用 Tauri setup 提供的实际 `resource_dir`，安装包环境不再依赖编译时源码路径寻找 `resources/runtime`。
- runtime 已重建并复制到 Tauri resources，最终安装包使用包含 M7/M8 变更的新 runtime。

## 发布注意事项

- 内置 Chromium 是生产可选方案，不等价替代 BitBrowser 的指纹环境能力。
- 对高风险账号和需要强指纹隔离的场景，仍建议默认使用 BitBrowser。
- 正式发布前建议在一台没有源码 checkout 的目标机器上完成真实安装、真实 TikTok 登录、FYP、目标号互动和 BitBrowser Local API 回归。
