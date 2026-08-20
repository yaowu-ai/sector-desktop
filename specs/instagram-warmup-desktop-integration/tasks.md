# Instagram 养号桌面端接入任务文档

## 阶段 1：基线确认

- [x] 确认桌面端 Instagram 平台仍处于 reserved 状态的位置：
  - [x] `desktop/src/platforms/registry.ts`
  - [x] `desktop/src/pages/PlatformPage.tsx`
  - [x] `desktop/src/pages/TaskPage.tsx`
- [x] 确认 Rust 命令层的任务放行点：
  - [x] `desktop/src-tauri/src/commands/process.rs`
  - [x] `desktop/src-tauri/src/commands/config.rs`
- [x] 确认桌面前端的 API 和类型入口：
  - [x] `desktop/src/services/api.ts`
  - [x] `desktop/src/services/types.ts`
  - [x] `desktop/src/services/platforms.ts`
- [x] 确认 Python runtime 的平台入口：
  - [x] `src/platforms/instagram.py`
  - [x] `src/platforms/registry.py`
  - [x] `src/core/runtime.py`
- [x] 确认 `account-matrix-ins/src/ins` 中需要迁移的执行模块边界。

## 阶段 2：Python runner 接入

- [x] 新建 Instagram runner 包并迁移执行逻辑：
  - [x] BitBrowser 会话
  - [x] 页面动作
  - [x] 配置读取
  - [x] 冷却写入
  - [x] 会话日志
- [x] 保留 `src/platforms/instagram.py` 兼容入口，导出新的 runner。
- [x] 为 Instagram runner 增加 CLI 入口和单账号运行入口。
- [x] 为 Instagram runner 增加原脚本长期运行入口：
  - [x] `--schedule` 拟人日程模式
  - [x] `--loop` 循环模式
  - [x] `--once` 单轮模式
  - [x] `--dry-run` 排期预览
- [x] 让 runner 写入现有 `actions.db` 和 `sessions.log`。
- [x] 让 Instagram 长期排期写入 `data/ins/schedule_state.json`，并同步镜像到桌面端 `scheduler_job_runs`。
- [x] 增加 `risk_cooldown` 持久化表或等价持久化结构。

## 阶段 3：桌面端后端接入

- [x] 更新平台能力矩阵，把 Instagram 从 reserved 改为 supported。
- [x] 放开 `run_platform_task` 对 Instagram warm-up 的执行校验。
- [x] 调度命令按平台分流：
  - [x] TikTok 继续使用现有 `src/scheduler.py` / bundled `scheduler`
  - [x] Instagram 使用 `platforms.instagram_runner --schedule` / bundled `instagram-scheduler`
- [x] 增加或调整 Instagram warm-up 的配置读取与保存接口。
- [x] 更新 `desktop/src/services/api.ts` 与 `desktop/src/services/types.ts` 的平台任务类型和配置请求。
- [x] 保证账号页、调度页、记录页可以按 Instagram 平台查询。

## 阶段 4：桌面端前端接入

- [x] 平台页展示 Instagram 可执行状态。
- [x] 任务页根据当前平台切换为 Instagram warm-up 表单。
- [x] 启动按钮发起 Instagram runner，而不是 `account-matrix-ins` 面板。
- [x] 运行输出区能显示 Instagram 任务状态和日志。
- [x] 调度页启动/停止/健康检查会传当前平台，Instagram 不再复用 TikTok scheduler。

## 阶段 5：配置与数据迁移

- [x] 为 `platforms.instagram.warmup` 定义稳定 schema。
- [x] 为旧配置提供迁移或默认值填充。
- [x] 确认 Instagram 的评论素材仍复用现有评论池文件。
- [x] 确认冷却、日志和统计可以在重启后继续读取。

## 阶段 6：测试

- [x] Python runner 单测：
  - [x] 配置解析
  - [x] 任务执行分支
  - [x] 冷却读写
  - [x] 代理/风控拒绝
- [x] Rust/Tauri 单测：
  - [x] 平台能力放行
  - [x] task type 映射
  - [x] 配置保存路径
- [x] 前端单测：
  - [x] 平台页状态展示
  - [x] 任务页平台切换
  - [x] Instagram 表单保存和启动
- [x] 长期模式接入检查：
  - [x] Python runner 只加载 scheduled Instagram 账号
  - [x] Instagram schedule_state 镜像到桌面端调度历史
  - [x] 前端/后端静态检查覆盖平台化 scheduler 分流
- 备注：Python/前端联调检查已通过；Rust/Tauri 单测已补充，当前机器缺少 `cargo`，未能本地执行。

## 阶段 7：打包与烟测

- [x] 确认 `desktop-build.ps1` 和 runtime 打包会包含新的 Instagram runner 文件。
- [ ] 在 Windows 下做一次桌面端启动烟测。
- [ ] 用一个已登录且已绑定 profile 的 Instagram 账号做单次 warm-up 烟测。
- [ ] 验证风控命中后会写入冷却并在桌面端显示跳过。
