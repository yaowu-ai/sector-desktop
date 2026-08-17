# TikTok FYP 视频信息采集 V1 Tasks

## M1 基线盘点

- [x] 确认 `src/platforms/tiktok/actions.py:fyp_browse` 当前循环、滚动和互动顺序。
- [x] 确认 `src/platforms/tiktok/fyp.py:run_tiktok_fyp` 当前汇总日志写入点。
- [x] 确认 `src/core/runtime.py:init_db`、`log_action` 的数据库初始化和写入约定。
- [x] 确认 `desktop/src-tauri/src/commands/stats.rs` 现有 SQLite 查询模式。
- [x] 确认 `desktop/src/pages/ExecutionRecordPage.tsx` 可复用筛选区和 Tab 结构。

## M2 数据库与 Runtime 写入

- [x] 在 `init_db()` 中新增 `fyp_video_views` 表。
- [x] 为 `fyp_video_views` 增加账号时间索引。
- [x] 为 `fyp_video_views` 增加 `video_id` 索引。
- [x] 新增 `record_fyp_video_view` 写入函数。
- [x] 新增 `update_fyp_video_interactions` 更新函数。
- [x] 对标题、描述、错误摘要做长度限制和脱敏。
- [x] 写入函数捕获异常，不向 FYP 主循环抛错。
- [x] 增加数据库 helper 单元测试或轻量 SQLite 测试。

## M3 TikTok 视频信息采集器

- [x] 新增 `src/platforms/tiktok/video_info.py` 或在 actions 模块中新增采集函数。
- [x] 实现当前 URL 的 `video_id` 和 `author_handle` 解析。
- [x] 实现当前可见视频附近 `a[href*="/video/"]` 解析。
- [x] 实现当前可见 caption/description/title 文本提取。
- [x] 实现 `meta og:title`、`og:description` fallback。
- [x] 实现 `document.title` fallback，并过滤 TikTok 通用标题。
- [x] 实现文本清洗、去重、截断。
- [x] 实现短超时和异常捕获。
- [x] 返回 `ok`、`partial`、`failed` 状态。

## M4 FYP 主流程接入

- [x] 为 `fyp_browse` 增加可选参数 `conn`、`platform`、`account_id`、`capture_video_info`、`video_capture_config`。
- [x] 进入 `fyp_browse` 时生成 `session_id`。
- [x] 每条视频生成递增 `video_index`。
- [x] 每条视频停留前或停留初期调用采集器。
- [x] 写入 `fyp_video_views` 明细。
- [x] 点赞成功后更新当前明细 `liked=true`。
- [x] 关注成功后更新当前明细 `followed=true`。
- [x] 评论成功后更新当前明细 `commented=true`。
- [x] 保持原返回字段 `videos`、`likes`、`follows`、`comments` 不变。
- [x] 保持原进度输出格式兼容。

## M5 配置接入

- [x] 在平台配置读取中支持 `warmup.video_capture`。
- [x] 提供默认值：开启、标题 300、描述 600、超时 800ms。
- [x] 在 `build_fyp_plan` 中读取并传递视频采集配置。
- [x] 关闭采集时完全跳过 DOM 采集和明细写入。
- [x] 配置缺失时保持向后兼容。

## M6 Rust 查询接口

- [x] 在 `stats.rs` 新增 `FypVideoViewFilter`。
- [x] 在 `stats.rs` 新增 `FypVideoViewRecord`。
- [x] 实现 `query_fyp_video_views` Tauri 命令。
- [x] 支持平台、账号、时间范围、是否有标题、点赞、评论筛选。
- [x] 表不存在时返回空数组。
- [x] 默认 limit 300，最大 limit 1000。
- [x] 在 `main.rs` 注册新命令。
- [x] 增加 Rust SQLite 查询测试。

## M7 前端类型与服务

- [x] 在 `desktop/src/services/types.ts` 增加 `FypVideoViewRecord`。
- [x] 在 `desktop/src/services/types.ts` 增加 `FypVideoViewFilter`。
- [x] 在 `desktop/src/services/api.ts` 增加 `queryFypVideoViews`。
- [x] 确认字段命名使用 camelCase，与 Tauri serde 对齐。

## M8 执行记录页面 UI

- [x] 在【执行记录】页面新增 `FYP 视频明细` Tab。
- [x] 复用平台、账号、时间范围筛选。
- [x] 增加明细专用筛选：有标题、已点赞、已评论。
- [x] 新增视频明细表格。
- [x] 表格展示时间、账号、序号、作者、标题/描述、video_id、观看秒数、互动结果、采集状态。
- [x] 标题和描述支持折叠展开。
- [x] 增加复制标题操作。
- [x] 增加复制视频链接操作。
- [x] 视频链接为空时禁用复制。
- [x] 增加清晰空态文案。

## M9 兼容与回归验证

- [ ] 运行旧数据库，确认新表自动创建。
- [ ] 运行 FYP 任务，确认 `action_log` 仍写入 `fyp_browse videos=N`。
- [ ] 运行 FYP 任务，确认统计页视频数仍与旧逻辑一致。
- [x] 运行 FYP 任务，确认新表产生明细记录。
- [x] 模拟采集失败，确认任务继续并最终记录汇总。
- [x] 关闭 `video_capture.enabled`，确认不产生新明细。
- [ ] BitBrowser provider 账号回归运行。
- [ ] 内置 Chromium provider 账号回归运行。
- [ ] 目标号互动任务回归运行，不受新表影响。

## M10 测试与构建

- [x] 运行 Python 单元测试或新增 SQLite helper 测试。
- [ ] 运行 `python -m compileall src`。
- [x] 运行 `pnpm tsc --noEmit`。
- [ ] 运行前端生产构建。
- [ ] 如修改 Tauri Rust 命令，运行 `cargo check`。
- [ ] 手工验证 PC 端执行记录页新增 Tab。
- [ ] 手工验证至少一个 TikTok FYP 视频能采集到标题或描述。

## 建议实施顺序

1. 先做数据库表和 runtime 写入 helper，保证旁路能力稳定。
2. 再做 TikTok 视频信息采集器，并用独立诊断脚本验证 DOM 提取。
3. 接入 `fyp_browse`，保持所有旧返回字段和日志不变。
4. 增加 Tauri 查询接口。
5. 最后加 PC 端 UI Tab 和筛选。

## 不通过时处理规则

- 如果新功能导致 `fyp_browse` 会话失败，不允许发布。
- 如果现有 `action_log` 汇总格式变化，不允许发布。
- 如果统计页改用新表导致历史统计不一致，不允许发布。
- 如果采集逻辑保存 Cookie、Token、HTML 或登录凭据，不允许发布。
- 如果关闭采集开关后仍写入视频明细，不允许发布。
