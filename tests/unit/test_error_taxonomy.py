"""Unit tests for runtime error taxonomy normalization."""

from __future__ import annotations

from datetime import datetime

import pytest
import requests

from ai_prompt_runner.core.error_taxonomy import (
    map_runtime_error_code,
    normalize_runtime_error,
)
from ai_prompt_runner.core.errors import (
    AuthenticationError,
    AuthorizationError,
    PromptRunnerError,
    ProviderError,
    RateLimitError,
)
from ai_prompt_runner.services.provider_factory import ConfigurationError


@pytest.mark.parametrize(
    ("exc", "expected_code"),
    [
        (RateLimitError("429"), "rate_limit"),
        (AuthenticationError("401"), "auth_error"),
        (AuthorizationError("403"), "auth_error"),
        (TimeoutError("timeout"), "timeout"),
        (requests.Timeout("timed out"), "timeout"),
        (ConnectionError("network down"), "network_error"),
        (requests.ConnectionError("socket closed"), "network_error"),
        (ConfigurationError("bad config"), "invalid_request"),
        (ProviderError("Provider returned HTTP 400."), "invalid_request"),
        (ProviderError("Provider returned invalid JSON."), "provider_error"),
        (PromptRunnerError("runner failure"), "provider_error"),
        (Exception("unexpected"), "provider_error"),
    ],
)
def test_map_runtime_error_code_covers_minimal_taxonomy(
    exc: BaseException,
    expected_code: str,
) -> None:
    """Map representative exception types to stable taxonomy codes."""
    assert map_runtime_error_code(exc) == expected_code


def test_normalize_runtime_error_includes_provider_and_timestamp() -> None:
    """Normalized payload must include code/message/provider/timestamp fields."""
    payload = normalize_runtime_error(
        ProviderError("Provider returned HTTP 400."),
        provider="openai",
    ).to_dict()

    assert payload["code"] == "invalid_request"
    assert payload["message"] == "Provider returned HTTP 400."
    assert payload["provider"] == "openai"

    # Validate timestamp format by parsing ISO-8601 output.
    datetime.fromisoformat(str(payload["timestamp_utc"]))


def test_map_runtime_error_code_preserves_timeout_over_network() -> None:
    """
    Timeout-class errors must map to `timeout`, even when transport-oriented.

    requests.Timeout inherits from RequestException and should not be downgraded
    to the broader `network_error` classification.
    """
    exc = requests.Timeout("timed out")
    assert map_runtime_error_code(exc) == "timeout"


def test_map_runtime_error_code_resolves_timeout_from_exception_cause_chain() -> None:
    """Timeout classification should inspect wrapped exception causes."""
    try:
        try:
            raise requests.Timeout("upstream timed out")
        except requests.Timeout as inner_exc:
            raise PromptRunnerError("provider call failed") from inner_exc
    except PromptRunnerError as exc:
        assert map_runtime_error_code(exc) == "timeout"


def test_map_runtime_error_code_resolves_network_error_from_exception_context_chain() -> None:
    """Network classification should inspect implicit exception context chains."""
    try:
        try:
            raise requests.ConnectionError("socket reset")
        except requests.ConnectionError:
            # No explicit "from": this path populates __context__.
            raise PromptRunnerError("provider call failed")
    except PromptRunnerError as exc:
        assert map_runtime_error_code(exc) == "network_error"


def test_map_runtime_error_code_does_not_misclassify_auth_status_as_invalid_request() -> None:
    """Generic provider 401/403/429 messages should not be tagged invalid_request."""
    assert map_runtime_error_code(ProviderError("Provider returned HTTP 401.")) == "provider_error"
    assert map_runtime_error_code(ProviderError("Provider returned HTTP 403.")) == "provider_error"
    assert map_runtime_error_code(ProviderError("Provider returned HTTP 429.")) == "provider_error"
