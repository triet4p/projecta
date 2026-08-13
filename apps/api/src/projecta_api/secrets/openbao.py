"""Provider-neutral OpenBao KV-v2 adapter with a deterministic in-memory fake."""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, Protocol, cast

import httpx
from pydantic import SecretStr

from projecta_api.configuration.ports import SecretScope, SecretSnapshot, SecretStatus

_REFERENCE = re.compile(r"^secret_[A-Za-z0-9_-]{10,128}$")


class OpenBaoSecretError(RuntimeError):
    """Internal finite error; it never contains paths, tokens, or plaintext."""

    def __init__(self, code: str) -> None:
        allowed = {
            "SEALED", "UNAVAILABLE", "UNAUTHORIZED", "MISSING", "REVOKED",
            "STALE", "INVALID_SCOPE", "ROTATION_CONFLICT", "REFERENCE_INVALID",
            "SCOPE_REQUIRED",
        }
        self.code = code if code in allowed else "UNAVAILABLE"
        super().__init__(self.code)


class OpenBaoTransport(Protocol):
    def write(self, path: str, value: SecretStr) -> tuple[int, datetime]: ...

    def read(self, path: str, version: int | None) -> tuple[int, datetime, SecretStr]: ...

    def revoke(self, path: str, version: int | None) -> None: ...

    def readiness(self) -> SecretStatus: ...


@dataclass(frozen=True, slots=True)
class _StoredVersion:
    version: int
    created_at: datetime
    secret: SecretStr
    revoked: bool = False


