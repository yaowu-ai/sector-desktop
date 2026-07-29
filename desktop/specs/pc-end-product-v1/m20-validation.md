# M20 测试与验收记录

## 自动化覆盖

- Rust 模块内单测已覆盖 YAML 读取/序列化、配置校验、active_hours 重叠、评论池读写、SQLite 查询、进程参数构造、日志脱敏、BitBrowser 代理解析和同步账号规划。
- `desktop/tests/m20_acceptance.py` 提供无副作用验收检查：读取真实 `accounts.yaml`、验证账号数量、探测 BitBrowser API socket、验证 `sessions.log` 增量读取、用临时 SQLite 校验执行记录和 `src/stats.py --json` 统计一致性。
- `desktop/package.json` 增加 `test:m20`，用于在 Windows 开发环境运行 M20 验收脚本。

## 本次执行结果

- `py -3.13 tests\m20_acceptance.py`：通过，检测到 `accounts.yaml` 中 25 个账号；BitBrowser API socket `http://127.0.0.1:54345` 当前可达；临时 SQLite 与 `src/stats.py --json` 统计一致。
- `.\node_modules\.bin\tsc.CMD --noEmit`：通过。
- `.\node_modules\.bin\vite.CMD build`：通过；保留既有的 chunk size warning。
- `cargo test`：当前机器 PATH 中没有 `cargo`，未能执行 Rust 单测。单测代码已落在对应 Rust 模块内，安装 Rust 工具链后可直接运行。

## 人工验收边界

以下项目依赖本机 BitBrowser 客户端、真实 TikTok/Gmail 账号或人工验证状态，不在自动脚本中直接触发，避免误运行账号任务或创建/删除 profile：

- 单账号真实运行。
- scheduler 真实启动并访问 `/health`。
- 账号同步 dry-run 的真实 BitBrowser profile 列表。
- Gmail 初始化真实登录流程。
- 点赞诊断和评论诊断真实页面执行。

这些入口已由无副作用检查确认前后端命令路径存在；真实环境验收按 `requirements.md` 的验收条件逐项执行。
