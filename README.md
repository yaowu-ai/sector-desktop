# account-matrix

TikTok 多账号养号自动化脚本。在云电脑上通过比特浏览器（指纹隔离）+ 住宅 IP 模拟真人行为，
对账号执行 FYP 浏览 / 点赞 / 关注等动作，支持定时调度与动作统计。

> 项目背景与整体方案见 [`tiktok_matrix_proposal_v1.md`](./tiktok_matrix_proposal_v1.md)。
> 规模目标：2 → 10 → 1000+ 账号。

## 架构

```
云电脑 (Windows)
├── 梯子 (Clash, TUN 模式)        — 内网穿透到 IPRoyal 住宅 IP
├── BitBrowser 比特浏览器           — 指纹隔离，每号一个 profile + 一个住宅 IP
│   └── 本地 API :54345           — open/close/pids
└── account-matrix (本仓库)
    ├── patchright                — 反检测版 Playwright，connect_over_cdp 接管浏览器
    ├── main.py                   — 单次批量执行所有启用账号
    └── scheduler.py              — FastAPI + APScheduler 定时调度
```

一个账号动作执行完即关闭浏览器，再执行下一个；文件锁保证**同一时间只操作一个账号**。

## 目录结构

```
config/accounts.yaml      账号与行为配置（唯一配置源）
config/comments.txt       FYP 默认评论池（每行一条，可自由增删）
config/comments_brand.txt 品牌向评论池（目标号互动用）
src/
  main.py                 入口：批量/单账号执行，PID 文件锁，SQLite 动作日志
  scheduler.py            定时调度服务（FastAPI lifespan + AsyncIOScheduler）
  bitbrowser.py           BitBrowser 本地 API 客户端
  actions.py              养号动作：fyp_browse / try_like / try_follow / try_comment
  target_engage.py        目标号互动：抓新视频 + 点赞/评论自家品牌官方号
  human_mouse.py          贝塞尔曲线模拟真人鼠标移动
  notify.py               批次结束推送（ServerChan / Bark / Webhook）
  stats.py                动作统计：按账号汇总浏览/点赞/关注/评论次数
  test_like.py            点赞动作诊断脚本
  test_comment.py         评论动作诊断脚本（dump 选择器 + 试发评论）
data/                     运行时生成（已 gitignore）
  actions.db              SQLite 动作日志
  sessions.log            可读的会话日志
  run.lock                PID 锁文件
```

## 环境准备

仅在**云电脑**上运行，本机不登录 TikTok / 不开 BitBrowser。

1. 云电脑装好 Clash（TUN 模式）、BitBrowser，并在 BitBrowser 里为账号配好住宅 IP 代理后再生成指纹。
2. Python 3.13，安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. BitBrowser 应用保持开启（脚本依赖其本地 API `127.0.0.1:54345`）。

## 配置

编辑 `config/accounts.yaml`：

```yaml
defaults:
  daily_actions:
    fyp_browse_minutes: [2, 5]     # 单次 FYP 浏览时长范围（分钟）
    like_probability: 0.35         # 每个视频点赞概率
    follows_per_session: [0, 1]    # 每 session 关注数上限
    comment:
      enabled: true
      comments_per_session: [1, 2]   # 每 session 评论数上限（最多 1~2 条）
      min_video_comments: 1000       # 仅评论“评论数 > 此值”的视频
      probability: 0.25              # 命中候选视频后，单视频尝试评论的概率
  active_hours: [[9, 12], [19, 23]]
  timezone: America/New_York

scheduler:
  fires_per_day: 3                 # 每天在 active_hours 内随机触发次数

accounts:
  - id: tiktok_1
    enabled: true
    bitbrowser_profile_id: "比特浏览器的 profile ID"
    notes: "测试号 #1"
```

新增账号 = 在 `accounts:` 下加一项；临时停用某号设 `enabled: false`。

## 使用

