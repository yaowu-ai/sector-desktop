"""Platform-aware config access with legacy TikTok fallbacks."""
from copy import deepcopy

DEFAULT_PLATFORM = "tiktok"
VALID_PLATFORMS = {"tiktok", "instagram", "whatsapp", "douyin"}
DEFAULT_BROWSER_PROVIDER = "bitbrowser"
VALID_BROWSER_PROVIDERS = {"bitbrowser", "builtin_chromium"}


def normalize_platform(platform=None):
    value = str(platform or DEFAULT_PLATFORM).strip().lower()
    if not value:
        value = DEFAULT_PLATFORM
    if value not in VALID_PLATFORMS:
        raise ValueError(f"unsupported platform '{platform}'")
    return value


def account_platform(account):
    return normalize_platform((account or {}).get("platform", DEFAULT_PLATFORM))


def normalize_accounts(config):
    for account in (config or {}).get("accounts") or []:
        account["platform"] = account_platform(account)
        account["browser_provider"] = normalize_browser_provider(
            account.get("browser_provider")
            or ((account.get("browser") or {}).get("provider") if isinstance(account.get("browser"), dict) else None)
            or ((config or {}).get("browser") or {}).get("default_provider")
        )
    return config


def normalize_browser_provider(provider=None):
    value = str(provider or DEFAULT_BROWSER_PROVIDER).strip().lower()
    if not value:
        value = DEFAULT_BROWSER_PROVIDER
    if value not in VALID_BROWSER_PROVIDERS:
        raise ValueError(f"unsupported browser_provider '{provider}'")
    return value


def platform_root(config, platform=DEFAULT_PLATFORM):
    platform = normalize_platform(platform)
    platforms = (config or {}).get("platforms") or {}
    value = platforms.get(platform) or {}
    return value if isinstance(value, dict) else {}


def warmup_config(config, platform=DEFAULT_PLATFORM):
    current = platform_root(config, platform).get("warmup")
    if isinstance(current, dict):
        return current
    return ((config or {}).get("defaults") or {}).get("daily_actions") or {}


def target_engagement_config(config, platform=DEFAULT_PLATFORM):
    current = platform_root(config, platform).get("target_engagement")
    if isinstance(current, dict):
        return current
    return (config or {}).get("target_accounts") or {}


def scheduler_config(config, platform=DEFAULT_PLATFORM):
    current = platform_root(config, platform).get("scheduler")
    if isinstance(current, dict):
        legacy_defaults = ((config or {}).get("defaults") or {})
        merged = deepcopy(current)
        if "active_hours" not in merged and "active_hours" in legacy_defaults:
            merged["active_hours"] = legacy_defaults["active_hours"]
        return merged
    legacy = deepcopy((config or {}).get("scheduler") or {})
    legacy_defaults = ((config or {}).get("defaults") or {})
    if "active_hours" not in legacy and "active_hours" in legacy_defaults:
        legacy["active_hours"] = legacy_defaults["active_hours"]
    return legacy


def comments_config(config, platform=DEFAULT_PLATFORM):
    current = platform_root(config, platform).get("comments")
    if isinstance(current, dict):
        return current
    target = target_engagement_config(config, platform)
    return {
        "general_file": "comments.txt",
        "target_file": target.get("comments_file", "comments_brand.txt"),
    }


def load_runtime_config(config):
    return normalize_accounts(config or {})
