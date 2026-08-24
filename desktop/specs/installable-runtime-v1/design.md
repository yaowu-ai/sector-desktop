# 可安装运行时 V1 Design

## 推荐架构

采用三层本地架构：

```text
Account Matrix Desktop
  Tauri 桌面壳
  React UI
  Rust commands

Account Matrix Runtime
  打包后的 Python sidecar 可执行文件
  当前自动化模块和依赖

User Workspace
  用户配置
  评论池
  SQLite 数据
  日志
  本地设置
```

桌面壳负责 UI、设置、校验、诊断和进程控制。运行时 sidecar 负责自动化行为。用户数据存储在安装目录之外。

## 目标文件结构

### 仓库结构

```text
account-matrix/
  desktop/
    specs/
      installable-runtime-v1/
        requirements.md
        design.md
        tasks.md
    src/
    src-tauri/
      tauri.conf.json
      resources/
        templates/
          config/
            accounts.yaml
            comments.txt
            comments_brand.txt
        runtime/
          account-matrix-runtime.exe
          runtime-manifest.json
  runtime/
    account_matrix_runtime/
      __main__.py
      cli.py
      package_info.py
    pyinstaller/
      account-matrix-runtime.spec
  src/
    迁移期保留的当前 Python 模块
  config/
    仅用于开发的配置
  data/
    仅用于开发的数据
```

当前 `src/` 可以在迁移期保留。长期看，自动化代码应移动到 `runtime/account_matrix_runtime/` 这种正式 Python package 中；`src/*.py` 只保留为开发 CLI 兼容包装器。

### 安装后应用结构

示例，安装器负责管理：

```text
%ProgramFiles%/Account Matrix/
  Account Matrix.exe
  resources/
    runtime/
      account-matrix-runtime.exe
      runtime-manifest.json
    templates/
      config/
        accounts.yaml
        comments.txt
        comments_brand.txt
```

从产品视角看，安装目录中的文件只读。

### 用户数据结构

使用用户拥有、可写的位置：

```text
%APPDATA%/Account Matrix/
  settings/
    local-settings.json
  config/
    accounts.yaml
    comments.txt
    comments_brand.txt
    backups/
      accounts.20260727-132800.yaml
  migrations/
    applied.json

%LOCALAPPDATA%/Account Matrix/
  data/
    actions.db
    sessions.log
    run.lock
    stop_after_current.flag
  logs/
    desktop.log
    runtime.log
  cache/
```

推荐拆分：

- `%APPDATA%`：用户设置和可编辑配置；如果 Windows 使用 roaming profile，这些内容可以跟随用户。
- `%LOCALAPPDATA%`：生成日志、SQLite、锁文件、缓存和较大的本地运行文件。

## 运行时打包策略

将 Python 自动化引擎打包为 sidecar 可执行文件。

首版推荐实现：

- 使用 PyInstaller `--onedir`，优先保证可靠性。
- 只有在能接受启动延迟和杀毒软件误报风险时，再考虑 `--onefile`。
- 包含 `requirements.txt` 中的 Python 依赖。
- 只包含生产运行需要的模块。
- 排除 `data/`、备份、`__pycache__`、测试、开发临时文件和客户配置。

运行时可执行文件契约：

```text
account-matrix-runtime.exe run --config <path> --data-dir <path> [--account <id>] [--platform <name>]
account-matrix-runtime.exe scheduler --config <path> --data-dir <path> --port 9601
account-matrix-runtime.exe gmail --config <path> --data-dir <path> ...
account-matrix-runtime.exe diagnostic --json
account-matrix-runtime.exe version --json
```

桌面壳不应该了解 Python 内部模块名，而应调用稳定的运行时命令。

## 运行时 Manifest

每个打包后的运行时都包含一个 manifest：

```json
{
  "name": "account-matrix-runtime",
  "version": "0.1.0",
  "schemaVersion": 1,
  "buildTime": "2026-07-27T00:00:00Z",
  "entrypoint": "account-matrix-runtime.exe",
  "supportedCommands": ["run", "scheduler", "gmail", "diagnostic", "version"],
  "minimumDesktopVersion": "0.1.0"
}
```

Tauri 后端在启动任务前读取 manifest，并在系统设置和诊断页中暴露相关信息。

## 路径解析策略

生产环境不再假设 `project_root` 中存在 `src/main.py`。

新的路径模型：

