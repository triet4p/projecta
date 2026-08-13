"""Certificate-based Microsoft Graph credentials behind the scoped secret port."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Protocol, cast

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from projecta_api.configuration.ports import SecretScope, VersionedSecretStore


class TeamsCredentialError(RuntimeError):
    """Finite credential failure without secret material or provider detail."""

    def __init__(self, code: str) -> None:
        allowed = {
            "CREDENTIAL_MISSING",
            "CREDENTIAL_INVALID",
            "CREDENTIAL_UNAUTHORIZED",
            "CREDENTIAL_UNAVAILABLE",
            "CREDENTIAL_EXPIRED",
        }
        self.code = code if code in allowed else "CREDENTIAL_UNAVAILABLE"
        super().__init__(self.code)


class TeamsCertificateCredential(BaseModel):
    """Exact JSON shape stored in the scoped OpenBao snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(alias="tenantId", min_length=1, max_length=128)
    client_id: str = Field(alias="clientId", min_length=1, max_length=128)
    certificate_pem: str = Field(alias="certificatePem", min_length=1, max_length=32_768)
    private_key_pem: SecretStr = Field(alias="privateKeyPem")


@dataclass(frozen=True, slots=True)
class AccessToken:
    value: str
    expires_at: datetime


class CertificateTokenExchange(Protocol):
    async def exchange(
        self, credential: TeamsCertificateCredential, deadline: datetime
    ) -> tuple[str, int]: ...


class TeamsCredentialProvider:
    """Resolve one scoped credential snapshot and cache only a short-lived token."""

    def __init__(self, store: VersionedSecretStore, exchange: CertificateTokenExchange) -> None:
        self._store = store
        self._exchange = exchange
        self._cache: dict[tuple[str, str, int], AccessToken] = {}
        self._lock = Lock()

    async def get_token(
        self, scope: SecretScope, reference: str, deadline: datetime
    ) -> str:
        try:
            snapshot = self._store.resolve_scoped(scope, reference)
        except Exception as error:  # noqa: BLE001 - provider boundary is finite.
            raise TeamsCredentialError("CREDENTIAL_UNAVAILABLE") from error
        key = (scope.path, reference, snapshot.version)
        now = datetime.now(UTC)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached.expires_at > now + timedelta(seconds=30):
                return cached.value
        try:
            credential = TeamsCertificateCredential.model_validate_json(
                snapshot.secret.get_secret_value()
            )
        except (ValidationError, ValueError) as error:
            raise TeamsCredentialError("CREDENTIAL_INVALID") from error
        if credential.tenant_id != scope.provider_tenant:
            raise TeamsCredentialError("CREDENTIAL_INVALID")
        if datetime.now(UTC) >= deadline:
            raise TeamsCredentialError("CREDENTIAL_EXPIRED")
        try:
            token, ttl = await self._exchange.exchange(credential, deadline)
        except TeamsCredentialError:
            raise
        except Exception as error:  # noqa: BLE001 - no provider detail crosses boundary.
            raise TeamsCredentialError("CREDENTIAL_UNAVAILABLE") from error
        if not token or len(token) > 8192 or ttl < 60:
            raise TeamsCredentialError("CREDENTIAL_UNAUTHORIZED")
        expires_at = datetime.now(UTC) + timedelta(seconds=min(ttl, 300))
        access_token = AccessToken(token, expires_at)
        with self._lock:
            self._cache[key] = access_token
        return token


class HttpCertificateTokenExchange:
    """Single-attempt OAuth certificate client for the Microsoft identity host."""

    async def exchange(
        self, credential: TeamsCertificateCredential, deadline: datetime
    ) -> tuple[str, int]:
        try:
            certificate = x509.load_pem_x509_certificate(credential.certificate_pem.encode())
            private_key = serialization.load_pem_private_key(
                credential.private_key_pem.get_secret_value().encode(), password=None
            )
            now = datetime.now(UTC)
            token_endpoint = f"https://login.microsoftonline.com/{credential.tenant_id}/oauth2/v2.0/token"
            assertion_header = {
                "alg": "RS256",
                "typ": "JWT",
                "x5t#S256": _b64url(hashlib.sha256(certificate.public_bytes(serialization.Encoding.DER)).digest()),
            }
            assertion_claims: dict[str, object] = {
                "aud": token_endpoint,
                "iss": credential.client_id,
                "sub": credential.client_id,
                "jti": secrets.token_urlsafe(18),
                "nbf": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=5)).timestamp()),
            }
            assertion = _sign_jwt(private_key, assertion_header, assertion_claims)
            remaining = max(0.1, min(5.0, (deadline - now).total_seconds()))
            async with httpx.AsyncClient(follow_redirects=False, timeout=remaining) as client:
                response = await client.post(
                    token_endpoint,
                    data={
                        "client_id": credential.client_id,
                        "scope": "https://graph.microsoft.com/.default",
                        "grant_type": "client_credentials",
                        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                        "client_assertion": assertion,
                    },
                )
                parsed_body: object = response.json()
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as error:
            raise TeamsCredentialError("CREDENTIAL_UNAVAILABLE") from error
        if response.status_code in {401, 403}:
            raise TeamsCredentialError("CREDENTIAL_UNAUTHORIZED")
        if response.status_code != 200 or not isinstance(parsed_body, dict):
            raise TeamsCredentialError("CREDENTIAL_UNAVAILABLE")
        body = cast(dict[object, object], parsed_body)
        access_token = body.get("access_token")
        expires_in = body.get("expires_in")
        if not isinstance(access_token, str) or not isinstance(expires_in, int):
            raise TeamsCredentialError("CREDENTIAL_UNAUTHORIZED")
        return access_token, expires_in


def _sign_jwt(private_key: object, header: dict[str, str], claims: dict[str, object]) -> str:
    if not hasattr(private_key, "sign"):
        raise TeamsCredentialError("CREDENTIAL_INVALID")
    encoded_header = _b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
    encoded_claims = _b64url(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    unsigned = f"{encoded_header}.{encoded_claims}".encode()
    try:
        raw_signature: object = private_key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256())  # type: ignore[union-attr]
    except Exception as error:  # noqa: BLE001 - key details stay private.
        raise TeamsCredentialError("CREDENTIAL_INVALID") from error
    if not isinstance(raw_signature, bytes):
        raise TeamsCredentialError("CREDENTIAL_INVALID")
    signature = raw_signature
    return f"{encoded_header}.{encoded_claims}.{_b64url(signature)}"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
