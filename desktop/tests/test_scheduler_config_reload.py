import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from apscheduler.schedulers.asyncio import AsyncIOScheduler


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import scheduler as scheduler_module


class SchedulerConfigReloadTests(unittest.TestCase):
    def setUp(self):
        self.original_scheduler = scheduler_module.scheduler
        self.original_fingerprint = scheduler_module.config_fingerprint
        scheduler_module.scheduler = AsyncIOScheduler()
        scheduler_module.config_fingerprint = None

    def tearDown(self):
        scheduler_module.scheduler = self.original_scheduler
        scheduler_module.config_fingerprint = self.original_fingerprint

    def test_rebuild_removes_orphaned_account_jobs(self):
        future = datetime.now() + timedelta(hours=1)
        scheduler_module.scheduler.add_job(
            scheduler_module.account_session_task,
            trigger="date",
            run_date=future,
            id="fire_tiktok_109_20260803_090400",
            args=["tiktok_109"],
        )
        config = {
            "accounts": [
                {
                    "id": "tiktok_101",
                    "platform": "tiktok",
                    "enabled": True,
                    "scheduled": True,
                    "active_hours": [[9, 12]],
                }
            ],
            "platforms": {"tiktok": {"scheduler": {"fires_per_day": 1}}},
        }

        with (
            patch.object(scheduler_module, "load_config", return_value=config),
            patch.object(scheduler_module, "generate_fire_times", return_value=[future]),
            patch.object(scheduler_module, "current_config_fingerprint", return_value="new"),
            patch.object(scheduler_module.main_runtime, "record_scheduler_job_scheduled"),
        ):
            scheduler_module.schedule_today_fires()

        job_ids = {job.id for job in scheduler_module.scheduler.get_jobs()}
        self.assertNotIn("fire_tiktok_109_20260803_090400", job_ids)
        self.assertTrue(any(job_id.startswith("fire_tiktok_101_") for job_id in job_ids))
        self.assertEqual(scheduler_module.config_fingerprint, "new")

    def test_schedule_records_pending_job_runs(self):
        future = datetime.now() + timedelta(hours=1)
        config = {
            "accounts": [
                {
                    "id": "tiktok_101",
                    "platform": "tiktok",
                    "enabled": True,
                    "scheduled": True,
                    "active_hours": [[9, 12]],
                }
            ],
            "platforms": {"tiktok": {"scheduler": {"fires_per_day": 1}}},
        }

        with (
            patch.object(scheduler_module, "load_config", return_value=config),
            patch.object(scheduler_module, "generate_fire_times", return_value=[future]),
            patch.object(scheduler_module, "current_config_fingerprint", return_value="new"),
            patch.object(scheduler_module.main_runtime, "record_scheduler_job_scheduled") as record_job,
        ):
            scheduler_module.schedule_today_fires()

        record_job.assert_called_once()
        job_id, platform, account_id, scheduled_run = record_job.call_args.args
        self.assertTrue(job_id.startswith("fire_tiktok_101_"))
        self.assertEqual(platform, "tiktok")
        self.assertEqual(account_id, "tiktok_101")
        self.assertEqual(scheduled_run, future.isoformat())

    def test_unchanged_config_does_not_rebuild(self):
        scheduler_module.config_fingerprint = "same"
        with (
            patch.object(scheduler_module, "current_config_fingerprint", return_value="same"),
            patch.object(scheduler_module, "schedule_today_fires") as rebuild,
        ):
            scheduler_module.reload_schedule_if_config_changed()

        rebuild.assert_not_called()

    def test_account_login_environment_selects_and_restores_credentials(self):
        payload = {
            "tiktok_101": {
                "username": "first@example.com",
                "password": "first-secret",
            },
            "tiktok_102": {
                "username": "second@example.com",
                "password": "second-secret",
            },
        }
        original = {
            "AM_LOGIN_ACCOUNT_ID": "manual_account",
            "AM_LOGIN_USERNAME": "manual@example.com",
            "AM_LOGIN_PASSWORD": "manual-secret",
            "AM_LOGIN_CREDENTIAL_SOURCE": "local_secure_store",
        }

        with patch.dict(
            os.environ,
            {
                scheduler_module.SCHEDULER_LOGIN_CREDENTIALS_ENV: json.dumps(payload),
                **original,
            },
            clear=False,
        ):
            with scheduler_module.account_login_environment("tiktok_102"):
                self.assertEqual(os.environ["AM_LOGIN_ACCOUNT_ID"], "tiktok_102")
                self.assertEqual(os.environ["AM_LOGIN_USERNAME"], "second@example.com")
                self.assertEqual(os.environ["AM_LOGIN_PASSWORD"], "second-secret")
                self.assertEqual(
                    os.environ["AM_LOGIN_CREDENTIAL_SOURCE"], "local_secure_store"
                )

            for key, value in original.items():
                self.assertEqual(os.environ[key], value)

    def test_account_login_environment_clears_credentials_for_unknown_account(self):
        with patch.dict(
            os.environ,
            {
                scheduler_module.SCHEDULER_LOGIN_CREDENTIALS_ENV: "{}",
                "AM_LOGIN_USERNAME": "unrelated@example.com",
                "AM_LOGIN_PASSWORD": "unrelated-secret",
                "AM_LOGIN_CREDENTIAL_SOURCE": "local_secure_store",
            },
            clear=False,
        ):
            with scheduler_module.account_login_environment("tiktok_404"):
                self.assertEqual(os.environ["AM_LOGIN_ACCOUNT_ID"], "tiktok_404")
                self.assertNotIn("AM_LOGIN_USERNAME", os.environ)
                self.assertNotIn("AM_LOGIN_PASSWORD", os.environ)
                self.assertNotIn("AM_LOGIN_CREDENTIAL_SOURCE", os.environ)


if __name__ == "__main__":
    unittest.main()
