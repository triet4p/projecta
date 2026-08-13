"""OIDC protocol validation, login state, and server-owned sessions."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from urllib.parse import urlencode

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.hashes import SHA256

from projecta_api.config import Settings
from projecta_api.context import TrustedActorContext, TrustedRequestContext
from projecta_api.correlation import resolve_correlation
from projecta_api.identity.models import IdentityPrincipal, LoginAttempt, SessionRecord
from projecta_api.identity.repository import IdentityRepository
from projecta_api.operational.audit import SecurityAuditSink, emit_safe


class IdentityError(RuntimeError):
    """Finite public identity failure."""

    def __init__(self, code: str, status_code: int = 401) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class OidcTokenClient(Protocol):
    async def exchange(self, code: str, verifier: str) -> dict[str, Any]: ...


class HttpOidcTokenClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def exchange(self, code: str, verifier: str) -> dict[str, Any]:
        issuer = str(self._settings.oidc_issuer_url).rstrip("/")
        discovery = await _get_json(f"{issuer}/.well-known/openid-configuration")
        endpoint = discovery.get("token_endpoint")
        if not isinstance(endpoint, str) or not endpoint.startswith(issuer + "/"):
            raise IdentityError("OIDC_PROVIDER_CONFIGURATION_INVALID", 503)
        async with httpx.AsyncClient(
            timeout=5.0, follow_redirects=False, verify=_tls_verify(self._settings)
        ) as client:
            response = await client.post(
                endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": str(self._settings.oidc_redirect_uri),
                    "client_id": self._settings.oidc_client_id,
                    "code_verifier": verifier,
                },
            )
        if response.status_code != 200:
            raise IdentityError("OIDC_CODE_EXCHANGE_FAILED", 502)
        raw_value: object = response.json()
        if not isinstance(raw_value, dict):
            raise IdentityError("OIDC_TOKEN_RESPONSE_INVALID", 502)
        value = cast(dict[str, Any], raw_value)
        if not isinstance(value.get("id_token"), str):
            raise IdentityError("OIDC_TOKEN_RESPONSE_INVALID", 502)
        return value


class IdentityService:
    """Coordinates OIDC while keeping all credentials and claims server-side."""

    def __init__(
        self,
        settings: Settings,
        repository: IdentityRepository,
        token_client: OidcTokenClient | None = None,
        audit_sink: SecurityAuditSink | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.token_client = token_client or HttpOidcTokenClient(settings)
        self.audit_sink = audit_sink

    def begin_login(self, return_path: str, correlation_id: str) -> tuple[str, str]:
        if not _safe_return_path(return_path):
            raise IdentityError("OIDC_RETURN_PATH_INVALID", 400)
        now = datetime.now(UTC)
        state = _token()
        nonce = _token()
        verifier = _token(48)
        attempt = LoginAttempt(state, nonce, verifier, return_path, now, now + timedelta(minutes=5), correlation_id)
        self.repository.save_login_attempt(attempt)
        emit_safe(self.audit_sink, category="login", action="login.begin", outcome="started", correlation_id=correlation_id)
        challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
        issuer = str(self.settings.oidc_issuer_url).rstrip("/")
        query = urlencode(
            {
                "client_id": self.settings.oidc_client_id,
                "redirect_uri": str(self.settings.oidc_redirect_uri),
                "response_type": "code",
                "scope": "openid profile email",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{issuer}/protocol/openid-connect/auth?{query}", return_path

    async def complete_login(self, code: str, state: str) -> tuple[SessionRecord, str]:
        now = datetime.now(UTC)
        attempt = self.repository.consume_login_attempt(state, now)
        if attempt is None:
            raise IdentityError("OIDC_STATE_INVALID")
        token_response = await self.token_client.exchange(code, attempt.code_verifier)
        claims = await validate_id_token(token_response["id_token"], self.settings)
        if claims.get("nonce") != attempt.nonce:
            raise IdentityError("OIDC_NONCE_INVALID")
        subject = _required_claim(claims, "sub")
        session = SessionRecord(
            session_id=_token(32),
            subject=subject,
            actor_id=subject,
            tenant_id=claims.get("tenant_id") if isinstance(claims.get("tenant_id"), str) else None,
            expires_at=now + timedelta(seconds=self.settings.session_max_age_seconds),
            created_at=now,
            revoked_at=None,
            csrf_token=_token(),
            session_epoch=1,
        )
        self.repository.save_session(session)
        emit_safe(self.audit_sink, category="login", action="login.complete", outcome="succeeded", correlation_id=attempt.correlation_id, actor_id=subject)
        return session, attempt.return_path

    def session(self, session_id: str | None) -> SessionRecord | None:
        return self.repository.get_session(session_id, datetime.now(UTC)) if session_id else None

    def revoke(self, session_id: str | None) -> None:
        if session_id:
            self.repository.revoke_session(session_id, datetime.now(UTC))
            emit_safe(self.audit_sink, category="session", action="session.revoke", outcome="revoked", correlation_id="session-revoke", actor_id=session_id)

    def principal(self, session_id: str | None, project_id: str | None = None) -> IdentityPrincipal:
        session = self.session(session_id)
        if session is None:
            raise IdentityError("AUTHENTICATION_REQUIRED")
        memberships = self.repository.memberships(session.subject)
        selected = next((item for item in memberships if item.project_id == project_id), None) if project_id else None
        if project_id and selected is None:
            raise IdentityError("PROJECT_FORBIDDEN", 403)
        roles = selected.roles if selected else ()
        return IdentityPrincipal(session.subject, session.actor_id, session.session_id, project_id, roles, session.session_epoch, session.expires_at)

    def roles_for_actor(self, actor_id: str, project_id: str | None = None) -> tuple[tuple[str, ...], tuple[str, ...]]:
        memberships = self.repository.memberships(actor_id)
        allowed = tuple(item.project_id for item in memberships)
        selected = next((item for item in memberships if item.project_id == project_id), None) if project_id else None
        return allowed, tuple(selected.roles) if selected else ()

    def context_for_request(self, request: Any) -> TrustedRequestContext:
        session_id = request.cookies.get(self.settings.session_cookie_name)
        session = self.session(session_id)
        if session is None:
            raise IdentityError("AUTHENTICATION_REQUIRED")
        selection = getattr(request.app.state, "project_selection_repository", None)
        selected = selection.get(session.actor_id) if selection is not None else None
        if selected is None:
            raise IdentityError("PROJECT_SELECTION_REQUIRED", 409)
        self.principal(session_id, selected.project_id)
        correlation = resolve_correlation(request.headers.get("X-Request-Id"), request.headers.get("X-Operation-Id"))
        return TrustedRequestContext(selected.project_id, session.actor_id, correlation.request_id, correlation.operation_id)

    def actor_context_for_request(self, request: Any) -> TrustedActorContext:
        session = self.session(request.cookies.get(self.settings.session_cookie_name))
        if session is None:
            raise IdentityError("AUTHENTICATION_REQUIRED")
        correlation = resolve_correlation(request.headers.get("X-Request-Id"), request.headers.get("X-Operation-Id"))
        return TrustedActorContext(session.actor_id, correlation.request_id, correlation.operation_id)

    def csrf_valid(self, request: Any) -> bool:
        session = self.session(request.cookies.get(self.settings.session_cookie_name))
        if session is None:
            return True
        return secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session.csrf_token)


async def validate_id_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validate an RS256 JWT against the provider's current JWKS before mapping claims."""
    parts = token.split(".")
    if len(parts) != 3:
        raise IdentityError("OIDC_TOKEN_INVALID")
    try:
        header = _json_object(_decode(parts[0]))
        claims = _json_object(_decode(parts[1]))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise IdentityError("OIDC_TOKEN_INVALID") from error
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise IdentityError("OIDC_TOKEN_ALGORITHM_INVALID")
    jwks = await _get_json(
        f"{str(settings.oidc_issuer_url).rstrip('/')}/protocol/openid-connect/certs",
        verify=_tls_verify(settings),
    )
    raw_keys = jwks.get("keys")
    keys: list[object] = cast(list[object], raw_keys) if isinstance(raw_keys, list) else []
    key = next(
        (
            cast(dict[str, object], item)
            for item in keys
            if isinstance(item, dict)
            and cast(dict[object, object], item).get("kid") == header["kid"]
        ),
        None,
    )
    if not isinstance(key, dict) or key.get("kty") != "RSA":
        raise IdentityError("OIDC_SIGNING_KEY_UNKNOWN")
    try:
        public_key = rsa.RSAPublicNumbers(
            int.from_bytes(_base64url_decode(str(key["e"])), "big"),
            int.from_bytes(_base64url_decode(str(key["n"])), "big"),
        ).public_key()
        public_key.verify(_base64url_decode(parts[2]), f"{parts[0]}.{parts[1]}".encode("ascii"), padding.PKCS1v15(), SHA256())
    except (InvalidSignature, KeyError, ValueError, TypeError) as error:
        raise IdentityError("OIDC_SIGNATURE_INVALID") from error
    _validate_claims(claims, settings)
    return claims