class InMemoryOpenBaoTransport:
    """Deterministic fake for CI; it models seal, auth, versions and revocation."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._values: dict[str, list[_StoredVersion]] = {}
        self._status: SecretStatus = "ready"

    def write(self, path: str, value: SecretStr) -> tuple[int, datetime]:
        self._require_ready()
        if not value.get_secret_value() or len(value.get_secret_value()) > 16_384:
            raise OpenBaoSecretError("INVALID_SCOPE")
        now = datetime.now(UTC)
        with self._lock:
            versions = self._values.setdefault(path, [])
            version = len(versions) + 1
            versions.append(_StoredVersion(version, now, SecretStr(value.get_secret_value())))
        return version, now

    def read(self, path: str, version: int | None) -> tuple[int, datetime, SecretStr]:
        self._require_ready()
        with self._lock:
            versions = self._values.get(path)
            if not versions:
                raise OpenBaoSecretError("MISSING")
            selected = versions[-1] if version is None else next((item for item in versions if item.version == version), None)
            if selected is None:
                raise OpenBaoSecretError("STALE")
            if selected.revoked:
                raise OpenBaoSecretError("REVOKED")
            return selected.version, selected.created_at, SecretStr(selected.secret.get_secret_value())

    def revoke(self, path: str, version: int | None) -> None:
        self._require_ready()
        with self._lock:
            versions = self._values.get(path)
            if not versions:
                raise OpenBaoSecretError("MISSING")
            targets = versions if version is None else [item for item in versions if item.version == version]
            if not targets:
                raise OpenBaoSecretError("STALE")
            self._values[path] = [
                _StoredVersion(item.version, item.created_at, item.secret, True) if item in targets else item
                for item in versions
            ]

    def readiness(self) -> SecretStatus:
        return self._status

    def seal(self) -> None:
        self._status = "sealed"

    def unseal(self) -> None:
        self._status = "ready"

    def unauthorized(self) -> None:
        self._status = "unauthorized"

    def unavailable(self) -> None:
        self._status = "unavailable"

    def _require_ready(self) -> None:
        if self._status != "ready":
            raise OpenBaoSecretError(self._status.upper())


class OpenBaoSecretStore:
    """OpenBao adapter exposing only opaque references and scoped snapshots."""

    def __init__(self, transport: OpenBaoTransport, *, cache_ttl_seconds: int = 30) -> None:
        self._transport = transport
        self._cache_ttl = timedelta(seconds=max(0, min(cache_ttl_seconds, 300)))
        self._cache: dict[tuple[str, str, int | None], tuple[datetime, SecretSnapshot]] = {}
        self._lock = RLock()

    def create_scoped(self, scope: SecretScope, secret: SecretStr) -> SecretSnapshot:
        reference = "secret_" + secrets.token_urlsafe(18)
        version, created_at = self._transport.write(self._path(scope, reference), secret)
        return SecretSnapshot(reference, version, scope, SecretStr(secret.get_secret_value()), created_at)

    def resolve_scoped(self, scope: SecretScope, reference: str, version: int | None = None) -> SecretSnapshot:
        self._validate_reference(reference)
        key = (scope.path, reference, version)
        now = datetime.now(UTC)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached[0] > now:
                return cached[1]
        selected_version, created_at, secret = self._transport.read(self._path(scope, reference), version)
        snapshot = SecretSnapshot(reference, selected_version, scope, secret, created_at)
        with self._lock:
            self._cache[key] = (now + self._cache_ttl, snapshot)
        return snapshot

    def rotate_scoped(self, scope: SecretScope, reference: str, secret: SecretStr) -> SecretSnapshot:
        self._validate_reference(reference)
        self.resolve_scoped(scope, reference)
        version, created_at = self._transport.write(self._path(scope, reference), secret)
        self._invalidate(scope, reference)
        return SecretSnapshot(reference, version, scope, SecretStr(secret.get_secret_value()), created_at)

    def revoke_scoped(self, scope: SecretScope, reference: str, version: int | None = None) -> None:
        self._validate_reference(reference)
        self._transport.revoke(self._path(scope, reference), version)
        self._invalidate(scope, reference)

    def readiness(self) -> SecretStatus:
        return self._transport.readiness()

    # Legacy SecretStore methods intentionally require scope. They are kept so
    # the adapter can be passed through old composition code without silently
    # weakening production scope enforcement.
    def create(self, secret: SecretStr) -> str:
        del secret
        raise OpenBaoSecretError("SCOPE_REQUIRED")

    def resolve(self, reference: str) -> SecretStr:
        del reference
        raise OpenBaoSecretError("SCOPE_REQUIRED")

    def delete(self, reference: str | None) -> None:
        del reference
        raise OpenBaoSecretError("SCOPE_REQUIRED")

    @staticmethod
    def _validate_reference(reference: str) -> None:
        if not _REFERENCE.fullmatch(reference):
            raise OpenBaoSecretError("REFERENCE_INVALID")

    @staticmethod
    def _path(scope: SecretScope, reference: str) -> str:
        try:
            SecretScope(scope.project_id, scope.installation_id, scope.connector_type, scope.provider_tenant, scope.installation_revision)
        except ValueError as error:
            raise OpenBaoSecretError("INVALID_SCOPE") from error
        return f"{scope.path}/{reference}"

    def _invalidate(self, scope: SecretScope, reference: str) -> None:
        with self._lock:
            for key in tuple(self._cache):
                if key[0] == scope.path and key[1] == reference:
                    del self._cache[key]


class OpenBaoHttpTransport:
    """Small HTTP transport; token and response bodies never enter exceptions."""

    def __init__(self, base_url: str, token_provider: Callable[[], str], *, verify: str | bool = True) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._verify = verify

    def write(self, path: str, value: SecretStr) -> tuple[int, datetime]:
        response = self._request("POST", f"/v1/secret/data/{path}", json={"data": {"value": value.get_secret_value()}})
        data = _mapping(response).get("data")
        data_object = cast(dict[str, object], data)
        metadata = _mapping(data_object.get("metadata"))
        raw_version = metadata.get("version")
        if not isinstance(raw_version, int):
            raise OpenBaoSecretError("UNAVAILABLE")
        return raw_version, _timestamp(metadata.get("created_time"))

    def read(self, path: str, version: int | None) -> tuple[int, datetime, SecretStr]:
        query = {"version": str(version)} if version is not None else None
        response = self._request("GET", f"/v1/secret/data/{path}", params=query)
        data = _mapping(response).get("data")
        if not isinstance(data, dict):
            raise OpenBaoSecretError("MISSING")
        data_object = cast(dict[str, object], data)
        secret_data = _mapping(data_object.get("data"))
        metadata = _mapping(data_object.get("metadata"))
        value = secret_data.get("value")
        raw_version = metadata.get("version")
        if not isinstance(raw_version, int) or not isinstance(value, str):
            raise OpenBaoSecretError("MISSING")
        return raw_version, _timestamp(metadata.get("created_time")), SecretStr(value)

    def revoke(self, path: str, version: int | None) -> None:
        endpoint = f"/v1/secret/metadata/{path}" if version is None else f"/v1/secret/delete/{path}"
        payload: dict[str, Any] = {"versions": [version]} if version is not None else {"delete_version_after": "1s"}
        self._request("DELETE" if version is None else "POST", endpoint, json=payload)

    def readiness(self) -> SecretStatus:
        try:
            response = self._request("GET", "/v1/sys/health", include_token=False)
        except OpenBaoSecretError as error:
            return {"SEALED": "sealed", "UNAUTHORIZED": "unauthorized"}.get(error.code, "unavailable")  # type: ignore[return-value]
        return "ready" if response.get("sealed") is False else "sealed"

    def _request(self, method: str, path: str, *, include_token: bool = True, **kwargs: Any) -> dict[str, object]:
        headers = {"Accept": "application/json"}
        if include_token:
            token = self._token_provider()
            if not token:
                raise OpenBaoSecretError("UNAUTHORIZED")
            headers["X-Vault-Token"] = token
        try:
            with httpx.Client(base_url=self._base_url, verify=self._verify, timeout=5.0, follow_redirects=False) as client:
                response = client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as error:
            raise OpenBaoSecretError("UNAVAILABLE") from error
        if response.status_code in {401, 403}:
            raise OpenBaoSecretError("UNAUTHORIZED")
        if response.status_code == 404:
            raise OpenBaoSecretError("MISSING")
        if response.status_code in {423, 503}:
            raise OpenBaoSecretError("SEALED")
        if not 200 <= response.status_code < 300:
            raise OpenBaoSecretError("UNAVAILABLE")
        if response.status_code == 204:
            return {}
        try:
            raw_payload: object = response.json()
        except ValueError as error:
            raise OpenBaoSecretError("UNAVAILABLE") from error
        if not isinstance(raw_payload, dict):
            raise OpenBaoSecretError("UNAVAILABLE")
        return cast(dict[str, object], raw_payload)


def _mapping(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _timestamp(value: object) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pass
    return datetime.now(UTC)
