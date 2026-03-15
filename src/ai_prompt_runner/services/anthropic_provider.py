"""Anthropic Messages API provider implementation using requests."""

import json
from collections.abc import Iterator
from dataclasses import dataclass

import requests

from ai_prompt_runner.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    RateLimitError,
    UpstreamServerError,
)
from ai_prompt_runner.core.models import GenerationConfig, UsageMetadata
from ai_prompt_runner.services.base import BaseProvider


@dataclass
class AnthropicProviderConfig:
    """Configuration for Anthropic Messages API requests."""

    endpoint: str
    api_key: str
    model: str
    timeout_seconds: int = 30
    max_retries: int = 0
    max_tokens: int = 1024


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic's Messages API contract."""
    provider_protocol = "anthropic-messages"

    def __init__(self, config: AnthropicProviderConfig) -> None:
        self.config = config
        self._last_usage: UsageMetadata | None = None
        self._last_model_resolved: str | None = None

    def _raise_for_mapped_status(self, response: requests.Response) -> None:
        """Map provider HTTP status codes to domain-specific exceptions."""
        status_code = response.status_code

        explicit_status_errors = {
            401: AuthenticationError("Provider authentication failed (HTTP 401)."),
            403: AuthorizationError("Provider authorization failed (HTTP 403)."),
            429: RateLimitError("Provider rate limit exceeded (HTTP 429)."),
        }

        mapped_error = explicit_status_errors.get(status_code)
        if mapped_error is not None:
            raise mapped_error

        if 500 <= status_code <= 599:
            raise UpstreamServerError(f"Provider server error (HTTP {status_code}).")
        if status_code >= 400:
            raise ProviderError(f"Provider returned HTTP {status_code}.")

    def _extract_text(self, body: dict) -> str:
        """
        Extract text from Anthropic Messages API response payload.

        Expected shape:
        {
            "content": [
                {"type": "text", "text": "..."},
                ...
            ]
        }
        """
        content_blocks = body.get("content")
        if not isinstance(content_blocks, list) or not content_blocks:
            raise ProviderError("Provider response must contain a non-empty 'content' list.")

        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue

            text = block.get("text")
            if isinstance(text, str):
                return text
            raise ProviderError("Provider text content block must contain string 'text'.")

        raise ProviderError("Provider response must contain at least one text content block.")

    def _extract_stream_delta(self, event: dict) -> str | None:
        """
        Extract text delta from an Anthropic SSE event payload.

        We currently consume text via `content_block_delta` events:
        {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "..."}
        }
        """
        if not isinstance(event, dict):
            raise ProviderError("Provider streaming event must be an object.")

        event_type = event.get("type")
        if not isinstance(event_type, str):
            return None

        if event_type == "error":
            error_obj = event.get("error")
            if isinstance(error_obj, dict):
                message = error_obj.get("message")
                if isinstance(message, str) and message.strip():
                    raise ProviderError(f"Provider stream error: {message}")
            raise ProviderError("Provider stream returned an error event.")

        if event_type != "content_block_delta":
            return None

        delta = event.get("delta")
        if not isinstance(delta, dict):
            raise ProviderError("Provider streaming event must contain object 'delta'.")

        if delta.get("type") != "text_delta":
            return None

        text = delta.get("text")
        if text is None:
            return None
        if not isinstance(text, str):
            raise ProviderError("Provider streaming delta 'text' must be a string.")

        return text

    def _extract_usage(self, payload: dict) -> UsageMetadata | None:
        """
        Normalize Anthropic usage shape to project-wide usage metadata.

        Anthropic commonly returns:
        {"usage": {"input_tokens": X, "output_tokens": Y}}
        """
        if not isinstance(payload, dict):
            return None

        usage_obj = payload.get("usage")
        if not isinstance(usage_obj, dict):
            return None

        prompt_tokens_raw = usage_obj.get("input_tokens")
        completion_tokens_raw = usage_obj.get("output_tokens")
        total_tokens_raw = usage_obj.get("total_tokens")

        prompt_tokens = (
            prompt_tokens_raw if isinstance(prompt_tokens_raw, int) else None
        )
        completion_tokens = (
            completion_tokens_raw if isinstance(completion_tokens_raw, int) else None
        )
        total_tokens = total_tokens_raw if isinstance(total_tokens_raw, int) else None

        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        return UsageMetadata(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def _extract_model_resolved(self, payload: dict) -> str | None:
        """Extract resolved model identifier when Anthropic includes it."""
        if not isinstance(payload, dict):
            return None

        model_value = payload.get("model")
        if isinstance(model_value, str):
            return model_value

        message_obj = payload.get("message")
        if isinstance(message_obj, dict):
            nested_model = message_obj.get("model")
            if isinstance(nested_model, str):
                return nested_model

        return None

    def _merge_usage(self, usage_update: UsageMetadata) -> None:
        """
        Merge partial Anthropic stream usage updates into one normalized object.

        Stream events may provide usage in multiple phases (`message_start`,
        `message_delta`), so we merge instead of replacing blindly.
        """
        existing = self._last_usage or UsageMetadata()

        prompt_tokens = (
            usage_update.prompt_tokens
            if usage_update.prompt_tokens is not None
            else existing.prompt_tokens
        )
        completion_tokens = (
            usage_update.completion_tokens
            if usage_update.completion_tokens is not None
            else existing.completion_tokens
        )

        total_tokens = (
            usage_update.total_tokens
            if usage_update.total_tokens is not None
            else existing.total_tokens
        )
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        self._last_usage = UsageMetadata(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def get_last_usage(self) -> UsageMetadata | None:
        """Expose normalized usage captured during the last provider call."""
        return self._last_usage

    def get_last_model_resolved(self) -> str | None:
        """Expose resolved model metadata captured during the last provider call."""
        return self._last_model_resolved

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        """Send one prompt to Anthropic and return generated text."""
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt is not None:
            payload["system"] = system_prompt
        if generation_config is not None:
            if generation_config.max_tokens is not None:
                payload["max_tokens"] = generation_config.max_tokens
            if generation_config.temperature is not None:
                payload["temperature"] = generation_config.temperature
            if generation_config.top_p is not None:
                payload["top_p"] = generation_config.top_p

        self._last_usage = None
        self._last_model_resolved = None

        # Retry only transient transport failures.
        for attempt in range(self.config.max_retries + 1):
            try:
                response = requests.post(
                    self.config.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
            except requests.RequestException as exc:
                if attempt == self.config.max_retries:
                    raise ProviderError(f"Provider request failed: {exc}") from exc
                continue

            self._raise_for_mapped_status(response)

            try:
                body = response.json()
            except ValueError as exc:
                raise ProviderError("Provider returned invalid JSON.") from exc

            self._last_usage = self._extract_usage(body)
            self._last_model_resolved = self._extract_model_resolved(body)
            return self._extract_text(body)

        # Defensive fallback: loop always returns or raises.
        raise ProviderError("Provider request failed unexpectedly.")

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> Iterator[str]:
        """
        Stream generated text chunks from Anthropic's Messages API.

        Notes:
        - retries are attempted only while no chunk has been emitted
        - once chunks are emitted, retrying would duplicate visible output
        """
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        if system_prompt is not None:
            payload["system"] = system_prompt
        if generation_config is not None:
            if generation_config.max_tokens is not None:
                payload["max_tokens"] = generation_config.max_tokens
            if generation_config.temperature is not None:
                payload["temperature"] = generation_config.temperature
            if generation_config.top_p is not None:
                payload["top_p"] = generation_config.top_p

        self._last_usage = None
        self._last_model_resolved = None

        for attempt in range(self.config.max_retries + 1):
            emitted_any_chunk = False
            try:
                response = requests.post(
                    self.config.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                    stream=True,
                )
                self._raise_for_mapped_status(response)

                for line in response.iter_lines(decode_unicode=True):
                    if line is None:
                        continue
                    normalized_line = line.strip()
                    if not normalized_line:
                        continue
                    if not normalized_line.startswith("data:"):
                        continue

                    data_value = normalized_line[len("data:") :].strip()
                    if data_value == "[DONE]":
                        return

                    try:
                        event = json.loads(data_value)
                    except json.JSONDecodeError as exc:
                        raise ProviderError(
                            "Provider returned invalid streaming event JSON."
                        ) from exc

                    # Anthropic usage may appear in different stream event shapes.
                    event_usage = self._extract_usage(event)
                    if event_usage is None and isinstance(event, dict):
                        message = event.get("message")
                        if isinstance(message, dict):
                            event_usage = self._extract_usage(message)
                    if event_usage is not None:
                        self._merge_usage(event_usage)

                    event_model = self._extract_model_resolved(event)
                    if event_model is not None:
                        self._last_model_resolved = event_model

                    delta_text = self._extract_stream_delta(event)
                    if delta_text is None:
                        continue

                    emitted_any_chunk = True
                    yield delta_text
                return
            except requests.RequestException as exc:
                if emitted_any_chunk or attempt == self.config.max_retries:
                    raise ProviderError(f"Provider request failed: {exc}") from exc
                continue

        # Defensive fallback: loop always returns or raises.
        raise ProviderError("Provider request failed unexpectedly.")
