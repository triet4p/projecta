"""Bounded production readiness probe for OIDC discovery and signing keys."""

from __future__ import annotations

import httpx

from projecta_api.config import Settings


async def oidc_ready(settings: Settings) -> bool:
    if settings.runtime_mode != "production" or not settings.oidc_issuer_url:
        return True
    issuer = str(settings.oidc_issuer_url).rstrip("/")
    try:
        verify: str | bool = str(settings.oidc_ca_file) if settings.oidc_ca_file is not None else True
        async with httpx.AsyncClient(timeout=2.0, follow_redirects=False, verify=verify) as client:
            discovery = await client.get(f"{issuer}/.well-known/openid-configuration")
            if discovery.status_code != 200:
                return False
            payload = discovery.json()
            jwks_uri = payload.get("jwks_uri")
            if payload.get("issuer") != issuer or not isinstance(jwks_uri, str) or not jwks_uri.startswith(issuer + "/"):
                return False
            keys = await client.get(jwks_uri)
            return keys.status_code == 200 and isinstance(keys.json().get("keys"), list) and bool(keys.json()["keys"])
    except (httpx.HTTPError, ValueError, TypeError):
        return False
