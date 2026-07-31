import os
import sqlite3
import sys
import types
from pathlib import Path
import shutil
import uuid


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from browser_providers import bitbrowser_profile_id, builtin_user_data_dir
from core import runtime
from platforms.registration.base import RegistrationStatus
from platforms.registration.browser_session import close_registration_browser
from platforms.registration.cookies import persist_registration_session, session_profile_detail
from platforms.registration.random_identity import (
    generate_unique_username,
    load_username_registry,
    random_birthday,
    random_username,
    record_username,
)
from auth_adapters import LoginState
from platforms.tiktok import auth as tiktok_auth
from platforms.tiktok import register as tiktok_register


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    def count(self):
        return 1 if self._visible() else 0

    def nth(self, _index):
        return self

    def is_visible(self, timeout=0):
        return self._visible()

    def fill(self, value, timeout=0):
        self.page.filled.append(value)

    def click(self, timeout=0):
        self.page.clicked.append(self.selector)
        if 'button:has-text("Next")' in self.selector:
            self.page.state = "username"
        if 'button:has-text("Sign up")' in self.selector:
            self.page.submitted += 1

    def select_option(self, label=None, value=None, timeout=0):
        choice = label or value
        if "Month" in self.selector:
            self.page.selected["month"] = choice
        elif "Day" in self.selector:
            self.page.selected["day"] = choice
        elif "Year" in self.selector:
            self.page.selected["year"] = choice
        else:
            raise RuntimeError("not a birthday selector")

    def inner_text(self, timeout=0):
        if self.page.state == "birthday":
            return "When's your birthday? Month Day Year"
        if self.page.state == "username":
            return "Create username Sign up"
        if self.page.state == "logged_in":
            return "For You Profile Upload"
        if self.page.state == "google_one_tap":
            return "For You Profile Upload Sign in to tiktok.com with google.com Continue as Kyle"
        if self.page.state == "interest_onboarding":
            return "For You Profile Upload What would you like to watch on TikTok? Continue (0/3) Log in"
        return "For You"

    def _visible(self):
        selector = self.selector
        if selector == "body":
            return True
        if self.page.state == "birthday":
            return (
                "birthday" in selector
                or "Month" in selector
                or "Day" in selector
                or "Year" in selector
                or 'button:has-text("Next")' in selector
            )
        if self.page.state == "username":
            return "username" in selector.lower() or 'button:has-text("Sign up")' in selector
        if self.page.state in {"logged_in", "google_one_tap", "interest_onboarding"}:
            if selector in ('[data-e2e="profile-icon"]', '[data-e2e="nav-profile"]'):
                return True
        if self.page.state == "google_one_tap":
            return "Continue as" in selector or "Sign in to tiktok" in selector
        if self.page.state == "interest_onboarding":
            return "What would you like" in selector or "Continue (0/3)" in selector or "Log in" in selector
        return False


class FakeContext:
    def __init__(self):
        self.storage_state_calls = 0

    def storage_state(self):
        self.storage_state_calls += 1
        return {"cookies": [{"name": "sid", "value": "secret-cookie"}]}


class FakePage:
    url = "https://www.tiktok.com/signup"

    def __init__(self, state="birthday"):
        self.state = state
        self.selected = {}
        self.filled = []
        self.clicked = []
        self.submitted = 0
        self.context = FakeContext()

    def locator(self, selector):
        return FakeLocator(self, selector)

    def wait_for_load_state(self, *_args, **_kwargs):
        return None

    def evaluate(self, *_args, **_kwargs):
        return self.locator("body").inner_text()


class FakeProvider:
    name = "builtin_chromium"

    def __init__(self, close_result=None, close_error=None):
        self.close_result = close_result
        self.close_error = close_error
        self.closed = 0

    def close_session(self, _session, _config):
        self.closed += 1
        if self.close_error:
            raise self.close_error
        return self.close_result


def memory_db():
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
    conn.commit()
    return conn


def logged_actions(conn):
    return conn.execute("SELECT action, status, detail FROM action_log ORDER BY id").fetchall()


