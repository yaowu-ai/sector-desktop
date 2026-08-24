import sys
import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auth_adapters import LoginState
from platforms.registration.base import RegistrationResult, RegistrationStatus
from platforms.tiktok import runner as runner_module


class TikTokRegistrationStatusTests(unittest.TestCase):
    def test_completed_registration_records_logged_in_status(self):
        adapter = Mock()
        adapter.register.return_value = RegistrationResult(
            platform="tiktok",
            account_id="tiktok_nz1",
            status=RegistrationStatus.COMPLETE,
            detail="TikTok registration completed and session saved",
            username="registered-user",
            browser_closed=True,
        )

        with (
            patch.object(runner_module, "adapter_for_platform", return_value=adapter),
            patch.object(runner_module, "log_action") as log_action,
            patch.object(runner_module, "session_log"),
        ):
            summary = runner_module.run_tiktok_registration(
                {"id": "tiktok_nz1", "platform": "tiktok"},
                {},
                Mock(),
            )

        self.assertEqual(summary["status"], "ok")
        log_action.assert_any_call(
            ANY,
            "tiktok",
            "tiktok_nz1",
            "login_check",
            LoginState.LOGGED_IN.value,
            "registration completed and browser session saved",
        )


if __name__ == "__main__":
    unittest.main()
