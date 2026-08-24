# TikTok AI 评论 V1 M1 基线盘点

盘点日期：2026-08-09

## 结论

M1 的 5 个基线点均已确认。当前系统已经有完整的评论池编辑链路、FYP 评论池随机评论链路、FYP 视频信息采集链路、action_log 汇总日志链路，以及可复用的本机安全凭据存储模式。

## 评论素材页面

前端入口：`desktop/src/pages/CommentPoolPage.tsx`

- 页面通过 `loadCommentPools(currentPlatform)` 读取评论池。
- 页面通过 `saveCommentPools({ platform, generalText, brandText })` 保存通用评论池和品牌评论池。
- 页面本地编辑模型为 `PoolDraft.rows`，每行一个 `CommentRow`。
- 批量粘贴和有效评论统计都使用 `parseCommentLines`。
- 解析规则：空行忽略，`#` 开头注释行忽略，评论按 `trim()` 后的小写文本去重。
- 页面展示重复项数量和前 5 个重复文本。
- 保存后使用后端返回结果重建 snapshot 和 draft。

后端入口：`desktop/src-tauri/src/commands/files.rs`

- Tauri 命令为 `load_comment_pools` 和 `save_comment_pools`，已在 `desktop/src-tauri/src/main.rs` 注册。
- 后端同样执行空行、注释行、大小写去重。
- 保存前会备份通用评论池、品牌评论池和配置文件。
- 保存只写入清理后的有效评论，每行一条。
- 评论池路径来自 `platforms.<platform>.comments.general_file/target_file`，TikTok 默认兼容 `comments.txt` 和 `comments_brand.txt`。

后续影响：

- `CommentPoolPage` 可以在现有两个评论池 Card 上方或下方增加 AI 评论高级区域。
- 不应改变现有 `parseCommentLines` / `saveCommentPools` 的行为。
- AI 评论配置保存应走新命令，避免污染评论池保存职责。

## 本机安全凭据存储

当前已有登录密码凭据能力：`desktop/src-tauri/src/commands/config.rs`

- 命令：`get_login_credential_status`、`save_login_password`、`delete_login_password`。
- 命令已在 `desktop/src-tauri/src/main.rs` 注册。
- Windows 当前实现使用 PowerShell `ConvertFrom-SecureString`，基于当前 Windows 用户 DPAPI 加密。
- Windows 加密内容保存到 `data/credentials/login/<name>.dpapi`。
- macOS 当前实现使用系统 Keychain，并在本地文件保存 marker、service、account。
- `accounts.yaml` 只保存 `login.credential_ref`，不保存登录密码明文。
- 运行时由 Tauri 读取密码后通过环境变量注入 Python，并把密码加入输出脱敏列表。

限制：

- 现有实现命名绑定在 `LOGIN_CREDENTIAL_PREFIX = "account-login/"` 和 `credential_ref_path()`。
- AI API Key 不能直接复用登录密码的 credential_ref 前缀和路径函数。
- 后续应抽出通用 secret helper，或新增 AI Key 专用 helper，例如 `ai-comment/kimi_moonshot/api-key`。

后续影响：

- API Key 保存/删除/状态查询可以复用 DPAPI/Keychain 的实现模式。
- API Key 状态命令只应返回 `hasApiKey` / `provider` 等非敏感字段。
- `desktop/src-tauri/src/security.rs` 的敏感词列表已有 `token`、`secret`、`password`，但后续应明确覆盖 `api_key`、`apikey`、`authorization`。

## FYP 评论入口

主入口：`src/platforms/tiktok/fyp.py`

- `build_fyp_plan(account, config)` 读取 `warmup.comment` 配置。
- `comment.enabled=false` 时 `comments_pool=[]`。
- `comment.enabled=true` 时通过 `load_comments(config, platform)` 读取通用评论池。
- `comments_target = random.randint(*comments_per_session) if comments_pool else 0`。
- `run_tiktok_fyp()` 将 `comments_target`、`comments_pool`、`comment_prob`、`comment_min_videos` 传入 `fyp_browse()`。

