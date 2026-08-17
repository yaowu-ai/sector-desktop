# Comment Fetcher

Standalone Python/Playwright tools for fetching Douyin profile comments and chat conversations.

## Run Standalone

Initialize the environment from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m playwright install chromium
```

Fetch profile comments:

```powershell
.\.venv\Scripts\python .\douyin_comment_crawler.py --headed --login-prompt
```

Fetch chats:

```powershell
.\.venv\Scripts\python .\douyin_chat_crawler.py --headed --login-prompt
```

By default, runtime files stay inside this project directory:

- `comments.json`
- `chats.json`
- `.douyin-browser-profile/`
- `.douyin-chat-cookie.txt`

Use `--output`, `--user-data-dir`, or `--cookie-file` to override paths. Explicit relative paths are resolved from the current command working directory.

## Move Into Another Git Repository

Move this directory as a child project, for example:

```text
target-repo/
  tools/
    comment-fetcher/
      douyin_comment_crawler.py
      douyin_chat_crawler.py
      requirements.txt
      README.md
      .gitignore
```

After moving, the tools can still be launched from the target repository root. Default runtime files will still be written back into the `comment-fetcher` child directory:

```powershell
python .\tools\comment-fetcher\douyin_comment_crawler.py
python .\tools\comment-fetcher\douyin_chat_crawler.py
```

## Commit Checklist

Commit these files:

- `douyin_comment_crawler.py`
- `douyin_chat_crawler.py`
- `requirements.txt`
- `README.md`
- `.gitignore`

Do not commit local runtime files:

- `.douyin-cookie.txt`
- `.douyin-chat-cookie.txt`
- `.douyin-browser-profile/`
- `comments*.json`
- `chats*.json`
- `*.xlsx`
- `*.ndjson`
- `outputs/`
- `.codex_spreadsheet/`
- `.codex-build-comments-xlsx/`
- `__pycache__/`
