"""Common registration adapter types."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Protocol


class RegistrationStatus(str, Enum):
    STARTED = "started"
    LOGIN_OPENED = "login_opened"
    GOOGLE_STARTED = "google_started"
    BIRTHDAY_SUBMITTED = "birthday_submitted"
    USERNAME_SUBMITTED = "username_submitted"
    SESSION_SAVED = "session_saved"
    COMPLETE = "complete"
    MANUAL_REQUIRED = "manual_required"
    ERROR = "error"


class RegistrationErrorCode(str, Enum):
    ACCOUNT_NOT_FOUND = "REGISTER_ACCOUNT_NOT_FOUND"
    UNSUPPORTED_PLATFORM = "REGISTER_UNSUPPORTED_PLATFORM"
    BROWSER_PROVIDER_INVALID = "REGISTER_BROWSER_PROVIDER_INVALID"
    BROWSER_OPEN_FAILED = "REGISTER_BROWSER_OPEN_FAILED"
    TIKTOK_LOGIN_LOAD_FAILED = "REGISTER_TIKTOK_LOGIN_LOAD_FAILED"
    GOOGLE_POPUP_NOT_FOUND = "REGISTER_GOOGLE_POPUP_NOT_FOUND"
    GOOGLE_EMAIL_FIELD_NOT_FOUND = "REGISTER_GOOGLE_EMAIL_FIELD_NOT_FOUND"
    GOOGLE_PASSWORD_FIELD_NOT_FOUND = "REGISTER_GOOGLE_PASSWORD_FIELD_NOT_FOUND"
    GOOGLE_FLOW_BLOCKED = "REGISTER_GOOGLE_FLOW_BLOCKED"
    TIKTOK_BIRTHDAY_FORM_NOT_FOUND = "REGISTER_TIKTOK_BIRTHDAY_FORM_NOT_FOUND"
    USERNAME_FORM_NOT_FOUND = "REGISTER_USERNAME_FORM_NOT_FOUND"
    USERNAME_UNAVAILABLE = "REGISTER_USERNAME_UNAVAILABLE"
    SESSION_SAVE_FAILED = "REGISTER_SESSION_SAVE_FAILED"
    BROWSER_CLOSE_FAILED = "REGISTER_BROWSER_CLOSE_FAILED"
    MANUAL_INTERVENTION_REQUIRED = "REGISTER_MANUAL_INTERVENTION_REQUIRED"


@dataclass(frozen=True)
class RegistrationResult:
    platform: str
    account_id: str
    status: RegistrationStatus
    detail: str = ""
    error_code: Optional[RegistrationErrorCode] = None
    username: Optional[str] = None
    manual_reason: Optional[str] = None
    browser_closed: bool = False

    @property
    def ok(self) -> bool:
        return self.status == RegistrationStatus.COMPLETE and self.error_code is None

    def summary(self) -> str:
        parts = [self.status.value]
        if self.error_code:
            parts.append(self.error_code.value)
        if self.detail:
            parts.append(self.detail)
        if self.username:
            parts.append(f"username={self.username}")
        if self.manual_reason:
            parts.append(f"manual_reason={self.manual_reason}")
        return "; ".join(parts)


class RegistrationAdapter(Protocol):
    platform: str

    def register(
        self,
        account: Mapping[str, Any],
        config: Mapping[str, Any],
        conn: Any,
    ) -> RegistrationResult:
        ...
