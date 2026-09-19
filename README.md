# 星域

星域是一个 TikTok 多账号运营工作台，提供 PC 桌面端和 Python 脚本两套入口，用于管理账号、浏览器环境、FYP 养号任务、目标号互动、自动调度、评论素材和执行统计。

当前真实自动执行能力只支持 TikTok。产品结构已预留 Instagram、WhatsApp、抖音等平台，但这些平台暂不作为生产自动化入口。

## 资源

- [星域官网](https://sector.mechlabs.cn/)
- [星域管理后台](https://sector.mechlabs.cn/dashboard)
- [Gitlab仓库地址](https://gitlab.yaowutech.cn/g-group/frontend/h-ai-labs/h-sector)
- [GitHub仓库地址](https://github.com/yaowu-ai/sector-desktop)

## 快速开始

### PC 桌面端

生产使用优先选择 Windows 安装版，不需要安装 Python，也不依赖源码仓库。

桌面端有三种常用入口：

```powershell
# 本地开发模式启动，不生成安装包
.\desktop-dev.ps1

# 测试环境安装包：前端按 test 模式构建
.\desktop-build.ps1 -BuildMode test -Python ".runtime-build-venv\Scripts\python.exe"

# 生产环境安装包：默认模式，包含 production 环境校验
.\desktop-build.ps1
```

`desktop-build.ps1` 的 `-BuildMode` 支持 `test` / `prod` / `production`，其中 `prod` 是 `production` 的别名；默认值为 `production`。生产包构建要求提供 `VITE_DESKTOP_API_BASE_URL` 和有效的 `VITE_LICENSE_PUBLIC_KEY`。

如需指定打包使用的 Python 解释器：

```powershell
.\desktop-build.ps1 -Python ".runtime-build-venv\Scripts\python.exe"
```

### Python 脚本

适用于开发、诊断或没有桌面端环境的场景。

```powershell
# 安装依赖（Python 3.13）
pip install -r requirements.txt

# 运行所有启用的 TikTok 账号
python src/main.py --platform tiktok

# 只运行一个账号
python src/main.py --platform tiktok --account tiktok_1

# 启动自动调度服务
python src/scheduler.py

# 查看统计
python src/stats.py
python src/stats.py --today
python src/stats.py --days 7
python src/stats.py --target
```

命令行 runtime 也可通过以下入口使用：

```powershell
python src/runtime_cli.py version --json
python src/runtime_cli.py diagnostic --json
python src/runtime_cli.py run --platform tiktok
```

## 核心配置

配置源为 `config/accounts.yaml`。首次使用可复制 `config/accounts.example.yaml`。

主要配置：

- `platforms.tiktok.warmup`：FYP 浏览时长、点赞概率、关注数量和评论策略。
- `platforms.tiktok.target_engagement`：目标官方号、参与账号、互动概率和关注策略。
- `platforms.tiktok.scheduler`：每日触发次数和运行时间段。
- `accounts`：账号启用状态、平台、浏览器 profile、IP 分组和班次。
- `notify`：批次结束通知，支持 ServerChan / Bark / Webhook，默认关闭。

评论素材：

- `config/comments.txt`：通用评论池。
- `config/comments_brand.txt`：品牌互动评论池。

## 目录结构

```text
config/                配置文件与评论素材
src/                   Python 自动化脚本和 runtime CLI
desktop/               PC 桌面端
runtime/               安装版运行时
data/                  运行数据（日志、数据库、锁文件）
docs/                  产品文档
```

## 常用维护命令

```powershell
# 创建绑定代理的 BitBrowser 窗口
python src/create_browser.py --name tiktok_2 --proxy "host:port:user:password"

# 创建 ixBrowser 窗口；先在 ixBrowser 中开启 Local API
python src/ix_create_browser.py --name tiktok_2 \
  --proxy "host:port:user:password"

# 创建不设置代理的 ixBrowser 窗口
python src/ix_create_browser.py --name tiktok_direct --no-proxy

# 批量读取代理文件创建窗口
python src/create_browser.py --file config/private/proxies/ip_0630

# Gmail 初始化
python src/gmail_setup.py --browser-name tiktok_25 --email account@gmail.com

# 读取 TikTok 主页统计
python src/profile_stats.py --browser-name tiktok_2

# 点赞诊断
python src/test_like.py

# 评论诊断
python src/test_comment.py
```

各脚本支持的完整参数、异常语义和边界条件请直接运行脚本查看 `--help`，或阅读源码内说明。

## 运行注意事项

- 生产使用优先在云电脑上运行，不要在本机和云电脑同时打开同一个 BitBrowser profile。
- BitBrowser 模式需要保持 BitBrowser 开启，并确保 Local API 默认可访问 `http://127.0.0.1:54345`。
- ixBrowser 模式需要保持 ixBrowser 开启并启用 Local API，默认地址为 `http://127.0.0.1:53200`。
- 使用 ixBrowser 时，在账号配置中设置 `browser_provider: ixbrowser` 和数字类型的 `browser.profile_id`。
- 同一账号的自动化动作由运行锁控制，避免调度和手动执行同时驱动同一 profile。
- 共享 IP 的账号应使用不同运行班次，避免同一 IP 下多个账号同时在线。
- 自动登录遇到验证码、二次验证或安全检查时会进入人工接管，不会自动绕过平台安全检查。
- 目标号互动建议先使用少量账号验证，确认互动留存后再逐步扩大范围。
