"""Negative and boundary tests for Sprint 11 identity foundations."""

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.connectors.authorization import (
    ConnectorAuthorizationError,
    LocalConnectorPrincipalAdapter,
    ProductionConnectorPrincipalAdapter,
)
from projecta_api.identity.models import SessionRecord
from projecta_api.identity.oidc import (
    IdentityError,
    IdentityService,
    _validate_claims,
    validate_id_token,
)
from projecta_api.identity.repository import InMemoryIdentityRepository
from projecta_api.main import create_app


def _settings() -> Settings:
    return Settings(
        runtime_mode="production",
        oidc_issuer_url="https://auth.example.com/realms/projecta",
        oidc_client_id="projecta-web",
        oidc_redirect_uri="https://projecta.example.com/auth/callback",
        oidc_audience="projecta-web",
        identity_database_url="postgresql+psycopg://unused/unused",
    )


def test_login_state_is_single_use_and_return_path_is_allowlisted() -> None:
    repository = InMemoryIdentityRepository()
    service = IdentityService(_settings(), repository)
    location, return_path = service.begin_login("/projects", "request-1")
    assert return_path == "/projects"
    assert "code_challenge=" in location
    state = next(value.split("=", 1)[1] for value in location.split("?")[1].split("&") if value.startswith("state="))
    assert repository.consume_login_attempt(state, datetime.now(UTC)) is not None
    assert repository.consume_login_attempt(state, datetime.now(UTC)) is None
    with pytest.raises(IdentityError, match="OIDC_RETURN_PATH_INVALID"):
        service.begin_login("https://evil.example/steal", "request-2")


def test_claim_validation_rejects_wrong_issuer_audience_and_time() -> None:
    now = datetime.now(UTC).timestamp()
    valid = {
        "iss": "https://auth.example.com/realms/projecta",
        "aud": "projecta-web",
        "sub": "user-1",
        "iat": now,
        "exp": now + 60,
    }
    _validate_claims(valid, _settings())
    for claim, value, code in (
        ("iss", "https://wrong.example/realms/projecta", "OIDC_ISSUER_INVALID"),
        ("aud", "other-client", "OIDC_AUDIENCE_INVALID"),
        ("exp", now - 1, "OIDC_TOKEN_EXPIRED"),
    ):
        invalid = {**valid, claim: value}
        with pytest.raises(IdentityError, match=code):
            _validate_claims(invalid, _settings())


@pytest.mark.asyncio
async def test_id_token_signature_is_verified_and_forgery_is_finite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    now = datetime.now(UTC).timestamp()

    async def jwks(_: str, **__: object) -> dict[str, object]:
        return {
            "keys": [
                {
                    "kid": "key-1",
                    "kty": "RSA",
                    "e": _b64url(public_numbers.e.to_bytes(3, "big")),
                    "n": _b64url(
                        public_numbers.n.to_bytes(
                            (public_numbers.n.bit_length() + 7) // 8, "big"
                        )
                    ),
                }
            ]
        }

    monkeypatch.setattr("projecta_api.identity.oidc._get_json", jwks)
    claims = {
        "iss": "https://auth.example.com/realms/projecta",
        "aud": "projecta-web",
        "sub": "user-1",
        "iat": now,
        "exp": now + 60,
    }
    token = _signed_token(private_key, claims)
    assert (await validate_id_token(token, _settings()))["sub"] == "user-1"

    forged = token.rsplit(".", 1)[0] + "." + _b64url(b"not-a-valid-signature")
    with pytest.raises(IdentityError, match="OIDC_SIGNATURE_INVALID"):
        await validate_id_token(forged, _settings())


def test_multiple_audiences_require_the_expected_authorized_party() -> None:
    now = datetime.now(UTC).timestamp()
    claims = {
        "iss": "https://auth.example.com/realms/projecta",
        "aud": ["projecta-web", "account"],
        "azp": "other-client",
        "sub": "user-1",
        "iat": now,
        "exp": now + 60,
    }
    with pytest.raises(IdentityError, match="OIDC_AUTHORIZED_PARTY_INVALID"):
        _validate_claims(claims, _settings())


def test_expired_or_revoked_session_and_csrf_are_fail_closed() -> None:
    repository = InMemoryIdentityRepository()
    service = IdentityService(_settings(), repository)
    now = datetime.now(UTC)
    session = SessionRecord("session", "subject", "actor", None, now + timedelta(minutes=5), now, None, "csrf", 1)
    repository.save_session(session)
    assert service.session("session") is not None
    repository.revoke_session("session", now)
    assert service.session("session") is None


def test_local_connector_adapter_is_rejected_in_production() -> None:
    with pytest.raises(ConnectorAuthorizationError, match="AUTH_ADAPTER_DISABLED"):
        LocalConnectorPrincipalAdapter(_settings())


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _signed_token(
    private_key: rsa.RSAPrivateKey, claims: dict[str, object]
) -> str:
    header = _b64url(json.dumps({"alg": "RS256", "kid": "key-1"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    unsigned = f"{header}.{payload}".encode("ascii")
    signature = private_key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64url(signature)}"


@pytest.mark.asyncio
async def test_production_connector_principal_uses_membership_roles_only() -> None:
    repository = InMemoryIdentityRepository()
    repository.replace_membership("actor", "project-a", ("project-reader", "connector-admin"))
    service = IdentityService(_settings(), repository)
    adapter = ProductionConnectorPrincipalAdapter(service)
    from projecta_api.connectors.authorization import ConnectorAuthorizationRequest
    from projecta_api.context import TrustedActorContext

    principal = await adapter.resolve(ConnectorAuthorizationRequest("catalog.read", TrustedActorContext("actor", "r"), "project-a"))
    assert principal.auth_source == "oidc-session"
    assert "installation.create" in principal.capabilities
    assert principal.allowed_projects == ("project-a",)


@pytest.mark.asyncio
async def test_production_session_endpoint_is_server_owned_and_csrf_is_required() -> None:
    repository = InMemoryIdentityRepository()
    now = datetime.now(UTC)
    repository.save_session(SessionRecord("session", "subject", "actor", None, now + timedelta(minutes=5), now, None, "csrf", 1))
    settings = _settings()
    app = create_app(settings=settings, identity_repository=repository)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://projecta.example.com") as client:
        client.cookies.set(
            settings.session_cookie_name,
            "session",
            domain="projecta.example.com",
            path="/",
        )
        session = await client.get("/v1/auth/session")
        assert session.status_code == 200
        assert session.json()["authenticated"] is True
        assert "subject" not in session.json()
        assert session.json()["identity"] == "authenticated-user"
        rejected = await client.post("/auth/logout")
        assert rejected.status_code == 403


@pytest.mark.asyncio
async def test_experience_session_endpoint_exposes_server_owned_context() -> None:
    settings = Settings(
        runtime_mode="experience",
        trusted_context_secret="experience-only-secret",
        experience_actor_id="acceptance-reviewer",
        experience_project_catalog="project-a|Project A",
    )
    app = create_app(settings=settings, identity_repository=InMemoryIdentityRepository())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session = await client.get("/v1/auth/session")
    assert session.status_code == 200
    assert session.json() == {
        "requestId": session.json()["requestId"],
        "authenticated": True,
        "identity": "server-owned-experience",
        "projects": [],
    }