执行入口：`src/platforms/tiktok/actions.py`

- `fyp_browse()` 参数包含：
  - `comments_target`
  - `comments_pool`
  - `comment_prob`
  - `comment_min_videos`
- 当前评论触发条件：
  - `comments_done < comments_target`
  - `comments_pool`
  - `random.random() < comment_prob`
- 当前评论文本选择位置：
  - `text = random.choice(comments_pool)`
- 当前发评论位置：
  - `try_comment(page, mouse_state, text, min_comments=comment_min_videos)`

后续影响：

- AI 评论接入点应替换或封装 `text = random.choice(comments_pool)` 这一小段。
- 保持 `comment_prob`、`comments_target`、`comment_min_videos` 的判断不变。
- AI 失败时 fallback 到 `random.choice(comments_pool)`。
- 为支持“评论池为空但 AI 可用”，后续需要调整当前 `and comments_pool` 的触发条件，但不能改变 AI 关闭时的旧行为。

## 当前视频信息可用性

当前工作区已有 FYP 视频信息采集链路：

- `src/platforms/tiktok/actions.py` 导入 `capture_active_video_info`。
- `fyp_browse()` 在每个视频 watch 前调用 `capture_active_video_info(...)`。
- 采集到的 `info` 包含 `title`、`description`、`author_handle`、`author_name`、`video_url`、`video_id`、`raw_source`、`capture_status`、`capture_error`。
- `src/platforms/tiktok/video_info.py` 当前为未跟踪文件，但已经被 `actions.py` 引用。
- `record_fyp_video_view()` 会把 `title` 和 `description` 写入 `fyp_video_views`。

限制：

- 当前 `info` 变量只在 `if capture_enabled:` 块内创建。
- 如果 `capture_enabled=false`，评论逻辑当前拿不到 `title/description`。
- 评论逻辑发生在采集之后、滚动前，因此在采集开启时同一轮循环可以复用当前 `info`。

后续影响：

- 后续接入应在每轮循环初始化 `current_video_info = {}`，采集成功后赋值，评论选择逻辑读取它。
- AI 评论开启但无标题/描述时，应直接 fallback 评论池，满足需求里的“有视频标题/描述时调用 AI 生成”。

## action_log 评论统计

日志入口：

- `src/core/runtime.py::log_action()` 统一写入 `action_log`，并调用 `redact_runtime_text()`。
- `src/platforms/tiktok/fyp.py::run_tiktok_fyp()` 写入 FYP 和评论汇总日志。

当前评论日志：

- 评论目标为 0：`comment skip`
- 评论池为空：`comment skip`
- 评论成功：`comment ok count=<comments>`
- 评论失败：`comment fail count=<comment_failures>`

确认结果：

- 当前 `action_log` 评论统计不记录单条评论文本。
- `fyp_browse()` 返回字段只包含评论数量和失败数量，不包含评论文本。
- `src/stats.py` 和 Tauri stats 查询基于 action/status/detail 聚合，当前不依赖单条评论文本。

后续影响：

- 可以增加 `comment_source=ai` 或 `comment_source=pool reason=<reason>` 日志，但不能替换现有 `comment ok count=N` 汇总。
- 不应把 AI 生成文本、API Key、完整请求体写入 `action_log` 或 session log。

## 工作区注意事项

当前工作区已有未提交改动和未跟踪文件，其中包括：

- `src/platforms/tiktok/actions.py`
- `src/platforms/tiktok/fyp.py`
- `src/core/runtime.py`
- `desktop/src-tauri/src/commands/stats.rs`
- `desktop/src-tauri/src/main.rs`
- `src/platforms/tiktok/video_info.py` 未跟踪
- `desktop/specs/tiktok-ai-comment-v1/` 未跟踪

后续阶段修改这些文件时需要先读取当前内容，保留已有改动，不能按 Git HEAD 覆盖。
