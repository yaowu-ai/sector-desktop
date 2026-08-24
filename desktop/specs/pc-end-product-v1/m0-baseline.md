# M0 准备与脚本基线

记录时间：2026-07-20 10:31（Asia/Shanghai）

## 验证结论

- 当前分支：`feat/PC-end-product`。
- 推荐脚本解释器：`py -3.13`，对应 `Python 3.13.0`。
- 当前 `python` 指向 Anaconda `Python 3.12.7`，不作为桌面端默认基线。
- 依赖安装方式：`py -3.13 -m pip install -r requirements.txt`。
- Python 3.13 依赖已按 `requirements.txt` 安装，`py -3.13 -m pip check` 通过。
- `config/accounts.yaml` 中 BitBrowser Local API 地址为 `http://127.0.0.1:54345`。
- 当前机器 `127.0.0.1:54345` 未监听，`Test-NetConnection` 结果为 `TcpTestSucceeded: False`。
- `py -3.13 src/stats.py` 可执行，无数据时正常输出空统计。
- `py -3.13 src/main.py --account tiktok_1` 可进入脚本流程并写入 `data/sessions.log` / `data/actions.db`，但因 BitBrowser Local API 未开启，执行在 `/browser/open` 阶段失败。
- 在受限 sandbox 内直接写 SQLite 会触发 `sqlite3.OperationalError: disk I/O error`；提升权限后最小 SQLite 写入和 `main.py` 写库均可执行。桌面端后续实现应将 SQLite 写入视为真实本地文件写入前置能力。

## 已执行命令

```powershell
git status --short --branch
python --version
py -0p
py -3.13 --version
py -3.13 -m pip install -r requirements.txt
py -3.13 -m pip check
Test-NetConnection 127.0.0.1 -Port 54345
py -3.13 src\stats.py
py -3.13 src\stats.py --target
py -3.13 src\main.py --account tiktok_1
```

`main.py --account tiktok_1` 关键输出：

```text
BATCH START | 1 account(s)
tiktok_1 | START | target=3.6min like_p=0.35 follows_max=1 comments_max=1
tiktok_1 | ERROR | ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=54345) ...
BATCH END | [ERR] TikTok bot: 0/1 OK, 1 failed
```

## 脚本入口基线

| 脚本 | 入口 | 参数 | 主要输出 |
| --- | --- | --- | --- |
| `src/main.py` | `py -3.13 src/main.py` | `--account <account_id>`；不传则运行全部 enabled 账号 | stdout、`data/sessions.log`、`data/actions.db` 的 `action_log` / `target_engagements` / `target_follows` |
| `src/stats.py` | `py -3.13 src/stats.py` | `--today`、`--days <n>`、`--target` | stdout 表格统计；无数据时输出 `(no data yet)` 或 `(no target engagement yet)` |
| `src/scheduler.py` | `py -3.13 src/scheduler.py` | 无 CLI 参数；启动 FastAPI/uvicorn，监听 `127.0.0.1:9601` | HTTP `/health`，stdout 服务日志 |
| `src/create_browser.py` | `py -3.13 src/create_browser.py` | `--name`、`--proxy`、`--file`、`--prefix`、`--type {http,https,socks5}`、`--api-url`、`--group-id`、`--skip-check`、`--skip-used` | stdout 创建结果；调用 BitBrowser `/browser/update`、`/checkagent`、`/browser/list` |
| `src/sync_accounts_config.py` | `py -3.13 src/sync_accounts_config.py` | `--config`、`--api-url`、`--prefix`、`--start`、`--end`、`--morning-start`、`--morning-end`、`--evening-start`、`--evening-end`、`--first-ip-group`、`--dry-run` | stdout dry-run 或写回 `config/accounts.yaml` |
| `src/gmail_setup.py` | `py -3.13 src/gmail_setup.py` | `--browser-name`、`--file`、`--query`、`--email`、`--password`、`--password-env`、`--ask-password`、`--new-password`、`--new-password-env`、`--ask-new-password`、`--api-url`、`--timeout`、`--terms-timeout`、`--keep-open-on-error` | stdout 步骤日志；打开 BitBrowser profile 并执行 Gmail 初始化 |
| `src/test_like.py` | `py -3.13 src/test_like.py` | `--account`，默认 `tiktok_1` | stdout 点赞诊断过程和结果 |
| `src/test_comment.py` | `py -3.13 src/test_comment.py` | `--account`，`--min`，`--no-post`，`--max-scroll` | stdout 评论诊断过程、选择器 HTML 片段和发布结果 |

## M1 前置注意

- 桌面端默认 Python 命令建议先配置为 `py -3.13` 或完整路径 `C:\Users\Aili\AppData\Local\Programs\Python\Python313\python.exe`，不要直接使用当前 PATH 中的 `python`。
- 启动真实任务前必须检测 BitBrowser Local API，否则当前状态会稳定失败。
- `data/` 当前由 M0 验证生成，包含 `actions.db` 和 `sessions.log`；`run.lock` 已确认释放。
