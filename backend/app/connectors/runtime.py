"""Cross-cutting connector runtime: auth handlers, retry/backoff, circuit breaker, dead-letter.

These utilities are shared by every connector so fault-tolerance and authentication behave
consistently regardless of source type.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import random
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("insightforge.connectors")


# --------------------------------------------------------------------------------------- retries
class TransientError(Exception):
    """Raised for errors that are safe to retry (timeouts, 429, 5xx, connection resets)."""


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and calls are being short-circuited."""


def resilient(
    *,
    retries: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: float = 0.3,
) -> Callable:
    """Decorator: exponential backoff with jitter for `TransientError`.

    Backoff = min(max_delay, base_delay * 2**attempt) ± jitter. Non-transient errors propagate
    immediately so genuine bugs are not masked.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except TransientError as exc:
                    attempt += 1
                    if attempt > retries:
                        logger.error("Giving up after %d retries: %s", retries, exc)
                        raise
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay += random.uniform(0, jitter * delay)
                    logger.warning(
                        "Transient error (attempt %d/%d), retrying in %.2fs: %s",
                        attempt,
                        retries,
                        delay,
                        exc,
                    )
                    time.sleep(delay)

        return wrapper

    return decorator


@dataclasses.dataclass
class CircuitBreaker:
    """Simple per-connector circuit breaker.

    Opens after `failure_threshold` consecutive failures; half-opens after `reset_timeout` to probe.
    """

    failure_threshold: int = 5
    reset_timeout: float = 30.0
    _failures: int = 0
    _opened_at: float | None = None

    def before_call(self) -> None:
        if self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self.reset_timeout:
                logger.info("Circuit half-open: probing")
                self._opened_at = None  # allow one probe
            else:
                raise CircuitOpenError("Circuit breaker is open")

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()
            logger.error("Circuit opened after %d failures", self._failures)


@dataclasses.dataclass
class DeadLetter:
    """Captures poison records that repeatedly fail mapping/validation for later replay."""

    records: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    def add(self, stream: str, data: dict[str, Any], reason: str) -> None:
        self.records.append({"stream": stream, "data": data, "reason": reason})


# ------------------------------------------------------------------------------------------- auth
class AuthHandler:
    """Base auth handler. Produces request headers/params for a connector call."""

    def headers(self) -> dict[str, str]:
        return {}

    def params(self) -> dict[str, str]:
        return {}


class ApiKeyAuth(AuthHandler):
    def __init__(self, key: str, header: str = "X-API-Key", in_: str = "header") -> None:
        self._key = key
        self._header = header
        self._in = in_

    def headers(self) -> dict[str, str]:
        return {self._header: self._key} if self._in == "header" else {}

    def params(self) -> dict[str, str]:
        return {self._header: self._key} if self._in == "query" else {}


class BasicAuth(AuthHandler):
    def __init__(self, username: str, password: str) -> None:
        import base64

        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._header = f"Basic {token}"

    def headers(self) -> dict[str, str]:
        return {"Authorization": self._header}


class StaticTokenAuth(AuthHandler):
    def __init__(self, token: str, scheme: str = "Bearer") -> None:
        self._value = f"{scheme} {token}".strip()

    def headers(self) -> dict[str, str]:
        return {"Authorization": self._value}


class OAuth2ClientCredentials(AuthHandler):
    """OAuth2 client-credentials grant with token caching + refresh-on-expiry."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
        http_post: Callable[..., Any] | None = None,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._http_post = http_post  # injectable for testing

    def _fetch_token(self) -> None:
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._scope:
            payload["scope"] = self._scope
        if self._http_post is None:
            import httpx

            resp = httpx.post(self._token_url, data=payload, timeout=30)
            resp.raise_for_status()
            body = resp.json()
        else:
            body = self._http_post(self._token_url, data=payload)
        self._token = body["access_token"]
        self._expires_at = time.time() + int(body.get("expires_in", 3600)) - 60

    def headers(self) -> dict[str, str]:
        if self._token is None or time.time() >= self._expires_at:
            self._fetch_token()
        return {"Authorization": f"Bearer {self._token}"}


def build_auth(kind: str, params: dict[str, str]) -> AuthHandler:
    """Factory: resolved (concrete-value) params → an AuthHandler instance."""

    kind = (kind or "none").lower()
    if kind == "none":
        return AuthHandler()
    if kind == "api_key":
        return ApiKeyAuth(
            key=params["api_key"],
            header=params.get("header", "X-API-Key"),
            in_=params.get("in", "header"),
        )
    if kind == "basic":
        return BasicAuth(params["username"], params["password"])
    if kind == "static_token":
        return StaticTokenAuth(params["token"], params.get("scheme", "Bearer"))
    if kind == "oauth2_client_credentials":
        return OAuth2ClientCredentials(
            token_url=params["token_url"],
            client_id=params["client_id"],
            client_secret=params["client_secret"],
            scope=params.get("scope"),
        )
    raise ValueError(f"Unsupported auth kind: {kind}")
