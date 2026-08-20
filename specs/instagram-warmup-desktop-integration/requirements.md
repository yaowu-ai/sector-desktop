# Instagram 养号桌面端接入需求文档

## 1. 背景

`account-matrix` 的桌面端已经预留了 Instagram 平台位置，但当前 Instagram 仍是 `reserved`，自动执行入口不可用。与此同时，`account-matrix-ins` 里已经有一套可独立运行的 Instagram 养号脚本，包含 BitBrowser 接管、拟人操作、风控检测、冷却和日志能力。

本需求的目标不是复用 `account-matrix-ins` 自带的控制面板，而是把其中的 Instagram 养号执行能力接到 `account-matrix` 的桌面端保留位里，让用户可以直接在桌面端完成 Instagram 账号养号。

## 2. 目标

- 桌面端的 Instagram 平台变成可执行平台。
- 用户可以在桌面端完成 Instagram 账号配置、任务启动、调度、日志查看和结果追踪。
- Instagram 的养号执行逻辑使用现有 ins 脚本的行为模型和风控保护，而不是重新实现一套新的自动化流程。
- 现有 TikTok、WhatsApp、抖音能力不被破坏。

## 3. 范围

### 3.1 需要覆盖

- 桌面端平台能力矩阵中 Instagram 的状态切换。
- 桌面端任务页中 Instagram 养号入口。
- 桌面端账号页、调度页、记录页对 Instagram 账号的支持。
- Python runtime 中 Instagram 养号 runner 的接入。
- Instagram 养号的配置、日志、冷却和统计落盘。
- 打包后的桌面应用也能直接使用 Instagram 养号功能。

### 3.2 不在范围

- 不接入 `account-matrix-ins` 自带的 web 面板。
- 不新增独立的 Instagram 后台服务。
- 不做目标号互动、Gmail 初始化、WhatsApp、抖音接入。
- 不改变现有授权、登录、订阅、设备管理主流程。

## 4. 用户故事

### 4.1 桌面端操作者

作为桌面端操作者，我可以在平台选择器里切到 Instagram，并在任务页直接启动 Instagram 养号。

### 4.2 账号管理员

作为账号管理员，我可以像管理 TikTok 账号一样配置 Instagram 账号、BitBrowser profile、代理和活跃时段，并把账号加入调度。

### 4.3 运行维护者

作为运行维护者，我可以在桌面端看到 Instagram 任务的执行状态、日志和冷却结果，异常账号会被自动跳过而不是重复硬跑。

## 5. 验收标准

- Instagram 在平台设置页显示为已接入，可执行养号任务，不再是纯预留状态。
- 任务页在 Instagram 平台下显示 Instagram 养号配置和启动按钮。
- 点击启动后，桌面端会启动 Python runner 并输出 Instagram 任务日志，而不是打开 `account-matrix-ins` 面板。
- Instagram 账号的配置、启用状态和调度设置可以保存并在重启后保持。
- 命中风控或验证页时，账号会进入冷却期，冷却期内桌面端自动跳过该账号。
- 现有 TikTok 养号、注册、统计和调度能力保持不变。