```bash
cd src

# 单次执行所有启用账号（账号间随机间隔 30-120s）
python main.py

# 只跑某一个账号
python main.py --account tiktok_1

# 查看统计
python stats.py            # 全部（FYP 浏览/点赞/关注/评论）
python stats.py --today    # 今天
python stats.py --days 7   # 近 7 天
python stats.py --target           # 目标号互动汇总（按号 + 按目标）
python stats.py --target --today   # 今天的目标号互动（可配合 --today/--days）

# 点赞动作诊断（浏览器已打开时也可用）
python test_like.py

# 评论动作诊断：找高评论视频、dump 选择器 HTML、试发评论
python test_comment.py                  # 找 >1000 评论的视频并试发
python test_comment.py --min 100 --no-post   # 调低门槛、只定位不发评论
```

> 评论池在 `config/comments.txt`，每行一条。养号阶段仅评论“评论数 > `min_video_comments`”
> 的高流量视频，每 session 最多 1~2 条，降低被判垃圾评论的风险。

### 目标号互动（捧场自家品牌）

让 `participants` 里的号每次 session **先刷 FYP，再去检查目标官方号有没有新视频**，
按概率点赞/评论。配置在 `accounts.yaml` 的 `target_accounts` 段：

```yaml
target_accounts:
  enabled: true
  handles: [mechlinkthai2025, mechlink_indonesia, mechlink0]   # 目标官方号
  participants: [tiktok_6, ..., tiktok_15]   # 执行号（10 个）
  first_run_latest_n: 1       # 无记录时只处理最新 1 条
  max_videos_per_run: 3       # 单次单目标最多处理几条新视频
  like_probability: 0.9
  comment_probability: 0.5    # 不强制全员评论，打散抱团
  comments_file: comments_brand.txt
```

**判新机制**：抓目标号主页每条视频 URL 里的 `video_id`（雪花号，越大越新），
与 SQLite `target_engagements` 表里的水位线（该号对该目标已处理过的最大 id）比对，
`id > 水位线` 才算新。置顶旧视频因 id 较小不会被误判为新。某号对某目标**无记录时
只处理最新 1 条**作为起点，之后每天自然跟进新发布的，同一天多次触发不会重复处理。

> ⚠️ 10 个号集中给同一品牌点赞/评论本质是「互动抱团」，是平台重点打击对象。
> 已内置缓解：点赞/评论各自独立按概率（非全员）、班次错峰、每次先刷 FYP 混淆。
> **建议先用 2~3 个号灰度 2~3 天，确认点赞/评论留存（没被限流回滚）再扩到 10 个。**

### 定时调度

```bash
cd src
python scheduler.py
```

启动后每天 00:05 为**每个账号**在它自己的 `active_hours` 内随机生成 `fires_per_day`
个触发时间，每次只跑那一个账号。服务监听 `127.0.0.1:9601`：

- `GET /health` — 查看已排期的触发时间、锁状态
- 触发前自动探测 BitBrowser API，不可达则跳过本次
- 进程内串行：同一时刻只驱动一个 profile（`session_lock`）
- 调度与手动 `python main.py` 通过 `data/run.lock` 互斥，不会同时跑

**共享 IP 错峰（班次模型）**：20 号 / 10 IP 时，每个 IP 挂 2 个号——一个排上午班
`[[9,12]]`、一个排晚上班 `[[19,23]]`。两班次时间不重叠，所以同一 IP 的两个号绝不会
同时在线（隔离靠 `active_hours` 错班，配合进程内 `session_lock` 串行执行）。

- `ip_group`：同一个 IP 的两个号填相同字母（A~J），**仅用于启动校验**——若同 IP 的
  两个号被排进重叠的 `active_hours`，scheduler 启动时会告警。
- `active_hours`：决定账号属于哪个班次。
> 默认 `accounts.yaml` 已是 20 号 / 2 班次模板，仅 `tiktok_1` 启用；填好各号的
> `bitbrowser_profile_id` 并把 `enabled` 改 `true` 即可逐个上线。

## 通知（可选）

`config/accounts.yaml` 的 `notify` 段默认关闭。开启后每批结束推送 OK/ERR 摘要，
支持 ServerChan / Bark / 通用 Webhook。

## 注意

- profile **同一时间只能在一台机器打开**，切勿本机与云电脑同时登录同一 BitBrowser 账号。
