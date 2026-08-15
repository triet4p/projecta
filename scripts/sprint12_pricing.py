"""Cache-aware, provider-neutral pricing binding for Sprint 12 experiments."""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
PRICE_ENV_KEYS = {
    "inputCacheHitUsdPer1M": "PROJECTA_LLM_PRICE_INPUT_CACHE_HIT_USD_PER_1M",
    "inputCacheMissUsdPer1M": "PROJECTA_LLM_PRICE_INPUT_CACHE_MISS_USD_PER_1M",
    "outputUsdPer1M": "PROJECTA_LLM_PRICE_OUTPUT_USD_PER_1M",
}


class PricingBindingError(ValueError):
    """Raised when the local price configuration cannot be bound safely."""


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def load_dotenv(path: Path = ROOT / ".env") -> dict[str, str]:
    """Read only simple KEY=VALUE pairs; never expose values in errors."""

    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def merged_environment(
    environment: Mapping[str, str] | None = None,
    dotenv_path: Path = ROOT / ".env",
) -> dict[str, str]:
    values = load_dotenv(dotenv_path)
    values.update(environment or os.environ)
    return values


def _decimal(value: object, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise PricingBindingError(f"invalid pricing value for {label}") from error
    if parsed < 0:
        raise PricingBindingError(f"negative pricing value for {label}")
    return parsed


def load_pricing_artifact(path: Path) -> dict[str, object]:
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PricingBindingError("cannot read pricing artifact") from error
    if not isinstance(artifact, dict):
        raise PricingBindingError("pricing artifact must be an object")
    if artifact.get("status") != "BOUND":
        raise PricingBindingError("pricing artifact is not bound")
    rates = artifact.get("rates")
    if not isinstance(rates, dict):
        raise PricingBindingError("pricing artifact has no rate table")
    for key in PRICE_ENV_KEYS:
        _decimal(rates.get(key), key)
    return artifact


def bind_pricing(
    artifact_path: Path,
    environment: Mapping[str, str] | None = None,
    dotenv_path: Path = ROOT / ".env",
    expected_model: str | None = None,
) -> dict[str, object]:
    artifact = load_pricing_artifact(artifact_path)
    if expected_model is not None and artifact.get("model") != expected_model:
        raise PricingBindingError("pricing model does not match experiment model")
    values = merged_environment(environment, dotenv_path)
    rates = artifact["rates"]
    assert isinstance(rates, dict)
    bound: dict[str, str] = {}
    for rate_key, env_key in PRICE_ENV_KEYS.items():
        env_value = values.get(env_key)
        if env_value is None or env_value == "":
            raise PricingBindingError(f"missing pricing variable: {env_key}")
        env_decimal = _decimal(env_value, env_key)
        artifact_decimal = _decimal(rates[rate_key], rate_key)
        if env_decimal != artifact_decimal:
            raise PricingBindingError(f"pricing mismatch for {env_key}")
        bound[rate_key] = str(env_decimal)
    return {
        "artifact": artifact,
        "artifactDigest": file_digest(artifact_path),
        "rates": bound,
        "currency": artifact.get("currency"),
        "unit": artifact.get("unit"),
        "sourceUrl": artifact.get("sourceUrl"),
        "retrievedAt": artifact.get("retrievedAt"),
    }


def cost_usd(
    usage: Mapping[str, object],
    pricing: Mapping[str, object],
) -> float:
    """Compute exact USD cost from the three DeepSeek token classes."""

    required_usage = (
        "inputTokens",
        "promptCacheHitTokens",
        "promptCacheMissTokens",
        "outputTokens",
    )
    if any(usage.get(key) is None for key in required_usage):
        raise PricingBindingError("usage is missing a required cache-aware token field")
    hit = int(usage["promptCacheHitTokens"])
    miss = int(usage["promptCacheMissTokens"])
    input_tokens = usage["inputTokens"]
    if input_tokens is not None and int(input_tokens) != hit + miss:
        raise PricingBindingError("input token total does not equal cache hit plus miss")
    output = int(usage["outputTokens"])
    rates = pricing["rates"]
    assert isinstance(rates, Mapping)
    total = (
        Decimal(hit) * _decimal(rates["inputCacheHitUsdPer1M"], "inputCacheHitUsdPer1M")
        + Decimal(miss) * _decimal(rates["inputCacheMissUsdPer1M"], "inputCacheMissUsdPer1M")
        + Decimal(output) * _decimal(rates["outputUsdPer1M"], "outputUsdPer1M")
    ) / Decimal(1_000_000)
    return float(total)
