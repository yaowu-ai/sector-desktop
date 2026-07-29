import contextlib
import io
import os
import shutil
import sqlite3
import sys
import types
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if "requests" not in sys.modules:
    fake_requests = types.ModuleType("requests")

    def _post(*_args, **_kwargs):
        return types.SimpleNamespace(ok=True)

    fake_requests.post = _post
    sys.modules["requests"] = fake_requests

from core import runtime, runner
from platform_config import target_engagement_config, warmup_config
from platforms import registry
from platforms.base import PlatformRunner

FAKE_RUNS = []


class FakeTikTokRunner(PlatformRunner):
    platform = "tiktok"
    executable = True

    def run_session(self, account, config, conn):
        assert account["platform"] == "tiktok"
        assert warmup_config(config, "tiktok")["like_probability"] == 0.5
        assert target_engagement_config(config, "tiktok")["handles"] == ["brand_one"]
        runtime.log_action(conn, "tiktok", account["id"], "session", "ok", "fake runner")
        FAKE_RUNS.append((account["id"], account["platform"]))
        return {
            "account_id": account["id"],
            "platform": "tiktok",
            "status": "ok",
            "videos": 1,
            "likes": 1,
            "follows": 0,
            "comments": 0,
            "target_videos": 0,
            "target_likes": 0,
            "target_comments": 0,
            "target_follows": 0,
            "duration_actual_min": 0.0,
            "error": None,
        }


def create_memory_db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            account_id TEXT,
            action TEXT,
            status TEXT,
            detail TEXT,
            ts TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE target_engagements (
            platform TEXT NOT NULL,
            our_account TEXT,
            handle TEXT,
            video_id TEXT,
            liked INTEGER,
            commented INTEGER,
            ts TEXT,
            PRIMARY KEY (platform, our_account, handle, video_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE target_follows (
            platform TEXT NOT NULL,
            our_account TEXT,
            handle TEXT,
            followed INTEGER,
            ts TEXT,
            PRIMARY KEY (platform, our_account, handle)
        )
        """
    )
    conn.commit()
    return conn


def write_legacy_config(path):
    path.write_text(
        """
bitbrowser:
  api_url: http://127.0.0.1:54345
defaults:
  daily_actions:
    fyp_browse_minutes: [1, 2]
    like_probability: 0.5
    follows_per_session: [0, 1]
target_accounts:
  enabled: true
  handles: [brand_one]
  participants: [acct_1]
  first_run_latest_n: 1
  max_videos_per_run: 1
  like_probability: 0.9
  comment_probability: 0.4
  comments_file: comments_brand.txt
  follow: false
  follow_probability: 0.0
accounts:
  - id: acct_1
    enabled: true
    bitbrowser_profile_id: profile_1
    active_hours: [[9, 12]]
  - id: ig_1
    platform: instagram
    enabled: true
    bitbrowser_profile_id: profile_ig_1
    active_hours: [[9, 12]]
notify:
  enabled: false
""".strip()
        + "\n",
        encoding="utf-8",
    )


def assert_tiktok_legacy_config_runs(config_path):
    original_runner = registry._RUNNERS["tiktok"]
    original_init_db = runtime.init_db
    original_session_log = runtime.session_log
    registry._RUNNERS["tiktok"] = FakeTikTokRunner()
    runtime.init_db = create_memory_db
    runtime.session_log = lambda line, platform="tiktok": print(f"{platform} | {line}")
    FAKE_RUNS.clear()
    try:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runner.run(account_id="acct_1")
        assert "BATCH START" in output.getvalue()
        assert FAKE_RUNS == [("acct_1", "tiktok")]
    finally:
        registry._RUNNERS["tiktok"] = original_runner
        runtime.init_db = original_init_db
        runtime.session_log = original_session_log


def assert_instagram_reserved_does_not_start():
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = runner.run(account_id="ig_1")

    text = output.getvalue()
    assert result is None
    assert "platform=instagram is reserved" in text
    assert "no executable instagram accounts to run" in text


def main():
    tmp_path = Path(__file__).resolve().parent / ".m14-temp" / f"run-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True)
    try:
        config_path = tmp_path / "accounts.yaml"
        write_legacy_config(config_path)
        os.environ["AM_DATA_DIR"] = str(tmp_path / "data")
        runtime.configure_runtime(config_path)

        config = runtime.load_config()
        assert config["accounts"][0]["platform"] == "tiktok"
        assert warmup_config(config, "tiktok")["like_probability"] == 0.5
        assert target_engagement_config(config, "tiktok")["handles"] == ["brand_one"]

        assert_tiktok_legacy_config_runs(config_path)
        assert_instagram_reserved_does_not_start()
    finally:
        os.environ.pop("AM_DATA_DIR", None)
        shutil.rmtree(tmp_path, ignore_errors=True)

    print("M14 python integration checks passed")


if __name__ == "__main__":
    main()
