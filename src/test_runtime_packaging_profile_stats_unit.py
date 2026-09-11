from pathlib import Path
import unittest


class RuntimePackagingProfileStatsTests(unittest.TestCase):
    def test_pyinstaller_spec_includes_profile_collector_modules(self):
        repo = Path(__file__).resolve().parents[1]
        spec = repo / "runtime" / "pyinstaller" / "account-matrix-runtime.spec"
        text = spec.read_text(encoding="utf-8")

        self.assertIn('"profile_activity"', text)
        self.assertIn('"profile_stats"', text)


if __name__ == "__main__":
    unittest.main()
