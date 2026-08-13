"""Short-lived AppRole workload authentication without exposing bootstrap material."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

import httpx

from projecta_api.secrets.openbao import OpenBaoSecretError


class AppRoleLogin(Protocol):
    def login(self, role_id: str, secret_id: str) -> tuple[str, int]: ...

    def renew(self, token: str) -> tuple[str, int]: ...


@dataclass(frozen=True, slots=True)
class WorkloadToken:
    token: str
    issued_at: datetime
    expires_at: datetime
    max_expires_at: datetime


class FileAppRoleTokenProvider:
    """Read role id and single-use SecretID from restricted Compose secret files."""

    def __init__(self, role_id_file: Path, secret_id_file: Path, login: AppRoleLogin) -> None:
        self._role_id_file = role_id_file
        self._secret_id_file = secret_id_file
        self._login = login
        self._token: WorkloadToken | None = None
        self._bootstrap_consumed = False

    def __call__(self) -> str:
        now = datetime.now(UTC)
        if self._token is not None and self._token.expires_at > now + timedelta(seconds=30):
            return self._token.token
        if self._token is not None and now < self._token.max_expires_at:
            token, ttl = self._login.renew(self._token.token)
            self._token = _bounded_token(token, ttl, now, self._token.max_expires_at)
            return self._token.token
        if self._bootstrap_consumed:
            raise OpenBaoSecretError("UNAUTHORIZED")
        role_id = _read_material(self._role_id_file)
        secret_id = _read_material(self._secret_id_file)
        token, ttl = self._login.login(role_id, secret_id)
        self._bootstrap_consumed = True
        issued = datetime.now(UTC)
        self._token = _bounded_token(token, ttl, issued, issued + timedelta(seconds=60 * 60))
        return token

    def invalidate(self) -> None:
        self._token = None


def _read_material(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as error:
        raise OpenBaoSecretError("UNAUTHORIZED") from error
    if not value or len(value) > 512 or any(char.isspace() for char in value):
        raise OpenBaoSecretError("UNAUTHORIZED")
    return value


class HttpAppRoleLogin:
    """OpenBao AppRole login/renew calls with bounded response handling."""

    def __init__(self, base_url: str, *, verify: str | bool = True) -> None:
        self._base_url = base_url.rstrip("/")
        self._verify = verify

    def login(self, role_id: str, secret_id: str) -> tuple[str, int]:
        return self._post("/v1/auth/approle/login", {"role_id": role_id, "secret_id": secret_id}, None)

    def renew(self, token: str) -> tuple[str, int]:
        return self._post("/v1/auth/token/renew-self", {}, token)

    def _post(self, path: str, payload: dict[str, str], token: str | None) -> tuple[str, int]:
        headers = {"X-Vault-Token": token} if token else {}
        try:
            with httpx.Client(base_url=self._base_url, verify=self._verify, timeout=5.0, follow_redirects=False) as client:
                response = client.post(path, json=payload, headers=headers)
            raw_body: object = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OpenBaoSecretError("UNAVAILABLE") from error
        body = cast(dict[object, object], raw_body) if isinstance(raw_body, dict) else {}
        auth = body.get("auth")
        if response.status_code != 200 or not isinstance(auth, dict):
            raise OpenBaoSecretError("UNAUTHORIZED")
        auth_object = cast(dict[object, object], auth)
        client_token = auth_object.get("client_token")
        ttl = auth_object.get("lease_duration")
        if not isinstance(client_token, str) or not isinstance(ttl, int):
            raise OpenBaoSecretError("UNAUTHORIZED")
        return client_token, ttl


def _bounded_token(token: str, ttl: int, issued: datetime, max_expires_at: datetime) -> WorkloadToken:
    if not token or len(token) > 512 or ttl < 60:
        raise OpenBaoSecretError("UNAUTHORIZED")
    expires_at = min(issued + timedelta(seconds=ttl), max_expires_at)
    return WorkloadToken(token, issued, expires_at, max_expires_at)
