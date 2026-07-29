"""Generate runtime-manifest.json for the bundled runtime directory."""
import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from runtime_cli import RUNTIME_VERSION, SCHEMA_VERSION, SUPPORTED_COMMANDS


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", required=True, help="Directory containing the runtime executable")
    parser.add_argument("--executable", default=None, help="Runtime executable name")
    parser.add_argument("--output", default=None, help="Manifest output path")
    args = parser.parse_args(argv)

    runtime_dir = Path(args.runtime_dir)
    executable = args.executable or default_executable_name()
    executable_path = runtime_dir / executable
    manifest = build_manifest(runtime_dir, executable_path)
    output = Path(args.output) if args.output else runtime_dir / "runtime-manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(output)
    return 0


def build_manifest(runtime_dir, executable_path):
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runtimeVersion": RUNTIME_VERSION,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "executable": executable_path.name,
        "executableSha256": sha256_file(executable_path) if executable_path.is_file() else None,
        "runtimeDir": str(runtime_dir),
        "supportedCommands": SUPPORTED_COMMANDS,
    }


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_executable_name():
    return "account-matrix-runtime.exe" if platform.system().lower() == "windows" else "account-matrix-runtime"


if __name__ == "__main__":
    raise SystemExit(main())
