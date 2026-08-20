# Account Matrix Desktop

PC 端养号产品 V1 桌面端工程。当前 M1 提供 Tauri + React + TypeScript + Vite 基础工程，并打通一个最小脚本启动闭环：读取 `config/accounts.yaml`、选择账号、运行 `py -3.13 src/main.py --account <account_id>`、显示 stdout 和 stderr。

## 安装版架构

发布版 Windows 安装包包含 Tauri 桌面端和内置 Python runtime sidecar。生产模式默认使用 `bundled`，任务启动器调用 `resources/runtime/account-matrix-runtime.exe`，不依赖源码仓库中的 `src/*.py`，也不依赖系统 `python` 或 `py` 命令。

安装版首次启动会创建用户目录：

- 配置和模板：`%APPDATA%/Account Matrix/config/`
- 本地设置：`%APPDATA%/Account Matrix/settings/local-settings.json`
- SQLite、日志和运行锁：`%LOCALAPPDATA%/Account Matrix/data/`
- 诊断和支持包：`%LOCALAPPDATA%/Account Matrix/logs/`

安装目录只放应用二进制、内置 runtime 和脱敏模板；密码、账号运行数据、SQLite、日志、备份和用户评论池不写入安装目录。

## 产品使用手册

第一版 PC 端产品使用手册见 [`../docs/pc-product-user-manual-v1.md`](../docs/pc-product-user-manual-v1.md)。

## 本地依赖

- Node.js 20+。
- pnpm 9+。如果未安装，可先运行 `corepack enable`，再运行 `corepack prepare pnpm@latest --activate`。
- Rust stable、Cargo 和 Windows WebView2。
- Python 3.13。M0 基线使用 `py -3.13`，不要直接依赖当前 PATH 中的 `python`。
- Python 依赖：在仓库根目录运行 `py -3.13 -m pip install -r requirements.txt`。
- BitBrowser Local API：默认 `http://127.0.0.1:54345`。未启动时脚本会进入失败路径，这是当前业务依赖的真实表现。

## 开发启动

在仓库根目录：

```powershell
cd desktop
pnpm install
pnpm tauri dev
```

也可以只启动前端开发服务器：

```powershell
cd desktop
pnpm dev
```

只启动前端时无法调用 Tauri 后端命令，读取账号和运行脚本需要通过 `pnpm tauri dev` 打开桌面端。

## 发布构建

发布构建需要 Python 3.13 环境中安装 `requirements.txt` 和 `PyInstaller`。仓库根目录运行：

```powershell
.\desktop-build.ps1
```

如需使用隔离 venv：

```powershell
.\desktop-build.ps1 -Python ".\.runtime-build-venv\Scripts\python.exe"
```

脚本会先执行 `runtime/build-runtime.ps1 -CopyToTauriResources`，再构建 NSIS 安装包。产物路径：

```text
desktop\src-tauri\target\release\bundle\nsis\Account Matrix_0.1.0_x64-setup.exe
```

如果要分别打 test / production 安装包：

```powershell
.\desktop-build.ps1 -BuildMode test
.\desktop-build.ps1 -BuildMode production
```

发布前至少运行：

```powershell
cargo +stable test
corepack pnpm build
py -3.13 desktop\tests\runtime_smoke.py
py -3.13 desktop\tests\m20_acceptance.py
desktop\src-tauri\resources\runtime\account-matrix-runtime.exe version --json
desktop\src-tauri\resources\runtime\account-matrix-runtime.exe diagnostic --json --config desktop\src-tauri\resources\templates\config\accounts.yaml --data-dir desktop\.m9-install-test\RuntimeData
```

安装包验证记录见 [`specs/installable-runtime-v1/validation.md`](specs/installable-runtime-v1/validation.md)。

## 支持排障

- 如果安装版提示 runtime 缺失，检查安装目录下 `resources/runtime/account-matrix-runtime.exe`、`resources/runtime/runtime-manifest.json` 和 `resources/runtime/_internal/python313.dll` 是否存在。
- 如果 BitBrowser API 不可用，确认 BitBrowser 已启动、Local API 已开启，系统设置中的 API 地址默认为 `http://127.0.0.1:54345`。
- 如果任务没有写入记录，检查 `%LOCALAPPDATA%/Account Matrix/data/actions.db` 和 `%LOCALAPPDATA%/Account Matrix/data/sessions.log`。
- 导出支持包时会脱敏配置内容；不要手工打包安装目录或仓库下的真实 `config/`、`data/` 目录。

## 路径策略

开发期项目根目录固定按 `desktop/..` 定位：

- `project_root`: 仓库根目录
- `config_path`: `project_root/config/accounts.yaml`
- `comments_path`: `project_root/config/comments.txt`
- `brand_comments_path`: `project_root/config/comments_brand.txt`
- `data_dir`: `project_root/data`
- `actions_db_path`: `project_root/data/actions.db`
- `sessions_log_path`: `project_root/data/sessions.log`
- `lock_file_path`: `project_root/data/run.lock`
- `src_dir`: `project_root/src`

## M1 验收入口

1. 运行 `pnpm tauri dev`。
2. 打开首页，确认项目路径和账号列表可见。
3. 选择 `tiktok_101`。
4. 点击“运行所选账号”。
5. 在脚本输出区域查看 stdout 和 stderr。

## M2 后端命令

M2 已提供以下 Tauri command：

- `get_project_paths()`：返回开发期默认路径。
- `load_config()`：读取 `config/accounts.yaml`，返回 YAML 原文、结构化配置快照和校验结果。
- `validate_config(payload)`：校验 YAML 原文。
- `backup_config()`：备份当前配置到 `config/backups/accounts.YYYYMMDD-HHMMSS.yaml`。
- `save_config(payload)`：先校验，再备份，再写回 `config/accounts.yaml`。

配置保存仍以 `config/accounts.yaml` 为真实数据源；`data/actions.db` 由现有 Python 脚本创建和写入，桌面端后续阶段只负责读取展示。
