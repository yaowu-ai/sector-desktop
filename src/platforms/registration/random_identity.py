"""Random identity helpers for registration tasks."""
from __future__ import annotations

import calendar
import json
import random
import string
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from core import runtime


USERNAME_ALPHABET = string.ascii_letters + string.digits


def random_birthday(min_year: int = 1985, max_year: int = 2005) -> dict[str, int]:
    year = random.randint(min_year, max_year)
    month = random.randint(1, 12)
    day = random.randint(1, calendar.monthrange(year, month)[1])
    return {"year": year, "month": month, "day": day}


def random_username(length: int = 15) -> str:
    return "".join(random.choice(USERNAME_ALPHABET) for _ in range(length))


def username_registry_path(platform: str = "tiktok") -> Path:
    return runtime.DATA_DIR / f"{platform}_registered_usernames.json"


def load_username_registry(platform: str = "tiktok") -> list[dict[str, Any]]:
    path = username_registry_path(platform)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def generate_unique_username(platform: str = "tiktok", length: int = 15, max_attempts: int = 100) -> str:
    used = {
        str(item.get("username") or "")
        for item in load_username_registry(platform)
        if item.get("username")
    }
    for _ in range(max_attempts):
        username = random_username(length)
        if username not in used:
            return username
    raise RuntimeError("failed to generate a unique registration username")


def record_username(username: str, account: Mapping[str, Any], platform: str = "tiktok") -> None:
    path = username_registry_path(platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    records = load_username_registry(platform)
    account_id = str(account.get("id") or "")
    records.append(
        {
            "username": username,
            "account_id": account_id,
            "ts": datetime.now().isoformat(),
        }
    )
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
