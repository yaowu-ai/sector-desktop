"""Registration adapter framework."""

from platforms.registration.base import (
    RegistrationAdapter,
    RegistrationErrorCode,
    RegistrationResult,
    RegistrationStatus,
)
from platforms.registration.registry import adapter_for_platform, registered_platforms

__all__ = [
    "RegistrationAdapter",
    "RegistrationErrorCode",
    "RegistrationResult",
    "RegistrationStatus",
    "adapter_for_platform",
    "registered_platforms",
]
