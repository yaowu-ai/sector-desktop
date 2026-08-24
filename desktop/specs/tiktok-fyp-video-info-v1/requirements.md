# TikTok FYP 视频信息采集 V1 Requirements

## 背景

当前 PC 端养号任务的 TikTok FYP 浏览能力只记录会话级汇总：

- `fyp_browse` 成功记录只保存 `videos=N`。
- `like`、`follow`、`comment` 只保存 `count=N` 或失败原因。
- `target_engagements` 只保存目标号互动的 `video_id`、点赞和评论状态。

因此用户无法在 PC 端查看养号过程中实际浏览过哪些视频，也无法获取视频标题、作者、链接等明细信息。现有统计和执行记录依赖当前汇总结构，新增能力必须不影响已有功能。

## 目标

- 在 TikTok FYP 养号浏览过程中采集当前可见视频的基础信息。
- 至少支持采集视频标题或描述文本。
- 尽量采集 `video_id`、作者、视频链接、观看时长、是否点赞、是否关注、是否评论。
- 将视频级明细存入独立数据结构，不破坏现有 `action_log` 汇总记录。
- 在 PC 端提供可查询的视频明细记录，便于用户确认浏览内容。
- 采集失败时不影响养号任务继续执行。

## 非目标

- 不改变 FYP 浏览、点赞、关注、评论的现有行为概率和节奏。
- 不替代 TikTok 官方 API，不新增外部服务依赖。
- 不保证所有 TikTok 页面版本都能 100% 采集标题。
- 不采集评论区内容、弹幕、用户隐私信息或登录态敏感信息。
- 不把视频标题塞进现有 `action_log.detail` 作为主要存储。
- 不改变目标号互动水位线逻辑。

## 功能要求

### R1 视频信息采集

FYP 浏览每切换到一条视频时，应尝试采集当前可见视频信息。

验收：

- 每条视频至少尝试采集一次。
- 采集逻辑必须是 best-effort，失败不能中断 `fyp_browse`。
- 采集超时必须短，不能明显拖慢浏览节奏。
- 采集结果必须允许部分字段为空。

推荐字段：

```text
platform
account_id
session_id
video_index
video_id
video_url
author_handle
author_name
title
description
watch_seconds
liked
followed
commented
collected_at
raw_source
capture_status
capture_error
```

### R2 标题与描述提取

系统必须优先提取用户可理解的视频标题或描述。

验收：

- 优先从当前可见视频 DOM 中读取 caption/desc/title 类内容。
- 如果 TikTok 页面标题只返回通用站点标题，不应误认为视频标题。
- 如果只拿到描述文本，应存入 `description`，并可作为 PC 端展示标题 fallback。
- 文本必须做清洗：去掉多余空白、控制字符和明显重复内容。
- 单字段长度必须限制，避免异常长文本撑爆数据库或 UI。

### R3 视频 ID 和链接

系统应尽量采集视频 ID 和视频链接。

验收：

- 当前 URL 为 `/@handle/video/<id>` 时必须解析 `video_id`。
- 如果 FYP 页面 URL 没有视频 ID，应尝试从当前视频附近的链接、分享链接或 DOM 属性提取。
- 无法提取 `video_id` 时仍可保存记录，但必须通过 `session_id + video_index` 唯一识别。
- `video_url` 必须只保存普通网页链接，不保存临时 CDP、blob、cookie 或带敏感参数的 URL。

### R4 独立明细表

视频明细必须写入独立表，不改变现有汇总表的含义。

验收：

- 新增 `fyp_video_views` 表或等价独立表。
- `action_log` 原有 `fyp_browse videos=N` 写入逻辑保持不变。
- 现有统计页依赖的 `videos`、`likes`、`follows`、`comments` 聚合结果保持不变。
- 旧数据库自动迁移，缺少新表时自动创建。
- 新表创建失败时，应记录诊断信息，但不能导致养号任务失败。

### R5 互动结果关联

如果当前视频发生点赞、关注或评论，明细记录应尽量反映最终结果。

验收：

- 当前视频点赞成功后，明细行 `liked=true`。
- 当前视频关注成功后，明细行 `followed=true`。
- 当前视频评论成功后，明细行 `commented=true`。
- 如果互动发生在采集记录之后，必须在同一轮循环内更新该视频明细。
- 如果没有可稳定匹配的 `video_id`，使用 `session_id + video_index` 更新。

### R6 桌面端查询

PC 端必须提供查询 FYP 视频明细的能力。

验收：

- Tauri 新增查询命令，例如 `query_fyp_video_views`。
- 前端类型中新增 `FypVideoViewRecord` 和筛选条件。
- 支持按平台、账号、时间范围、是否有标题、是否点赞/评论筛选。
- 默认查询限制必须有上限，避免一次拉取过多记录。

### R7 UI 展示

PC 端执行记录或统计相关页面应提供视频明细入口。

验收：

- 用户能从 PC 端看到浏览过的视频标题/描述、作者、视频链接、观看时长和互动结果。
- 视频链接应支持复制；如提供打开操作，必须走明确用户操作。
- 标题为空时显示 `未采集到标题` 或使用描述 fallback。
- 长标题在表格中折叠显示，支持展开或复制。
- 空态应说明“首次运行开启视频信息采集后的养号任务后会生成记录”。

### R8 兼容性

新增功能不能影响已有养号任务、目标号互动和统计能力。

验收：

- 未采集到标题时，FYP 浏览仍按原逻辑继续。
- 新表不存在或写入失败时，`action_log` 仍正常记录汇总。
- 旧版本数据库可直接升级。
- 旧的执行记录页面仍能显示已有动作记录。
- 现有 `query_fyp_stats` 聚合结果不从新表改算。

### R9 配置开关

视频信息采集应提供配置开关，便于风险控制。

验收：

- 默认建议开启基础采集，但必须可关闭。
- 关闭后不执行 DOM 视频信息采集，也不写入新明细表。
- 配置可放在 TikTok FYP 设置下，例如 `video_capture.enabled`。
- UI 或文档中应说明关闭后只保留会话级汇总。

推荐配置：

```yaml
tiktok:
  warmup:
    video_capture:
      enabled: true
      max_title_length: 300
      max_description_length: 600
```

### R10 数据安全

视频信息采集不得扩大敏感信息暴露面。

验收：

- 不保存 Cookie、Token、localStorage、请求头或账号登录凭据。
- 不保存完整页面 HTML。
- `capture_error` 必须经过脱敏。
- 支持包导出如包含视频标题，应在文档中明确该数据属于用户本机任务记录。

## 完成定义

- 运行 TikTok FYP 养号任务后，PC 端可以查询本次浏览过的视频明细。
- 至少部分公开视频能采集到标题或描述。
- 采集失败不会导致任务失败或统计异常。
- 原有执行记录、统计报表、目标号互动不回退。
- 新功能有明确开关、数据库迁移和 UI 查询入口。