def _validate_claims(claims: dict[str, Any], settings: Settings) -> None:
    now = datetime.now(UTC).timestamp()
    issuer = str(settings.oidc_issuer_url).rstrip("/")
    if claims.get("iss") != issuer:
        raise IdentityError("OIDC_ISSUER_INVALID")
    audience = claims.get("aud")
    audiences = (
        [item for item in cast(list[object], audience) if isinstance(item, str)]
        if isinstance(audience, list)
        else [audience]
    )
    if settings.oidc_audience not in audiences:
        raise IdentityError("OIDC_AUDIENCE_INVALID")
    if len(audiences) > 1 and claims.get("azp") != settings.oidc_client_id:
        raise IdentityError("OIDC_AUTHORIZED_PARTY_INVALID")
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise IdentityError("OIDC_SUBJECT_INVALID")
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] <= now:
        raise IdentityError("OIDC_TOKEN_EXPIRED")
    if not isinstance(claims.get("iat"), (int, float)) or claims["iat"] > now + 60:
        raise IdentityError("OIDC_TOKEN_TIME_INVALID")
    if isinstance(claims.get("nbf"), (int, float)) and claims["nbf"] > now + 60:
        raise IdentityError("OIDC_TOKEN_TIME_INVALID")


async def _get_json(url: str, *, verify: str | bool = True) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False, verify=verify) as client:
            response = await client.get(url)
        if response.status_code != 200 or not isinstance(response.json(), dict):
            raise IdentityError("OIDC_PROVIDER_UNAVAILABLE", 503)
        return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise IdentityError("OIDC_PROVIDER_UNAVAILABLE", 503) from error


def _required_claim(claims: dict[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value:
        raise IdentityError("OIDC_SUBJECT_INVALID")
    return value


def _tls_verify(settings: Settings) -> str | bool:
    return str(settings.oidc_ca_file) if settings.oidc_ca_file is not None else True


def _json_object(value: str) -> dict[str, Any]:
    parsed: object = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("OIDC JSON value must be an object")
    raw_object = cast(dict[object, object], parsed)
    if any(not isinstance(key, str) for key in raw_object):
        raise ValueError("OIDC JSON keys must be strings")
    return {cast(str, key): item for key, item in raw_object.items()}


def _safe_return_path(value: str) -> bool:
    return bool(value.startswith("/") and not value.startswith("//") and "\\" not in value and len(value) <= 256)


def _token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _decode(value: str) -> str:
    return _base64url_decode(value).decode("utf-8")
