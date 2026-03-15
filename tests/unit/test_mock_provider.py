import pytest

from ai_prompt_runner.core.errors import ProviderError
from ai_prompt_runner.services.mock_provider import MockProvider


def test_generate_includes_system_prompt_in_effective_prompt() -> None:
    """Mock provider should use deterministic SYSTEM/USER formatting when provided."""
    provider = MockProvider()

    assert (
        provider.generate("hello", system_prompt="You are strict.")
        == "Echo: SYSTEM:\nYou are strict.\n\nUSER:\nhello"
    )


def test_generate_stream_includes_system_prompt_in_effective_prompt() -> None:
    """Mock stream path should mirror generate formatting for reconstruction tests."""
    provider = MockProvider()

    streamed = "".join(provider.generate_stream("hello", system_prompt="You are strict."))
    assert streamed == "Echo: SYSTEM:\nYou are strict.\n\nUSER:\nhello"


def test_generate_stream_raises_provider_error_when_configured_to_fail() -> None:
    """Failure mode must be consistent between non-stream and stream paths."""
    provider = MockProvider(failure_message="mock failure")

    with pytest.raises(ProviderError, match="mock failure"):
        list(provider.generate_stream("hello"))
