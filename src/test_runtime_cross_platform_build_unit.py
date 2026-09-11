from pathlib import Path
import unittest


class RuntimeCrossPlatformBuildTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[1]

    def test_windows_runtime_build_validates_profile_stats_command(self):
        script = (self.repo / "runtime" / "build-runtime.ps1").read_text(encoding="utf-8")

        self.assertIn("profile-stats --json", script)
        self.assertIn("runtime manifest missing profile-stats command", script)
        self.assertIn("Tauri runtime resource missing executable", script)
        self.assertIn("account-matrix-runtime.exe", script)

    def test_macos_runtime_build_validates_native_runtime_not_windows_exe(self):
        script = (self.repo / "runtime" / "build-runtime.sh").read_text(encoding="utf-8")

        self.assertIn("profile-stats --json", script)
        self.assertIn("runtime manifest missing profile-stats command", script)
        self.assertIn("macOS runtime directory contains Windows executable", script)
        self.assertIn("Tauri runtime resource contains Windows executable on macOS", script)
        self.assertIn("account-matrix-runtime", script)

    def test_release_workflow_builds_runtime_per_platform(self):
        workflow = (
            self.repo / ".github" / "workflows" / "release-desktop.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("build-windows:", workflow)
        self.assertIn("build-macos-arm64:", workflow)
        self.assertIn("build-macos-x64:", workflow)
        self.assertIn("runs-on: windows-latest", workflow)
        self.assertIn("runs-on: macos-14", workflow)
        self.assertIn("runs-on: macos-15-intel", workflow)
        self.assertIn(".\\desktop-build.ps1", workflow)
        self.assertIn("bash ./desktop-build-macos.sh", workflow)
        self.assertIn("bash ./desktop-build-macos-x64.sh", workflow)


if __name__ == "__main__":
    unittest.main()
