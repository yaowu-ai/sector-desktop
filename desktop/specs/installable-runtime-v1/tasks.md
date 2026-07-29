# 可安装运行时 V1 Tasks

## M0 发布卫生

- [ ] 在 `desktop/src-tauri/resources/templates/config/` 定义生产模板。
- [ ] 创建已脱敏的 `accounts.yaml` 模板，不包含真实账号 ID、profile ID、代理或凭据。
- [ ] 创建已脱敏的默认 `comments.txt`。
- [ ] 创建已脱敏的默认 `comments_brand.txt`。
- [ ] 为打包增加排除规则：`data/`、`config/backups/`、`__pycache__/`、`.m20-tmp/`、测试输出和客户专属文件。
- [ ] 文档中明确开发配置仅用于开发。

## M1 Runtime CLI 契约

- [ ] 新增 runtime CLI 入口，支持 `run`、`scheduler`、`gmail`、`diagnostic` 和 `version` 命令。
- [ ] `run` 支持 `--config`、`--data-dir`、`--account` 和 `--platform`。
- [ ] `scheduler` 支持 `--config`、`--data-dir`、`--host` 和 `--port`。
- [ ] `gmail` 保留当前通过环境变量传递密码的安全流程。
- [ ] `diagnostic --json` 返回运行时健康状态，不启动完整账号任务。
- [ ] `version --json` 返回运行时版本、schema 版本和支持的命令。
- [ ] 保持现有 `src/main.py` 和 `src/scheduler.py` 包装器可用于开发。

## M2 Runtime 打包

- [ ] 新增 `runtime/pyinstaller/account-matrix-runtime.spec`。
- [ ] 使用 onedir 模式构建 `account-matrix-runtime.exe`。
- [ ] 包含 `requirements.txt` 中的必要 Python 依赖。
- [ ] 排除开发专用文件和用户数据。
- [ ] 生成 `runtime-manifest.json`。
- [ ] 增加 `version --json` runtime 冒烟测试。
- [ ] 增加 `diagnostic --json` runtime 冒烟测试。
- [ ] 增加使用模板配置的 runtime 配置校验冒烟测试。

## M3 Tauri 资源打包

- [ ] 将内置 runtime 文件加入 Tauri resources。
- [ ] 将模板配置文件加入 Tauri resources。
- [ ] 确认 NSIS 安装包包含 runtime 和模板。
- [ ] 如果继续支持 MSI，确认 MSI 安装包包含 runtime 和模板。
- [ ] 在构建脚本中增加步骤：把最新构建的 runtime 复制到 `desktop/src-tauri/resources/runtime/`。
- [ ] 如果 runtime 文件或 manifest 缺失，发布构建必须失败。

## M4 用户目录初始化

- [ ] 在 Tauri 后端实现启动初始化。
- [ ] 创建 `%APPDATA%/Account Matrix/settings/`。
- [ ] 创建 `%APPDATA%/Account Matrix/config/`。
- [ ] 创建 `%APPDATA%/Account Matrix/config/backups/`。
- [ ] 创建 `%LOCALAPPDATA%/Account Matrix/data/`。
- [ ] 创建 `%LOCALAPPDATA%/Account Matrix/logs/`。
- [ ] 仅在文件缺失时复制模板配置。
- [ ] 仅在 `local-settings.json` 缺失时初始化。
- [ ] 记录已初始化的应用版本。
- [ ] 向 UI 暴露初始化状态。

## M5 路径与设置重构

- [x] 在本地设置中增加 `runtimeMode: bundled | source`。
- [x] 生产构建默认使用 `bundled`。
- [x] 开发构建仍可使用 `source`。
- [x] 用用户配置/数据路径替代生产环境的 `project_root` 要求。
- [x] 在设置快照中增加 `runtimePath`、`runtimeVersion` 和 `runtimeManifestPath`。
- [x] 将普通用户配置默认值从仓库路径迁移到 app data 路径。
- [x] 保留源码模式下的项目根目录校验，供开发者使用。
- [x] 更新系统设置 UI 文案，避免普通用户被要求配置项目根目录。

## M6 进程启动器重构

- [x] 为 bundled 模式增加 Rust runtime 命令构造器。
- [x] 将账号任务执行改为调用 `account-matrix-runtime.exe run`。
- [x] 将调度执行改为调用 `account-matrix-runtime.exe scheduler`。
- [x] 将 Gmail 执行改为调用 `account-matrix-runtime.exe gmail`。
- [x] 保留源码模式下通过 `py -3.13 src/*.py` 执行。
- [x] 继续使用参数数组启动进程。
- [x] 保留 stdout 和 stderr 缓存。
- [x] 保留脱敏行为。
- [x] 仅在仍需要时传递 `AM_CONFIG_PATH`、`AM_DATA_DIR` 和 `AM_AUTO_CLOSE_PROFILE`。

## M7 诊断能力

- [x] 增加 runtime 是否存在的检查。
- [x] 增加 runtime manifest 校验。
- [x] 增加 runtime 版本展示。
- [x] 增加 runtime `diagnostic --json` 命令调用。
- [x] 区分内部 runtime、用户配置、数据目录、BitBrowser API 和 scheduler 端口的诊断。
- [x] 在系统设置中展示用户配置路径和数据路径。
- [x] 增加带脱敏的支持包导出。

## M8 配置迁移

- [x] 增加配置 schema 版本检测。
- [x] 将缺失 schema 版本的配置视为 legacy schema。
- [x] 迁移前备份配置。
- [x] 增加幂等迁移执行器。
- [x] 增加迁移失败恢复提示。
- [x] 确保迁移过程中不覆盖评论池文件。
- [x] 确保现有 `actions.db` 仍可读取。

## M9 安装器与升级验证

- [x] 构建包含内置 runtime 的 NSIS 安装包。
- [ ] 在干净 Windows 测试机或干净虚拟机安装。
- [x] 验证应用启动不依赖仓库根目录。
- [x] 验证应用启动不依赖系统 Python。
- [x] 验证首次启动会创建配置。
- [x] 验证 BitBrowser 停止时，应用显示 BitBrowser API 不可用。
- [ ] 验证 BitBrowser 运行时，任务启动至少能进入 BitBrowser 预检。
- [ ] 验证日志和 SQLite 写入 `%LOCALAPPDATA%/Account Matrix/data/`。
- [x] 覆盖安装升级后，验证用户配置保留。
- [x] 卸载时，确认用户数据保留策略清晰。

## M10 文档

- [x] 更新 desktop README，说明安装后应用架构。
- [x] 更新用户手册，加入首次启动配置。
- [x] 增加发布构建说明。
- [x] 增加干净机器冒烟测试清单。
- [x] 增加支持排障指南。

## 建议实施顺序

1. 创建脱敏模板和用户目录初始化。
2. 增加 runtime CLI，先从源码运行。
3. 打包 runtime sidecar 并做冒烟测试。
4. 在 Tauri 中增加 bundled/source 运行时模式。
5. 将生产进程启动器切换到 sidecar。
6. 加强诊断和迁移。
7. 在干净 Windows 机器上验证安装包。
