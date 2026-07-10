# douyin-fetcher 使用说明

`douyin-fetcher` 是一组基于 Playwright 的抖音数据采集脚本，用于在本地浏览器环境中采集：

- 用户主页的视频列表、评论与评论回复
- 抖音私信会话、私信用户信息与已加载消息内容

脚本默认使用有界面的 Chromium，并复用本目录下的浏览器登录态目录 `.douyin-browser-profile/`。首次运行通常需要手动登录抖音。

## 目录结构

```text
src/douyin-fetcher/
├── douyin_comment_crawler.py  # 主页视频、评论、回复采集
├── douyin_chat_crawler.py     # 私信会话和消息采集
├── requirements.txt           # Python 依赖
└── README.md                  # 本说明文件
```

## 环境准备

建议使用 Python 3.10+。

```bash
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

如果不使用虚拟环境，也可以直接执行依赖安装命令。

## 采集评论

默认采集脚本内置的抖音主页地址，输出到本目录的 `comments.json`。

```bash
python douyin_comment_crawler.py
```

采集指定主页：

```bash
python douyin_comment_crawler.py --profile-url "https://www.douyin.com/user/xxx?from_tab_name=main"
```

只采集视频列表，不进入评论：

```bash
python douyin_comment_crawler.py --videos-only
```

限制采集范围：

```bash
python douyin_comment_crawler.py --max-videos 20 --max-comments-per-video 100
```

重新打开已存在评论的视频并按评论 `cid` 合并：

```bash
python douyin_comment_crawler.py --refetch-existing-comments
```

常用参数：

- `--profile-url`：抖音用户主页 URL。
- `--output`：输出 JSON 路径，默认 `comments.json`。
- `--user-data-dir`：浏览器登录态目录，默认 `.douyin-browser-profile/`。
- `--headed` / `--headless`：显示或隐藏 Chromium 窗口，默认显示。
- `--login-prompt` / `--no-login-prompt`：打开页面后是否等待手动登录，默认等待。
- `--max-videos`：最多采集的视频数，`0` 表示不主动限制。
- `--max-comments-per-video`：每个视频最多采集的评论与回复总数，`0` 表示不主动限制。
- `--videos-only`：只采集主页视频列表。
- `--no-replies`：跳过评论回复。

## 采集私信

默认打开抖音私信页，输出到本目录的 `chats.json`。

```bash
python douyin_chat_crawler.py
```

首次运行建议使用有界面模式，手动确认登录状态：

```bash
python douyin_chat_crawler.py --headed --login-prompt
```

只采集私信用户信息，不采集消息内容：

```bash
python douyin_chat_crawler.py --users-only
```

采集用户信息并尝试采集已加载会话内容：

```bash
python douyin_chat_crawler.py --with-content
```

限制会话数量并重新生成输出：

```bash
python douyin_chat_crawler.py --max-conversations 30 --fresh
```

常用参数：

- `--chat-url`：抖音私信页 URL，默认 `https://www.douyin.com/chat?isPopup=1`。
- `--output`：输出 JSON 路径，默认 `chats.json`。
- `--cookie-file`：Cookie 文件路径，默认 `.douyin-chat-cookie.txt`。
- `--user-data-dir`：浏览器登录态目录，默认 `.douyin-browser-profile/`。
- `--headed` / `--headless`：显示或隐藏 Chromium 窗口，默认显示。
- `--login-prompt` / `--no-login-prompt`：是否等待手动登录，私信脚本默认不等待。
- `--login-wait-seconds`：需要登录时等待指定秒数，而不是等待回车。
- `--max-conversations`：最多采集会话数，`0` 表示不主动限制。
- `--fresh`：忽略已有 `chats.json`，重新采集。
- `--users-only`：只采集用户信息。
- `--with-content`：同时尝试采集消息内容。
- `--coordinate-clicks` / `--dom-clicks`：选择通过坐标或 DOM 点击会话行，默认坐标点击。
- `--debug-responses`：打印解析到的相关响应 URL，便于排查。

## Cookie 与登录态

评论脚本主要依赖 `.douyin-browser-profile/` 保存登录态。私信脚本还会尝试读取 `.douyin-chat-cookie.txt`，支持普通 Cookie header 或 Netscape cookie 文件格式。

私信 Cookie 文件示例：

```text
sessionid=xxx; passport_csrf_token=xxx; sid_guard=xxx
```

这些文件包含账号凭据，不要提交到 Git。当前 `.gitignore` 已忽略：

- `.douyin-chat-cookie.txt`
- `.douyin-*-cookie.txt`
- `.douyin-browser-profile/`
- `comments.json`
- `chats.json`
- `outputs/`

## 输出说明

评论采集默认输出 `comments.json`，主要包含视频信息和每个视频下的 `comment` 列表；评论回复会写入对应评论的 `sub-comment` 字段。

私信采集默认输出 `chats.json`，主要包含会话用户信息和 `content` 消息列表。脚本会在运行过程中持续合并已有输出，浏览器中途关闭时也会尽量保存已采集数据。

## 常见问题

如果提示缺少 Playwright：

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

如果没有采集到数据，优先检查：

- 浏览器是否已登录抖音账号。
- 页面是否出现登录弹窗、风控提示或验证码。
- 目标主页或私信页是否能在浏览器中正常打开。
- 是否需要改用 `--headed --login-prompt` 手动登录后再运行。
- 是否需要降低采集量，例如先加 `--max-videos 5` 或 `--max-conversations 5` 验证流程。

## 合规提醒

请仅在拥有合法权限的账号和数据范围内使用本工具，遵守抖音平台规则、隐私要求和所在地区法律法规。不要采集、保存或传播无授权的敏感信息。
