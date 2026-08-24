"""Credential helpers for registration tasks."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional


LOCAL_CREDENTIAL_SOURCES = {"local_secure_store", "dpapi"}


@dataclass(frozen=True)
class RegistrationCredentials:
    account_id: str
    username: Optional[str]
    password: Optional[str]
    source: Optional[str]

    @property
    def complete(self) -> bool:
        return bool(self.username and self.password)


def read_registration_credentials(account: Mapping[str, Any]) -> RegistrationCredentials:
    account_id = str(account.get("id") or "").strip()
    env_account = os.environ.get("AM_LOGIN_ACCOUNT_ID", "").strip()
    if env_account and account_id and env_account != account_id:
        return RegistrationCredentials(account_id, None, None, None)

    username = os.environ.get("AM_LOGIN_USERNAME", "").strip()
    if not username:
        login = account.get("login") if isinstance(account, Mapping) else None
        if isinstance(login, Mapping):
            username = str(login.get("username") or "").strip()

    source = os.environ.get("AM_LOGIN_CREDENTIAL_SOURCE", "").strip().lower()
    password = None
    if source in LOCAL_CREDENTIAL_SOURCES:
        password = os.environ.get("AM_LOGIN_PASSWORD", "")

    return RegistrationCredentials(
        account_id=account_id,
        username=username or None,
        password=password or None,
        source=source or None,
    )
