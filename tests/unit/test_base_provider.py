"""Unit tests for BaseProvider default behaviors."""

import pytest

from ai_prompt_runner.core.models import GenerationConfig
from ai_prompt_runner.services.base import BaseProvider


class _DelegatingProvider(BaseProvider):
    """
    Minimal provider used to exercise defensive base-class paths.

    This class intentionally delegates to BaseProvider.generate so we can
    validate the abstract default raises NotImplementedError as documented.
    """

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        return super().generate(
            prompt=prompt,
            system_prompt=system_prompt,
            generation_config=generation_config,
        )


def test_base_generate_raises_not_implemented_error() -> None:
    """BaseProvider.generate must raise when an implementation delegates to it."""
    provider = _DelegatingProvider()

    with pytest.raises(NotImplementedError):
        provider.generate("hello")


def test_base_generate_stream_raises_not_implemented_error() -> None:
    """BaseProvider.generate_stream default must signal unsupported streaming."""
    provider = _DelegatingProvider()

    with pytest.raises(NotImplementedError, match="Streaming is not supported"):
        list(provider.generate_stream("hello"))