def fake_browser(provider=None, already_open=False, user_data_dir=None):
    session = types.SimpleNamespace(
        provider="builtin_chromium",
        account_id="acct_1",
        profile_id="acct_1",
        cdp_endpoint="http://127.0.0.1:9333",
        already_open=already_open,
        process_id=123,
        user_data_dir=user_data_dir,
    )
    return types.SimpleNamespace(
        provider=provider or FakeProvider(types.SimpleNamespace(status="closed", detail="closed fake")),
        session=session,
        profile_id="acct_1",
    )


def assert_random_identity_and_registry():
    for _ in range(250):
        birthday = random_birthday()
        assert birthday["year"] < 2006
        assert 1 <= birthday["month"] <= 12
        assert 1 <= birthday["day"] <= 31
        username = random_username(15)
        assert len(username) == 15
        assert username.isalnum()

    account = {"id": "acct_1"}
    record_username("Abc123Abc123999", account)
    assert load_username_registry("tiktok")[-1]["account_id"] == "acct_1"
    assert generate_unique_username("tiktok") != "Abc123Abc123999"


def assert_tiktok_birthday_and_username_steps(conn):
    page = FakePage("birthday")
    birthday = {"year": 2005, "month": 2, "day": 28}
    username, result = tiktok_register.run_tiktok_signup_steps(
        page,
        {"id": "acct_1"},
        conn,
        "tiktok",
        birthday,
        "Aa1234567890BbC",
    )

    assert result is None
    assert username == "Aa1234567890BbC"
    assert page.selected == {"month": "February", "day": "28", "year": "2005"}
    assert page.filled == ["Aa1234567890BbC"]
    assert page.submitted == 1
    actions = logged_actions(conn)
    assert any(action == "register_birthday" and status == "ok" for action, status, _ in actions)
    assert any(action == "register_username" and status == "ok" for action, status, _ in actions)


def assert_username_retries(conn):
    page = FakePage("username")
    original_wait = tiktok_register.wait_for_username_unavailable
    original_generate = tiktok_register.generate_unique_username
    unavailable = [True, True, False]
    generated = iter(["RetryUser000001", "RetryUser000002"])
    try:
        tiktok_register.wait_for_username_unavailable = lambda _page: unavailable.pop(0)
        tiktok_register.generate_unique_username = lambda _platform: next(generated)
        username = tiktok_register.submit_tiktok_username(
            page,
            {"id": "acct_1"},
            conn,
            "tiktok",
            "FirstUser000001",
        )
    finally:
        tiktok_register.wait_for_username_unavailable = original_wait
        tiktok_register.generate_unique_username = original_generate

    assert username == "RetryUser000002"
    assert page.filled == ["FirstUser000001", "RetryUser000001", "RetryUser000002"]
    assert page.submitted == 3
    assert any(
        action == "register_username" and status == "retry"
        for action, status, _ in logged_actions(conn)
    )


def assert_session_save_and_browser_close(conn, data_dir):
    page = FakePage("done")
    browser = fake_browser(user_data_dir=str(data_dir / "browser" / "builtin_chromium" / "acct_1" / "user-data"))
    assert persist_registration_session(page, {"id": "acct_1"}, {}, conn, "tiktok", browser)
    assert page.context.storage_state_calls == 1
    detail = session_profile_detail(browser)
    assert "builtin_chromium" in detail
    assert "user_data_dir=" in detail

    close_result = close_registration_browser(browser, {}, "tiktok", "acct_1", conn)
    assert close_result is True
    already_open_provider = FakeProvider()
    already_open = fake_browser(provider=already_open_provider, already_open=True)
    assert close_registration_browser(already_open, {}, "tiktok", "acct_1", conn) is None
    assert already_open_provider.closed == 0

    failing = fake_browser(provider=FakeProvider(close_error=RuntimeError("close failed")))
    assert close_registration_browser(failing, {}, "tiktok", "acct_1", conn) is False
    assert any("REGISTER_BROWSER_CLOSE_FAILED" in detail for _, _, detail in logged_actions(conn))


