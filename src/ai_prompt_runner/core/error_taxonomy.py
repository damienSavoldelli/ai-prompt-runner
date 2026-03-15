"""Structured runtime error taxonomy and normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from ai_prompt_runner.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    PromptRunnerError,
    RateLimitError,
)

ErrorCode = Literal[
    "rate_limit",
    "auth_error",
    "timeout",
    "invalid_request",
    "network_error",
    "provider_error",
]

_HTTP_STATUS_PATTERN = re.compile(r"HTTP (\d{3})")


@dataclass(frozen=True)
class RuntimeErrorPayload:
    """Normalized runtime error payload used by CLI/logging layers."""

    code: ErrorCode
    message: str
    provider: str | None
    timestamp_utc: str

    def to_dict(self) -> dict[str, str | None]:
        """Return JSON-serializable payload representation."""
        return {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "timestamp_utc": self.timestamp_utc,
        }


def _iter_exception_chain(exc: BaseException) -> list[BaseException]:
    """Collect the direct error plus its cause/context chain."""
    chain: list[BaseException] = []
    visited: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in visited:
        chain.append(current)
        visited.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _is_timeout_related(exc: BaseException) -> bool:
    """True when the exception chain indicates timeout semantics."""
    for item in _iter_exception_chain(exc):
        if isinstance(item, TimeoutError):
            return True
        if item.__class__.__name__ == "Timeout":
            return True
    return False


def _is_network_related(exc: BaseException) -> bool:
    """True when the exception chain indicates network transport failures."""
    network_class_names = {
        "ConnectionError",
        "ConnectTimeout",
        "ReadTimeout",
        "SSLError",
        "ProxyError",
        "ChunkedEncodingError",
        "ProtocolError",
    }
    for item in _iter_exception_chain(exc):
        if isinstance(item, ConnectionError):
            return True
        if item.__class__.__name__ in network_class_names:
            return True
    return False


def _provider_error_is_invalid_request(exc: ProviderError) -> bool:
    """
    Classify generic provider errors as invalid_request when the message
    indicates HTTP 4xx (except 401/403/429 already mapped explicitly).
    """
    match = _HTTP_STATUS_PATTERN.search(str(exc))
    if match is None:
        return False
    status = int(match.group(1))
    return 400 <= status <= 499 and status not in {401, 403, 429}


def map_runtime_error_code(exc: BaseException) -> ErrorCode:
    """Map runtime exceptions to a stable error taxonomy code."""
    if isinstance(exc, RateLimitError):
        return "rate_limit"
    if isinstance(exc, (AuthenticationError, AuthorizationError)):
        return "auth_error"
    if _is_timeout_related(exc):
        return "timeout"
    if _is_network_related(exc):
        return "network_error"
    if exc.__class__.__name__ == "ConfigurationError":
        return "invalid_request"
    if isinstance(exc, ProviderError) and _provider_error_is_invalid_request(exc):
        return "invalid_request"
    if isinstance(exc, PromptRunnerError):
        return "provider_error"
    return "provider_error"


def normalize_runtime_error(
    exc: BaseException,
    provider: str | None = None,
) -> RuntimeErrorPayload:
    """Build normalized runtime error payload from a raised exception."""
    return RuntimeErrorPayload(
        code=map_runtime_error_code(exc),
        message=str(exc),
        provider=provider,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )

