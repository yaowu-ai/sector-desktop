"""Registration adapter registry."""
from __future__ import annotations

from platform_config import normalize_platform
from platforms.registration.base import RegistrationAdapter


_ADAPTERS: dict[str, RegistrationAdapter] = {}


def register_adapter(adapter: RegistrationAdapter) -> RegistrationAdapter:
    _ADAPTERS[normalize_platform(adapter.platform)] = adapter
    return adapter


def adapter_for_platform(platform: str) -> RegistrationAdapter:
    platform = normalize_platform(platform)
    if not _ADAPTERS:
        load_default_adapters()
    try:
        return _ADAPTERS[platform]
    except KeyError as exc:
        raise ValueError(f"platform '{platform}' does not support registration") from exc


def registered_platforms() -> list[str]:
    if not _ADAPTERS:
        load_default_adapters()
    return sorted(_ADAPTERS)


def load_default_adapters() -> None:
    from platforms.tiktok.register import TikTokGoogleRegistrationAdapter

    register_adapter(TikTokGoogleRegistrationAdapter())
