"""OpenAI-compatible provider porvider implementation using requests."""

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
class OpenAICompatibleProviderConfig:
    """Configuration for OpenAI-compatible chat completion providers."""

    endpoint: str
    api_key: str
    model: str
    timeout_seconds: int = 30
    max_retries: int = 0


class OpenAICompatibleProvider(BaseProvider):
    """
    Provider for APIs that expose an OpenAI-compatible chat-completions contract.

    Request shape sent:
    {
        "model": "...",
        "messages": [{"role": "user", "content": "..."}]
    }

    Response shape expected:
    {
        "choices": [{"message": {"content": "..."}}]
    }
    """

    def __init__(self, config: OpenAICompatibleProviderConfig) -> None:
        self.config = config
        self._last_usage: UsageMetadata | None = None

    def _normalized_endpoint(self) -> str:
        """
        Normalize endpoint to the chat-completions route.

        We allow callers to provide either:
        - base URL (e.g. https://api.openai.com/v1)
        - full route (.../chat/completions)

        This keeps factory defaults and user overrides flexible.
        """
        base = self.config.endpoint.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _raise_for_mapped_status(self, response: requests.Response) -> None:
        """Map provider HTTP status codes to domain-specific exceptions."""
        status_code = response.status_code

        # Explicit mappings for statuses we want to classify precisely.
        explicit_status_errors = {
            401: AuthenticationError("Provider authentication failed (HTTP 401)."),
            403: AuthorizationError("Provider authorization failed (HTTP 403)."),
            429: RateLimitError("Provider rate limit exceeded (HTTP 429)."),
        }

        mapped_error = explicit_status_errors.get(status_code)
        if mapped_error is not None:
            raise mapped_error

        # Fallback classification keeps behavior deterministic for unknown error statuses.
        if 500 <= status_code <= 599:
            raise UpstreamServerError(f"Provider server error (HTTP {status_code}).")
        if status_code >= 400:
            raise ProviderError(f"Provider returned HTTP {status_code}.")

    def _extract_text(self, body: dict) -> str:
        """
        Extract text from an OpenAI-compatible response payload.

        We validate each layer explicitly to fail fast with clear domain errors
        if an upstream service returns an unexpected shape.
        """
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("Provider response must contain a non-empty 'choices' list.")

        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderError("Provider response choice must be an object.")

        message = first.get("message")
        if not isinstance(message, dict):
            raise ProviderError("Provider response choice must contain a 'message' object.")

        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderError("Provider response message must contain string 'content'.")

        return content

    def _extract_stream_delta(self, event: dict) -> str | None:
        """
        Extract a stream text delta from one SSE `data:` event payload.

        OpenAI-compatible stream events commonly include:
        {"choices": [{"delta": {"content": "..."}}]}
        """
        if not isinstance(event, dict):
            raise ProviderError("Provider streaming event must be an object.")

        choices = event.get("choices")
        if choices is None:
            # Some providers may emit side-channel events without choices.
            return None
        if not isinstance(choices, list):
            raise ProviderError("Provider streaming event must contain list 'choices'.")
        if not choices:
            return None

        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderError("Provider streaming choice must be an object.")

        delta = first.get("delta")
        if delta is None:
            return None
        if not isinstance(delta, dict):
            raise ProviderError("Provider streaming choice must contain object 'delta'.")

        content = delta.get("content")
        if content is None:
            return None
        if not isinstance(content, str):
            raise ProviderError("Provider streaming delta 'content' must be a string.")

        return content

    def _extract_usage(self, payload: dict) -> UsageMetadata | None:
        """Normalize OpenAI-compatible usage payload when present."""
        if not isinstance(payload, dict):
            return None
        usage_obj = payload.get("usage")
        if not isinstance(usage_obj, dict):
            return None

        prompt_tokens = usage_obj.get("prompt_tokens")
        completion_tokens = usage_obj.get("completion_tokens")
        total_tokens = usage_obj.get("total_tokens")

        return UsageMetadata(
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
            completion_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
            total_tokens=total_tokens if isinstance(total_tokens, int) else None,
        )

    def get_last_usage(self) -> UsageMetadata | None:
        """Expose normalized usage captured during the last provider call."""
        return self._last_usage

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        """
        Send a single prompt and return generated text.

        Contract: one prompt in, one response string out.
        """
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        messages: list[dict[str, str]] = []
        if system_prompt is not None:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
        }
        if generation_config is not None:
            if generation_config.temperature is not None:
                payload["temperature"] = generation_config.temperature
            if generation_config.max_tokens is not None:
                payload["max_tokens"] = generation_config.max_tokens
            if generation_config.top_p is not None:
                payload["top_p"] = generation_config.top_p

        self._last_usage = None

        # Retry only transient transport errors. Deterministic HTTP responses are handled directly.
        for attempt in range(self.config.max_retries + 1):
            try:
                response = requests.post(
                    self._normalized_endpoint(),
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
            return self._extract_text(body)

        # Defensive fallback: the loop above always returns or raises.
        raise ProviderError("Provider request failed unexpectedly.")

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> Iterator[str]:
        """
        Stream generated text chunks from an OpenAI-compatible provider.

        Notes:
        - retries are attempted only when no chunk has been emitted yet
        - once chunks are emitted, retrying would duplicate visible output
        """
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        messages: list[dict[str, str]] = []
        if system_prompt is not None:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            # Ask OpenAI-compatible APIs to include final usage counters in stream events.
            "stream_options": {"include_usage": True},
        }
        if generation_config is not None:
            if generation_config.temperature is not None:
                payload["temperature"] = generation_config.temperature
            if generation_config.max_tokens is not None:
                payload["max_tokens"] = generation_config.max_tokens
            if generation_config.top_p is not None:
                payload["top_p"] = generation_config.top_p

        self._last_usage = None

        for attempt in range(self.config.max_retries + 1):
            emitted_any_chunk = False
            try:
                response = requests.post(
                    self._normalized_endpoint(),
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

                    # Usage often arrives on a final event without content delta.
                    event_usage = self._extract_usage(event)
                    if event_usage is not None:
                        self._last_usage = event_usage

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
