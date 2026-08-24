import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_CONFIG = ROOT / "desktop" / "src-tauri" / "resources" / "templates" / "config" / "accounts.yaml"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "src" / "runtime_cli.py"), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_version_json():
    result = run_cli("version", "--json")
    payload = json.loads(result.stdout)
    assert payload["runtimeVersion"]
    assert payload["schemaVersion"] == 1
    assert {"run", "scheduler", "gmail", "diagnostic", "version"}.issubset(
        set(payload["supportedCommands"])
    )


def test_diagnostic_json_with_template_config():
    data_dir = ROOT / "desktop" / "tests" / "runtime-smoke-output" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    result = run_cli(
        "diagnostic",
        "--json",
        "--config",
        str(TEMPLATE_CONFIG),
        "--data-dir",
        str(data_dir),
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["accounts"]["total"] == 1
    assert payload["checks"]


def test_pyinstaller_spec_exists():
    spec = ROOT / "runtime" / "pyinstaller" / "account-matrix-runtime.spec"
    assert spec.is_file()


def main():
    test_version_json()
    test_diagnostic_json_with_template_config()
    test_pyinstaller_spec_exists()
    print("runtime smoke ok")


if __name__ == "__main__":
    main()
