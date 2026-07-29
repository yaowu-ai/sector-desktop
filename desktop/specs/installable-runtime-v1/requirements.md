# 可安装运行时 V1 Requirements

## 背景

当前桌面端本质上是一个 Tauri 控制台：它会查找仓库根目录，并通过 `py -3.13 src/main.py` 启动 Python 脚本。这种方式适合开发调试，但不适合交付给客户使用，因为安装后的应用仍然依赖外部源码目录、系统 Python、手动安装的 Python 依赖，以及代码旁边可写的配置和数据文件。

可安装运行时 V1 的目标，是把产品变成真正的 Windows 桌面应用：用户安装 Account Matrix 后，打开程序完成首次配置，就能运行已支持的任务，不需要再复制 Python 脚本目录。

## 目标

- 安装包包含 Account Matrix 自身运行所需的全部程序资产。
- 用户不需要安装 Python，也不需要复制 `src/`、`config/` 或 `requirements.txt`。
- 安装后的应用不依赖开发仓库路径。
- 用户数据在应用升级后保留；卸载时除非用户明确删除，否则不应丢失。
- 运行时代码与用户可编辑配置严格分离。
- 迁移过程中保持现有 Python 自动化行为兼容。
- 对外部依赖给出清晰诊断，尤其是 BitBrowser Local API。

## 非目标

- 打包或替代 BitBrowser。
- 打包用户账号、代理凭据、Gmail 凭据或生产客户配置。
- 用 Rust 重写自动化引擎。
- 在本次打包改造中改变任务行为或平台策略。
- 增加云端账号管理、授权系统或多设备同步。

## 产品需求

### R1 安装后的应用必须自包含

Windows 应用安装完成后，Account Matrix 必须能够启动内置自动化运行时，并且不依赖：

- `PATH` 中存在 Python。
- `py -3.13`。
- 仓库根目录。
- 被复制过去的 `src/` 文件夹。
- 手动创建的 `config/` 或 `data/` 文件夹。
- 手动执行 `pip install -r requirements.txt`。

验收：

- Given 一台干净 Windows 机器已安装 BitBrowser，When 用户安装并启动 Account Matrix，Then 应用正常加载，且不要求用户配置项目根目录。
- Given 系统未安装 Python，When 用户启动支持的任务，Then Account Matrix 使用内置运行时。
- Given 旧仓库目录已被删除，When 安装后的应用运行，Then 仍能找到运行时和用户数据。

### R2 首次启动初始化

应用首次启动时，必须创建用户拥有的目录，并在文件不存在时复制默认模板。

首次启动需要准备的文件：

- `config/accounts.yaml`
- `config/comments.txt`
- `config/comments_brand.txt`
- `data/actions.db`，由运行时按需创建
- `data/sessions.log`，由运行时按需创建
- `settings/local-settings.json`

验收：

- Given Account Matrix 用户数据不存在，When 应用启动，Then 创建目录结构和默认配置文件。
- Given 用户配置已经存在，When 应用升级或重新启动，Then 不覆盖用户配置。
- Given 新版本中的模板发生变化，When 应用启动，Then 不直接替换用户已有文件。

### R3 不可变应用文件与可变用户文件分离

安装目录中的应用文件必须被视为不可变运行资产。所有用户编辑或运行时生成的文件，都必须放在安装目录之外。

验收：

- Given 应用安装在 `Program Files` 下，When 用户编辑账号或评论池，Then 写入用户数据目录。
- Given 运行时写入日志和 SQLite 记录，Then 文件写入用户数据目录。
- Given 安装器升级应用，Then 用户文件被保留。

### R4 运行时 Sidecar

Python 自动化引擎必须作为带版本的 sidecar 可执行文件打包，而不是以松散 `.py` 文件形式继续依赖系统 Python 执行。

验收：

- Given 应用启动任务，Then Tauri 启动内置 sidecar 可执行文件。
- Given 运行时 sidecar 缺失或损坏，Then 应用显示清晰的诊断信息。
- Given 运行时版本与桌面壳版本不同，Then 应用能够展示两个版本，方便排查问题。

### R5 兼容开发模式

开发体验必须保留。应用在开发模式下可以继续支持源码执行；但生产构建必须默认使用内置运行时。

验收：

- Given 运行 `pnpm tauri dev`，When 开发者启动任务，Then 应用可以按设置选择源码脚本或内置运行时。
- Given 生产构建，When 用户打开系统设置，Then 正常使用不需要配置项目根目录。
- Given 开发者显式切换到源码模式，Then 仍按项目根目录校验源码结构。

### R6 外部依赖诊断

应用必须清楚区分“内部运行时缺失”和“外部依赖缺失”。

外部依赖包括：

- BitBrowser 客户端。
- BitBrowser Local API，默认 `http://127.0.0.1:54345`。
- 通知服务所需的网络访问。

验收：

- Given BitBrowser 未运行，When 用户启动任务，Then 应用提示 BitBrowser Local API 不可用，而不是提示 Python 缺失。
- Given 内置运行时无法启动，Then 应用提示运行时启动失败，并展示运行时路径。
- Given 配置无效，Then 应用提示配置校验失败，并指向用户数据目录中的配置路径。

### R7 敏感数据不得打包

安装包不得包含客户密钥、凭据或真实运行数据。

敏感数据和私有数据包括：

- 账号凭据。
- 代理凭据。
- Gmail 密码。
- 带密钥的 Webhook URL。
- 生产 `actions.db`。
- 生产 `sessions.log`。
- 客户专属 `accounts.yaml`。

验收：

- Given 创建发布构建，Then 安装包只包含模板配置，不包含仓库里的活动 `config/accounts.yaml`。
- Given 仓库日志包含敏感运行值，Then 发布打包排除这些日志。
- Given 应用导出诊断信息，Then 敏感值被脱敏。

### R8 升级与迁移

应用必须支持未来的运行时升级和配置 schema 升级。

验收：

- Given 用户数据使用旧 schema，When 新版本应用启动，Then 执行幂等迁移。
- Given 迁移失败，Then 应用先备份受影响文件，并显示可恢复的错误。
- Given 内置运行时要求更新的 schema，Then 桌面壳在任务启动前检查兼容性。

### R9 可支持性

技术支持人员必须能从 UI 中识别应用版本、运行时版本、用户数据路径、BitBrowser API 地址和任务日志。

验收：

- 系统设置或诊断页展示桌面端版本、运行时版本、运行时模式、用户配置路径、数据路径和 BitBrowser API URL。
- 诊断页可以测试内置运行时健康状态，而不启动完整账号任务。
- 诊断页可以通过受控 UI 操作打开或定位用户数据路径。

## 完成定义

可安装运行时 V1 完成时，一台干净 Windows 机器应能安装 Account Matrix、创建首次启动配置、连接 BitBrowser、运行已支持的 TikTok 任务、将日志和 SQLite 记录写入用户数据目录，并且在重启和升级后继续可用，不依赖源码仓库或系统 Python。