def assert_complete_result_preserves_success_on_close_failure(conn):
    page = FakePage("done")
    original_detect = tiktok_register.detect_registration_complete
    tiktok_register.detect_registration_complete = lambda _page, _account_id: True
    try:
        result = tiktok_register.complete_registration_result(
            page,
            fake_browser(provider=FakeProvider(close_error=RuntimeError("close failed"))),
            {"id": "acct_1"},
            {},
            conn,
            "tiktok",
            "FinalUser000001",
            "done",
        )
    finally:
        tiktok_register.detect_registration_complete = original_detect

    assert result.status == RegistrationStatus.COMPLETE
    assert result.browser_closed is False
    assert "browser close failed" in result.detail
    assert any(action == "register_complete" and status == "ok" for action, status, _ in logged_actions(conn))


def assert_strict_tiktok_auth_blocks_incomplete_sessions():
    logged_in = tiktok_auth.classify_tiktok_page(FakePage("logged_in"), account_id="acct_1")
    one_tap = tiktok_auth.classify_tiktok_page(FakePage("google_one_tap"), account_id="acct_1")
    onboarding = tiktok_auth.classify_tiktok_page(FakePage("interest_onboarding"), account_id="acct_1")

    assert logged_in.state == LoginState.LOGGED_IN
    assert one_tap.state == LoginState.LOGGED_OUT
    assert "Google one-tap" in one_tap.detail
    assert onboarding.state == LoginState.LOGGED_OUT
    assert "onboarding" in onboarding.detail


def assert_existing_google_account_skips_email_entry():
    conn = memory_db()
    original_select = tiktok_register.select_existing_google_account
    original_first_visible = tiktok_register.first_visible_locator
    try:
        tiktok_register.select_existing_google_account = lambda *_args, **_kwargs: (True, None)

        def fail_if_email_branch_runs(*_args, **_kwargs):
            raise AssertionError("email input should not be queried after choosing an existing Google account")

        tiktok_register.first_visible_locator = fail_if_email_branch_runs
        result = tiktok_register.run_google_login_flow(
            FakePage("done"),
            FakePage("done"),
            {"id": "acct_1"},
            types.SimpleNamespace(username="user@example.com", password="secret"),
            conn,
            "tiktok",
        )
    finally:
        tiktok_register.select_existing_google_account = original_select
        tiktok_register.first_visible_locator = original_first_visible
        conn.close()

    assert result is None


def assert_profiles_and_redaction(data_dir):
    assert bitbrowser_profile_id({"browser": {"profile_id": "bb_profile_1"}}) == "bb_profile_1"
    user_data = builtin_user_data_dir({"id": "acct_1", "browser": {"provider": "builtin_chromium"}})
    assert str(user_data).startswith(str(data_dir))
    assert str(user_data).endswith(os.path.join("browser", "builtin_chromium", "acct_1", "user-data"))

    redacted = runtime.redact_runtime_text(
        "password=abc credential:def proxy_password=ghi token=jkl cookie=mno session=pqr proxy=http://u:p@h:1"
    )
    for secret in ("abc", "def", "ghi", "jkl", "mno", "pqr"):
        assert secret not in redacted
    assert "http://u:***@h:1" in redacted


def main():
    tmp_path = Path(__file__).resolve().parent / ".m14-temp" / f"run-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True)
    data_dir = tmp_path / "data"
    config_path = tmp_path / "accounts.yaml"
    config_path.write_text("accounts: []\n", encoding="utf-8")
    os.environ["AM_DATA_DIR"] = str(data_dir)
    runtime.configure_runtime(config_path)
    conn = memory_db()
    try:
        assert_random_identity_and_registry()
        assert_tiktok_birthday_and_username_steps(conn)
        assert_username_retries(conn)
        assert_session_save_and_browser_close(conn, data_dir)
        assert_complete_result_preserves_success_on_close_failure(conn)
        assert_strict_tiktok_auth_blocks_incomplete_sessions()
        assert_existing_google_account_skips_email_entry()
        assert_profiles_and_redaction(data_dir)
    finally:
        conn.close()
        os.environ.pop("AM_DATA_DIR", None)
        shutil.rmtree(tmp_path, ignore_errors=True)

    print("M14 Python registration acceptance checks passed")


if __name__ == "__main__":
    main()
