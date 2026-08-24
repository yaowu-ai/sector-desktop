"""Platform-aware config access with legacy TikTok fallbacks."""
from copy import deepcopy

DEFAULT_PLATFORM = "tiktok"
VALID_PLATFORMS = {"tiktok", "instagram", "whatsapp", "douyin"}
DEFAULT_BROWSER_PROVIDER = "bitbrowser"
VALID_BROWSER_PROVIDERS = {"bitbrowser", "builtin_chromium"}
DEFAULT_AI_COMMENT_CONFIG = {
    "enabled": False,
    "provider": "kimi_moonshot",
    "base_url": "https://api.moonshot.cn/v1",
    "model": "kimi-k2.6",
    "timeout_seconds": 5,
    "max_comment_length": 80,
    "fallback_to_pool": True,
    "language": "auto",
    "blocked_words": [],
}


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


def ai_comment_config(config):
    current = (config or {}).get("ai_comment")
    if not isinstance(current, dict):
        return deepcopy(DEFAULT_AI_COMMENT_CONFIG)
    merged = deepcopy(DEFAULT_AI_COMMENT_CONFIG)
    for key in DEFAULT_AI_COMMENT_CONFIG:
        if key in current:
            merged[key] = current[key]
    merged["enabled"] = bool(merged.get("enabled"))
    merged["provider"] = str(merged.get("provider") or DEFAULT_AI_COMMENT_CONFIG["provider"]).strip()
    merged["base_url"] = str(merged.get("base_url") or DEFAULT_AI_COMMENT_CONFIG["base_url"]).strip()
    merged["model"] = str(merged.get("model") or DEFAULT_AI_COMMENT_CONFIG["model"]).strip()
    merged["language"] = str(merged.get("language") or DEFAULT_AI_COMMENT_CONFIG["language"]).strip()
    merged["fallback_to_pool"] = bool(merged.get("fallback_to_pool", True))
    try:
        merged["timeout_seconds"] = int(merged.get("timeout_seconds"))
    except (TypeError, ValueError):
        merged["timeout_seconds"] = DEFAULT_AI_COMMENT_CONFIG["timeout_seconds"]
    try:
        merged["max_comment_length"] = int(merged.get("max_comment_length"))
    except (TypeError, ValueError):
        merged["max_comment_length"] = DEFAULT_AI_COMMENT_CONFIG["max_comment_length"]
    blocked_words = merged.get("blocked_words")
    if not isinstance(blocked_words, list):
        blocked_words = []
    merged["blocked_words"] = [
        str(word).strip()
        for word in blocked_words
        if str(word).strip()
    ]
    return merged


def load_runtime_config(config):
    return normalize_accounts(config or {})
