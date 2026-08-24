# Account Matrix macOS 内部测试打包说明

本文档只用于内部测试。当前目标是打出一个 macOS 应用，能打开 `.app`、启动内置 Python runtime、拉起 Chrome/Edge/Chromium，并跑一个基础账号任务。

这些步骤需要在 Mac 电脑上执行。Windows 电脑可以用来改源码，但不要用 Windows 电脑产出最终 macOS `.app`。

## 前置准备

- 已安装 macOS 和 Xcode Command Line Tools。
- 已安装 Node.js，并可使用 Corepack。
- 已安装 Rust 和 `rustup`。
- 已安装 Python 3。
- 已安装目标架构可用的 Chrome、Edge、Chromium 或 Chrome for Testing。

安装通用工具：

```bash
xcode-select --install
corepack enable
rustup update stable
```

安装前端依赖：

```bash
cd account-matrix/desktop
pnpm install
cd ..
```

## Intel 芯片 Mac 打包

如果打包机器本身就是 Intel 芯片 Mac，走这一套流程。

创建 Python 打包环境：

```bash
cd account-matrix
python3 -m venv .runtime-build-venv
source .runtime-build-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
```

打包内置 runtime 和 Tauri 应用：

```bash
bash desktop-build-macos.sh
```

预期产物位置：

```text
desktop/src-tauri/target/release/bundle/macos/
desktop/src-tauri/target/release/bundle/dmg/
```

内部测试时，优先使用 `macos` bundle 目录里的 `.app`。如果因为未签名被 macOS 拦截，右键点击应用并选择“打开”，或者到系统设置里允许打开。

## M 芯片 Mac 打 Intel 包

如果打包机器是 M1/M2/M3/M4 Mac，但测试目标是 Intel 芯片 Mac，走这一套流程。

如果还没安装 Rosetta，先安装：

```bash
softwareupdate --install-rosetta --agree-to-license
```

添加 Intel Rust target：

```bash
rustup target add x86_64-apple-darwin
```

在 Rosetta 下创建 Intel 架构 Python 环境：

```bash
cd account-matrix
arch -x86_64 python3 -m venv .runtime-build-venv-x64
source .runtime-build-venv-x64/bin/activate
python -m pip install --upgrade pip
arch -x86_64 python -m pip install -r requirements.txt pyinstaller
```

打包 Intel 架构 Python runtime，并复制到 Tauri resources：

```bash
COPY_TO_TAURI_RESOURCES=1 \
PYTHON_ARCH=x86_64 \
PYTHON_BIN="$PWD/.runtime-build-venv-x64/bin/python" \
DIST_DIR=runtime/dist-x64 \
WORK_DIR=build-x64 \
bash runtime/build-runtime.sh
```

打包 Intel 架构 Tauri 应用：

```bash
cd desktop
pnpm tauri build --target x86_64-apple-darwin
cd ..
```

也可以直接使用项目提供的组合脚本：

```bash
bash desktop-build-macos-x64.sh
```

预期产物位置：

```text
desktop/src-tauri/target/x86_64-apple-darwin/release/bundle/macos/
desktop/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg/
```

注意：Python runtime 和 Tauri 应用必须是同一个目标架构。不要把 arm64 的 Python runtime 放进 x86_64 的 Tauri 应用里。

## M 芯片 Mac 打 M 芯片包

只有当目标测试机器也是 M 芯片 Mac 时，才走这一套流程。

```bash
cd account-matrix
python3 -m venv .runtime-build-venv
source .runtime-build-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
bash desktop-build-macos.sh
```

预期产物位置：

```text
desktop/src-tauri/target/release/bundle/macos/
desktop/src-tauri/target/release/bundle/dmg/
```

## 内部测试检查清单

下面这些检查要在目标 Mac 上做，不要在 Windows 上做：

- `.app` 能正常打开。
- 设置页能显示可读的配置、数据、日志和 runtime 路径。
- 内置 runtime 启动时没有缺失可执行文件错误。
- `Built-in Chromium / 内置 Chromium` 能找到 Chrome、Edge、Chromium 或 Chrome for Testing。
- 浏览器能打开，并使用对应账号的独立用户数据目录。
- 一个基础账号任务能启动，并正常结束，或进入预期的登录/人工处理状态。

## 说明

- 本文档不包含 Apple Developer 签名和公证流程。
- 未签名的内部测试版首次打开时，macOS 可能会出现安全提示。
- BitBrowser 的 macOS 支持还需要在目标 Mac 上用真实客户端和本地 API 验证。