```text
runtime_mode:
  bundled | source

bundled:
  runtime_path = app_resource_dir/resources/runtime/account-matrix-runtime.exe
  config_path = app_config_dir/config/accounts.yaml
  comments_path = app_config_dir/config/comments.txt
  brand_comments_path = app_config_dir/config/comments_brand.txt
  data_dir = app_local_data_dir/data

source:
  project_root = 开发者配置的仓库根目录
  python_command = 开发者配置的 Python
  script_path = project_root/src/main.py
  config_path = 开发者配置，或 project_root/config/accounts.yaml
  data_dir = 开发者配置，或 project_root/data
```

生产默认使用 `bundled`。`source` 是开发者选项。

## 首次启动初始化

启动时，Tauri 执行一个幂等初始化命令：

1. 解析应用资源目录。
2. 解析 `%APPDATA%/Account Matrix` 和 `%LOCALAPPDATA%/Account Matrix`。
3. 创建必需目录。
4. 仅在目标文件不存在时复制模板配置。
5. 仅在 `local-settings.json` 不存在时创建。
6. 记录已初始化的应用版本。
7. 执行待处理迁移。

规则：

- 没有备份和明确迁移逻辑时，绝不覆盖用户配置。
- 生产包绝不复制开发环境的 `config/accounts.yaml`。
- 模板必须经过清理，对新用户安全。

## Tauri Command 改造

当前生产任务启动方式：

```text
py -3.13 src/main.py --config <config> --account <id>
```

目标生产任务启动方式：

```text
resources/runtime/account-matrix-runtime.exe run --config <user-config> --data-dir <user-data> --account <id>
```

命令构造必须继续使用进程参数数组，不能拼接 shell 字符串。

系统设置快照应暴露：

- `runtimeMode`
- `runtimePath`
- `runtimeVersion`
- `runtimeManifestPath`
- `configPath`
- `dataDir`
- `settingsPath`
- `bitbrowserApiUrl`

## Python 代码迁移

推荐迁移路径：

1. 保持当前 `src/*.py` 命令行脚本可用。
2. 新增 package 级运行时 CLI，先委托现有逻辑。
3. 将共享逻辑从 `src/` 移入可导入的 package 模块。
4. 将 `src/main.py`、`src/scheduler.py` 和诊断脚本改成薄兼容包装器。
5. 基于 package CLI 构建 PyInstaller 运行时。
6. 更新 Tauri 生产模式，改为调用 sidecar runtime。
7. 保留源码模式，用于开发和紧急支持。

## 配置与数据兼容

V1 中继续兼容 `accounts.yaml`、`comments.txt`、`comments_brand.txt` 和 `actions.db` 格式。

只在安全位置增加 schema 元数据：

```yaml
app:
  schema_version: 1
```

如果旧配置缺少 schema 元数据，则视为 schema version `0`，迁移前必须备份。

## 安全边界

打包本身不保护密钥。设计上必须假设用户可以查看本地文件。

规则：

- 不打包真实客户数据。
- 不把密码写入命令行参数。
- 必要时通过短生命周期环境变量传递敏感值。
- 对 stdout、stderr、诊断信息和导出的支持包做脱敏。
- 未来可优先考虑 Windows Credential Manager 或 DPAPI 存储密钥。

## 构建流水线

推荐发布顺序：

```text
1. 清理构建输出。
2. 运行 Python 单元/集成检查。
3. 使用 PyInstaller 构建 runtime sidecar。
4. 运行 runtime 冒烟测试：
   - version --json
   - diagnostic --json
   - 使用模板配置做配置校验
5. 将 runtime 和模板复制到 Tauri resources。
6. 构建 React 前端。
7. 构建 Tauri 安装包。
8. 在干净测试机或干净虚拟机安装。
9. 执行首次启动和任务启动冒烟测试。
```

## 升级策略

每个发布版本可以包含：

- 桌面壳版本。
- runtime sidecar 版本。
- 配置 schema 版本。
- 数据库 schema 版本。

启动流程必须检查兼容性：

```text
desktop starts
  -> initialize user dirs
  -> read runtime manifest
  -> read user settings
  -> migrate config if needed
  -> expose health snapshot to UI
```

数据库迁移继续由运行时逻辑负责，因为运行时写入数据库。

## 长期收益

该设计避免把客户交付绑定到开发工作区，也为后续增长建立清晰边界：

- Tauri 桌面壳可以独立于自动化引擎演进。
- 运行时可以独立测试和版本化。
- 配置和日志路径稳定，便于支持。
- 模板、用户数据、运行时和安装器职责分离，升级更可控。
- 未来平台 adapter 可以打包进同一个运行时，而无需改变桌面端进程模型。
