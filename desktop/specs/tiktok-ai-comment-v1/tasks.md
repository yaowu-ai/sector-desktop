# TikTok AI 评论 V1 Tasks

## M1 基线盘点

- [x] 确认评论素材页面 `CommentPoolPage` 的现有读取、编辑、保存、去重逻辑。
- [x] 确认 Tauri 当前是否已有本机安全凭据存储能力可复用。
- [x] 确认 FYP 评论入口：`fyp_browse` 中 `random.choice(comments_pool)` 和 `try_comment` 调用位置。
- [x] 确认当前视频信息在 FYP 循环中的可用变量。
- [x] 确认现有 `action_log` 评论统计不依赖单条评论文本。

## M2 配置与密钥存储

- [x] 新增 AI 评论非敏感配置模型。
- [x] 默认 `enabled=false`。
- [x] 支持 `provider=kimi_moonshot`。
- [x] 支持 `base_url`、`model`、`timeout_seconds`、`max_comment_length`、`language`、`blocked_words`。
- [x] 默认 `base_url=https://api.moonshot.cn/v1`。
- [x] 默认 `model=kimi-k2.6`。
- [x] 配置模型保留未来 provider 扩展能力，避免只支持硬编码 Kimi。
- [x] 新增 API Key 保存命令，使用本机安全凭据存储。
- [x] 新增 API Key 删除命令。
- [x] 新增 API Key 状态查询命令，只返回是否已保存。
- [x] 确认 API Key 不写入 YAML。

## M3 AI 评论生成模块

- [x] 新增 `src/ai_comment.py`。
- [x] 实现 Kimi Moonshot chat completions 请求。
- [x] 通过 `Authorization: Bearer <MOONSHOT_API_KEY>` 认证。
- [x] 将 Kimi 请求逻辑封装到 provider adapter 或等价结构中。
- [x] `generate_ai_comment` 只依赖统一 adapter 接口，不直接写死某个厂商。
- [x] 实现 Base URL 拼接兼容。
- [x] 实现请求超时。
- [x] 实现响应解析 `choices[0].message.content`。
- [x] 实现错误脱敏。
- [x] 实现 `generate_ai_comment(context, config, credential_reader)`。
- [x] 为网络失败、超时、无密钥、响应格式异常返回结构化失败结果。

## M4 内容校验

- [x] 实现 `validate_generated_comment`。
- [x] 过滤空文本。
- [x] 过滤多行文本。
- [x] 过滤 URL。
- [x] 过滤 `@` 提及。
- [x] 过滤手机号、邮箱、WhatsApp/Telegram 等联系方式。
- [x] 过滤超过最大长度的文本。
- [x] 过滤敏感词黑名单。
- [x] 过滤模型解释前缀。
- [x] 增加单元测试覆盖每个失败原因。

## M5 FYP 评论接入

- [x] 将当前视频 `title/description` 传入评论文本选择逻辑。
- [x] AI 评论关闭时保持原 `random.choice(comments_pool)`。
- [x] AI 评论开启且有视频标题/描述时调用 AI 生成。
- [x] AI 成功且校验通过时使用 AI 评论。
- [x] AI 失败或校验失败时回退评论池。
- [x] 评论池为空且 AI 失败时沿用现有跳过/失败逻辑。
- [x] 不改变 `comment_prob`、`comments_target`、`comment_min_videos`。
- [x] 不改变 `fyp_browse` 原汇总返回字段。
- [x] FYP 评论流程不直接读取具体 provider 名称，只调用统一 AI 评论生成入口。

## M6 日志与追踪

- [x] AI 生成成功记录 `comment_source=ai`。
- [x] 回退评论池记录 `comment_source=pool reason=<reason>`。
- [x] AI 失败记录脱敏错误。
- [x] 普通 `comment ok count=N` 汇总保持不变。
- [x] 不记录 API Key、完整请求体或账号敏感信息。

## M7 Tauri 设置命令

- [x] 新增 `load_ai_comment_settings`。
- [x] 新增 `save_ai_comment_settings`。
- [x] 新增 `save_ai_comment_api_key`。
- [x] 新增 `delete_ai_comment_api_key`。
- [x] 新增 `get_ai_comment_api_key_status`。
- [x] 新增 `test_ai_comment_connection`。
- [x] 新增 `preview_ai_comment`。
- [x] 在 `main.rs` 注册命令。
- [x] 增加 Rust 命令参数和返回类型。

## M8 评论素材页面 UI

- [x] 在 `CommentPoolPage` 增加 `AI 评论` 高级区域。
- [x] 增加启用 Switch。
- [x] 增加 Base URL 输入。
- [x] 增加 Model 输入。
- [x] 增加 API Key 密码输入。
- [x] 增加超时秒数设置。
- [x] 增加最大评论长度设置。
- [x] 增加语言设置。
- [x] 增加敏感词黑名单编辑。
- [x] 增加保存配置按钮。
- [x] 增加保存/删除 API Key 按钮。
- [x] 增加测试连接按钮。
- [x] 增加试生成区域。
- [x] 未配置 API Key 时展示明确提示。
- [x] 保留原评论池编辑体验。

## M9 前端类型与服务

- [x] 新增 AI 评论设置 TypeScript 类型。
- [x] 新增 API Key 状态类型。
- [x] 新增测试连接结果类型。
- [x] 在 `services/api.ts` 增加 AI 评论相关 invoke 封装。
- [x] UI 字段命名与 Tauri serde camelCase 对齐。

## M10 测试与回归

- [x] AI 评论关闭时，FYP 评论仍从评论池取文本。
- [x] AI 评论开启且生成成功时，`try_comment` 使用 AI 文本。
- [x] AI 超时时回退评论池。
- [x] AI 返回 URL/@/多行/过长文本时回退评论池。
- [x] 评论池为空且 AI 失败时任务不崩溃。
- [x] API Key 不出现在 YAML。
- [x] API Key 不出现在 action_log。
- [x] 评论素材页面原保存评论池能力不回退。
- [x] 运行 Python 单元测试。
- [x] 运行 `pnpm tsc --noEmit`。
- [x] 运行前端生产构建。
- [x] 如修改 Tauri Rust 命令，运行 `cargo check`。

## M11 Provider 扩展性验证

- [x] 验证 Kimi Moonshot adapter 可通过配置的 `base_url` 和 `model` 工作。
- [x] 增加一个 fake/custom Chat Completions adapter 单元测试，确认不改 FYP 逻辑也能替换模型来源。
- [x] 验证新增 provider 时不需要修改内容校验逻辑。
- [x] 验证新增 provider 时不需要修改评论池 fallback 逻辑。
- [x] 文档中说明：兼容 Chat Completions 的 API 通常只需改配置；非兼容 API 需要新增 adapter。

## 建议实施顺序

1. 先做配置模型和密钥存储，确保 API Key 安全边界清楚。
2. 再做 `src/ai_comment.py` 和内容校验单元测试。
3. 接入 FYP 评论文本选择逻辑，保持评论池 fallback。
4. 增加 Tauri 设置、测试连接和试生成命令。
5. 最后改评论素材页面 UI。

## 不通过时处理规则

- 如果 AI 评论关闭时原评论池行为变化，不允许发布。
- 如果 API Key 明文进入 YAML、日志或支持包，不允许发布。
- 如果 AI 失败导致 FYP 任务失败，不允许发布。
- 如果生成内容未校验就发布，不允许发布。
- 如果评论概率、评论目标数或评论数门槛被 AI 功能改变，不允许发布。
