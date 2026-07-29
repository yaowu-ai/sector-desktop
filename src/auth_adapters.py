"""Authentication adapter abstraction for platform runners."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Protocol

from platform_config import normalize_platform


class LoginState(str, Enum):
    LOGGED_IN = "logged_in"
    LOGGED_OUT = "logged_out"
    LOGIN_PAGE = "login_page"
    MFA = "mfa"
    CAPTCHA = "captcha"
    SECURITY_CHECK = "security_check"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class InterventionState:
    required: bool
    state: LoginState
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class AuthResult:
    platform: str
    state: LoginState
    detail: str
    account_id: Optional[str] = None
    url: Optional[str] = None
    error_code: Optional[str] = None
    intervention: Optional[InterventionState] = None

    @property
    def logged_in(self) -> bool:
        return self.state == LoginState.LOGGED_IN

    def summary(self) -> str:
        parts = [self.state.value]
        if self.detail:
            parts.append(self.detail)
        if self.url:
            parts.append(f"url={self.url}")
        return "; ".join(parts)


class AuthAdapter(Protocol):
    platform: str

    def ensure_logged_in(
        self,
        page: Any,
        account: Mapping[str, Any],
        config: Mapping[str, Any],
    ) -> AuthResult:
        ...

    def open_login_page(self, page: Any) -> AuthResult:
        ...


class UnsupportedAuthAdapter:
    def __init__(self, platform: str):
        self.platform = platform

    def ensure_logged_in(
        self,
        page: Any,
        account: Mapping[str, Any],
        config: Mapping[str, Any],
    ) -> AuthResult:
        platform = normalize_platform(self.platform)
        return AuthResult(
            platform=platform,
            account_id=str(account.get("id") or "") or None,
            state=LoginState.UNKNOWN,
            detail=f"platform '{platform}' does not support AuthAdapter yet",
            url=getattr(page, "url", None),
            error_code="AUTH_UNSUPPORTED_PLATFORM",
            intervention=InterventionState(
                required=True,
                state=LoginState.UNKNOWN,
                reason="unsupported_platform",
                detail=f"platform '{platform}' does not support login detection yet",
            ),
        )

    def open_login_page(self, page: Any) -> AuthResult:
        platform = normalize_platform(self.platform)
        return AuthResult(
            platform=platform,
            state=LoginState.UNKNOWN,
            detail=f"platform '{platform}' does not support opening a login page yet",
            url=getattr(page, "url", None),
            error_code="AUTH_UNSUPPORTED_PLATFORM",
            intervention=InterventionState(
                required=True,
                state=LoginState.UNKNOWN,
                reason="unsupported_platform",
            ),
        )


def auth_adapter_for_platform(platform: str) -> AuthAdapter:
    platform = normalize_platform(platform)
    if platform == "tiktok":
        from platforms.tiktok.auth import TikTokAuthAdapter

        return TikTokAuthAdapter()
    return UnsupportedAuthAdapter(platform)

