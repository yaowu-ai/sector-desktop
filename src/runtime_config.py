"""Runtime path helpers shared by command-line scripts."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "accounts.yaml"


def resolve_path(value, base=None):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_absolute():
        return path
    return (base or Path.cwd()) / path


def resolve_config_path(config_path=None):
    return (
        resolve_path(config_path)
        or resolve_path(os.environ.get("AM_CONFIG_PATH"))
        or DEFAULT_CONFIG_PATH
    )


def resolve_data_dir(config_path=None):
    config = resolve_config_path(config_path)
    return (
        resolve_path(os.environ.get("AM_DATA_DIR"))
        or config.parent.parent / "data"
    )


def resolve_comments_path(name, config_path=None):
    config = resolve_config_path(config_path)
    return config.parent / name
