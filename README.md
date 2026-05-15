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
src/
  main.py                 入口：批量/单账号执行，PID 文件锁，SQLite 动作日志
  scheduler.py            定时调度服务（FastAPI lifespan + AsyncIOScheduler）
  bitbrowser.py           BitBrowser 本地 API 客户端
  actions.py              养号动作：fyp_browse / try_like / try_follow
  human_mouse.py          贝塞尔曲线模拟真人鼠标移动
  notify.py               批次结束推送（ServerChan / Bark / Webhook）
  stats.py                动作统计：按账号汇总浏览/点赞/关注次数
  test_like.py            点赞动作诊断脚本
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
python stats.py            # 全部
python stats.py --today    # 今天
python stats.py --days 7   # 近 7 天

# 点赞动作诊断（浏览器已打开时也可用）
python test_like.py
```

### 定时调度

```bash
cd src
python scheduler.py
```

启动后每天 00:05 在 `active_hours` 内随机生成 `fires_per_day` 个触发时间，
每次触发执行一遍所有启用账号。服务监听 `127.0.0.1:9601`：

- `GET /health` — 查看已排期的触发时间、锁状态
- 触发前自动探测 BitBrowser API，不可达则跳过本次

调度与手动 `python main.py` 通过 `data/run.lock` 互斥，不会同时跑。

## 通知（可选）

`config/accounts.yaml` 的 `notify` 段默认关闭。开启后每批结束推送 OK/ERR 摘要，
支持 ServerChan / Bark / 通用 Webhook。

## 注意

- profile **同一时间只能在一台机器打开**，切勿本机与云电脑同时登录同一 BitBrowser 账号。
