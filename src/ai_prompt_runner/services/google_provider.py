"""Google Gemini generateContent provider implementation using requests."""

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
class GoogleProviderConfig:
    """Configuration for Google Gemini generateContent requests."""

    endpoint: str
    api_key: str
    model: str
    timeout_seconds: int = 30
    max_retries: int = 0


class GoogleProvider(BaseProvider):
    """Provider for Gemini generateContent protocol."""

    def __init__(self, config: GoogleProviderConfig) -> None:
        self.config = config
        self._last_usage: UsageMetadata | None = None

    def _normalized_endpoint(self) -> str:
        """
        Build full generateContent URL from a base models endpoint.

        Example:
        https://generativelanguage.googleapis.com/v1beta/models
        -> .../models/{model}:generateContent
        """
        base = self.config.endpoint.rstrip("/")
        return f"{base}/{self.config.model}:generateContent"

    def _normalized_stream_endpoint(self) -> str:
        """
        Build full streamGenerateContent URL from a base models endpoint.

        Expected form:
        .../models/{model}:streamGenerateContent?alt=sse
        """
        base = self.config.endpoint.rstrip("/")
        return f"{base}/{self.config.model}:streamGenerateContent?alt=sse"

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
        Extract text from Gemini generateContent response payload.

        Expected shape:
        {
            "candidates": [
                {"content": {"parts": [{"text": "..."}]}}
            ]
        }
        """
        candidates = body.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderError("Provider response must contain a non-empty 'candidates' list.")

        first_candidate = candidates[0]
        if not isinstance(first_candidate, dict):
            raise ProviderError("Provider response candidate must be an object.")

        content = first_candidate.get("content")
        if not isinstance(content, dict):
            raise ProviderError("Provider response candidate must contain a 'content' object.")

        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            raise ProviderError("Provider response content must contain a non-empty 'parts' list.")

        first_part = parts[0]
        if not isinstance(first_part, dict):
            raise ProviderError("Provider response part must be an object.")

        text = first_part.get("text")
        if not isinstance(text, str):
            raise ProviderError("Provider response part must contain string 'text'.")

        return text

    def _extract_stream_delta(self, event: dict) -> str | None:
        """
        Extract stream text from one Gemini SSE event payload.

        Stream events generally include the same candidates/content/parts shape
        as non-stream responses, but incrementally.
        """
        if not isinstance(event, dict):
            raise ProviderError("Provider streaming event must be an object.")

        if "error" in event:
            error_obj = event.get("error")
            if isinstance(error_obj, dict):
                message = error_obj.get("message")
                if isinstance(message, str) and message.strip():
                    raise ProviderError(f"Provider stream error: {message}")
            raise ProviderError("Provider stream returned an error event.")

        candidates = event.get("candidates")
        if candidates is None:
            return None
        if not isinstance(candidates, list):
            raise ProviderError("Provider streaming event must contain list 'candidates'.")
        if not candidates:
            return None

        first_candidate = candidates[0]
        if not isinstance(first_candidate, dict):
            raise ProviderError("Provider streaming candidate must be an object.")

        content = first_candidate.get("content")
        if not isinstance(content, dict):
            raise ProviderError("Provider streaming candidate must contain a 'content' object.")

        parts = content.get("parts")
        if not isinstance(parts, list):
            raise ProviderError("Provider streaming content must contain list 'parts'.")
        if not parts:
            return None

        text_chunks: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                raise ProviderError("Provider streaming part must be an object.")
            text = part.get("text")
            if text is None:
                continue
            if not isinstance(text, str):
                raise ProviderError("Provider streaming part text must be a string.")
            text_chunks.append(text)

        if not text_chunks:
            return None
        return "".join(text_chunks)

    def _extract_usage(self, payload: dict) -> UsageMetadata | None:
        """
        Normalize Gemini `usageMetadata` to project-wide usage metadata.

        Expected keys (when present):
        - promptTokenCount
        - candidatesTokenCount
        - totalTokenCount
        """
        if not isinstance(payload, dict):
            return None

        usage_obj = payload.get("usageMetadata")
        if not isinstance(usage_obj, dict):
            return None

        prompt_tokens_raw = usage_obj.get("promptTokenCount")
        completion_tokens_raw = usage_obj.get("candidatesTokenCount")
        total_tokens_raw = usage_obj.get("totalTokenCount")

        return UsageMetadata(
            prompt_tokens=prompt_tokens_raw if isinstance(prompt_tokens_raw, int) else None,
            completion_tokens=(
                completion_tokens_raw if isinstance(completion_tokens_raw, int) else None
            ),
            total_tokens=total_tokens_raw if isinstance(total_tokens_raw, int) else None,
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
        """Send one prompt to Gemini and return generated text."""
        headers = {
            "x-goog-api-key": self.config.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ]
                }
            ]
        }
        if system_prompt is not None:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}],
            }
        if generation_config is not None:
            generation_payload: dict[str, float | int] = {}
            if generation_config.temperature is not None:
                generation_payload["temperature"] = generation_config.temperature
            if generation_config.max_tokens is not None:
                generation_payload["maxOutputTokens"] = generation_config.max_tokens
            if generation_config.top_p is not None:
                generation_payload["topP"] = generation_config.top_p
            if generation_payload:
                payload["generationConfig"] = generation_payload

        self._last_usage = None

        # Retry only transient transport failures.
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

        # Defensive fallback: loop always returns or raises.
        raise ProviderError("Provider request failed unexpectedly.")

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> Iterator[str]:
        """
        Stream generated text chunks from Google Gemini.

        Notes:
        - retries are attempted only while no chunk has been emitted
        - once chunks are emitted, retrying would duplicate visible output
        """
        headers = {
            "x-goog-api-key": self.config.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ]
                }
            ]
        }
        if system_prompt is not None:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}],
            }
        if generation_config is not None:
            generation_payload: dict[str, float | int] = {}
            if generation_config.temperature is not None:
                generation_payload["temperature"] = generation_config.temperature
            if generation_config.max_tokens is not None:
                generation_payload["maxOutputTokens"] = generation_config.max_tokens
            if generation_config.top_p is not None:
                generation_payload["topP"] = generation_config.top_p
            if generation_payload:
                payload["generationConfig"] = generation_payload

        self._last_usage = None

        for attempt in range(self.config.max_retries + 1):
            emitted_any_chunk = False
            try:
                response = requests.post(
                    self._normalized_stream_endpoint(),
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

                    # Usage metadata may appear in stream events without text chunks.
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
