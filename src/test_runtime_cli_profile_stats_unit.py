import contextlib
import io
import json
import unittest

import runtime_cli


class RuntimeCliProfileStatsTests(unittest.TestCase):
    def test_version_payload_lists_profile_stats_command(self):
        payload = runtime_cli.version_payload()

        self.assertIn("profile-stats", payload["supportedCommands"])

    def test_profile_stats_payload_checks_collector_imports(self):
        payload = runtime_cli.build_profile_stats_payload()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["collector"]["module"], "profile_stats")
        self.assertEqual(payload["collector"]["entry"], "collect_profile_snapshot")
        self.assertEqual(payload["checks"][0]["name"], "profileCollector")

    def test_profile_stats_command_prints_json(self):
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = runtime_cli.main(["profile-stats", "--json"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertIn("profile-stats", payload["version"]["supportedCommands"])


if __name__ == "__main__":
    unittest.main()
