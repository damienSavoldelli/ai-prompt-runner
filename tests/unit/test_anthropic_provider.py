import pytest
import requests

from ai_prompt_runner.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    RateLimitError,
    UpstreamServerError,
)
from ai_prompt_runner.services.anthropic_provider import (
    AnthropicProvider,
    AnthropicProviderConfig,
)


class DummyResponse:
    """Small test double for requests.Response-like JSON behavior."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


class DummyStreamResponse:
    """Small test double for streaming `iter_lines` behavior."""

    def __init__(self, lines: list[str | None], status_code: int = 200) -> None:
        self._lines = lines
        self.status_code = status_code

    def iter_lines(self, decode_unicode: bool = True):
        assert decode_unicode is True
        for line in self._lines:
            yield line


def _make_provider(
    *,
    endpoint: str = "https://api.anthropic.com/v1/messages",
    max_retries: int = 0,
) -> AnthropicProvider:
    """Build provider instances with deterministic test defaults."""
    return AnthropicProvider(
        AnthropicProviderConfig(
            endpoint=endpoint,
            api_key="dummy",
            model="claude-3-7-sonnet-latest",
            timeout_seconds=5,
            max_retries=max_retries,
            max_tokens=1024,
        )
    )


def test_generate_returns_text_for_valid_response_shape(monkeypatch) -> None:
    """Extract generated text from the first valid text content block."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["url"] = url
        observed["headers"] = headers
        observed["json"] = json
        observed["timeout"] = timeout
        return DummyResponse(
            {
                "content": [
                    {"type": "text", "text": "Echo: hello"},
                ]
            },
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    result = provider.generate("hello")

    assert result == "Echo: hello"
    assert observed["url"] == "https://api.anthropic.com/v1/messages"
    assert observed["json"]["model"] == "claude-3-7-sonnet-latest"
    assert observed["json"]["max_tokens"] == 1024
    assert observed["json"]["messages"][0]["role"] == "user"
    assert observed["json"]["messages"][0]["content"] == "hello"
    assert observed["timeout"] == 5


def test_generate_includes_system_field_when_provided(monkeypatch) -> None:
    """System prompt must be forwarded through Anthropic `system` payload field."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["payload"] = json
        return DummyResponse(
            {"content": [{"type": "text", "text": "ok"}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    assert provider.generate("hello", system_prompt="You are strict.") == "ok"
    assert observed["payload"]["system"] == "You are strict."


def test_generate_retries_then_succeeds(monkeypatch) -> None:
    """Transient transport errors should be retried up to max_retries."""
    provider = _make_provider(max_retries=2)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.ConnectionError("temporary network error")
        return DummyResponse(
            {"content": [{"type": "text", "text": "ok"}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    assert provider.generate("hello") == "ok"
    assert calls["count"] == 3


def test_generate_fails_after_retry_exhausted(monkeypatch) -> None:
    """Exhausted retries should raise a ProviderError with clear context."""
    provider = _make_provider(max_retries=1)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        raise requests.Timeout("timed out")

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    with pytest.raises(ProviderError, match="Provider request failed"):
        provider.generate("hello")

    assert calls["count"] == 2


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, AuthenticationError),
        (403, AuthorizationError),
        (429, RateLimitError),
        (503, UpstreamServerError),
    ],
)
def test_generate_maps_http_status_to_domain_errors(
    monkeypatch,
    status_code: int,
    expected_error: type[Exception],
) -> None:
    """Known HTTP statuses must map to stable domain exceptions."""
    provider = _make_provider(max_retries=2)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return DummyResponse({"error": "x"}, status_code=status_code)

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    with pytest.raises(expected_error):
        provider.generate("hello")

    # Deterministic status responses should fail immediately (no retries).
    assert calls["count"] == 1


def test_generate_maps_unknown_4xx_to_provider_error(monkeypatch) -> None:
    """Unexpected 4xx statuses should map to the generic ProviderError."""
    provider = _make_provider()

    def fake_post(*args, **kwargs):
        return DummyResponse({"error": "unused"}, status_code=418)

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    with pytest.raises(ProviderError, match="Provider returned HTTP 418."):
        provider.generate("hello")


def test_generate_rejects_invalid_json_response(monkeypatch) -> None:
    """A 200 response with invalid JSON must raise a ProviderError."""
    provider = _make_provider()

    class FakeResponse:
        status_code = 200

        def json(self):
            raise ValueError("invalid json")

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ProviderError, match="Provider returned invalid JSON."):
        provider.generate("hello")


def test_generate_rejects_missing_content_list(monkeypatch) -> None:
    """Response payload must include a non-empty content list."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyResponse({"response": "unused"}, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response must contain a non-empty 'content' list.",
    ):
        provider.generate("hello")


def test_generate_rejects_missing_text_content_block(monkeypatch) -> None:
    """At least one text content block must be present in response content."""
    provider = _make_provider()

    payload = {
        "content": [
            {"type": "tool_use", "id": "x"},
            {"type": "image", "source": {}},
        ]
    }
    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response must contain at least one text content block.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_string_text_block(monkeypatch) -> None:
    """Text content blocks must contain a string text field."""
    provider = _make_provider()

    payload = {"content": [{"type": "text", "text": 123}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider text content block must contain string 'text'.",
    ):
        provider.generate("hello")


def test_generate_ignores_non_object_content_blocks(monkeypatch) -> None:
    """Non-object content blocks should be skipped when a valid text block exists."""
    provider = _make_provider()

    payload = {
        "content": [
            123,
            {"type": "text", "text": "Echo: hello"},
        ]
    }
    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    assert provider.generate("hello") == "Echo: hello"


def test_generate_defensive_fallback_on_invalid_retry_config() -> None:
    """
    Defensive path coverage: if a caller constructs an invalid config
    (negative max_retries), the loop is skipped and fallback error is raised.
    """
    provider = _make_provider(max_retries=-1)

    with pytest.raises(ProviderError, match="Provider request failed unexpectedly."):
        provider.generate("hello")


def test_generate_stream_yields_chunks_and_enables_stream_flag(monkeypatch) -> None:
    """Stream mode must emit chunks from Anthropic SSE events and send stream=true."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout, stream):
        observed["url"] = url
        observed["headers"] = headers
        observed["json"] = json
        observed["timeout"] = timeout
        observed["stream"] = stream
        return DummyStreamResponse(
            [
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Echo: "}}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hello"}}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    chunks = list(provider.generate_stream("hello"))
    assert chunks == ["Echo: ", "hello"]
    assert observed["url"] == "https://api.anthropic.com/v1/messages"
    assert observed["json"]["stream"] is True
    assert observed["stream"] is True
    assert observed["timeout"] == 5


def test_generate_stream_includes_system_field_when_provided(monkeypatch) -> None:
    """Stream payload must include Anthropic `system` when system_prompt is provided."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout, stream):
        observed["payload"] = json
        return DummyStreamResponse(
            [
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    assert list(provider.generate_stream("hello", system_prompt="You are strict.")) == ["ok"]
    assert observed["payload"]["system"] == "You are strict."


def test_generate_stream_ignores_blank_and_non_data_lines(monkeypatch) -> None:
    """Parser should skip blank lines and SSE lines that are not `data:` payloads."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                "",
                "event: message",
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_ignores_non_text_delta_events(monkeypatch) -> None:
    """Events outside `content_block_delta` with `text_delta` should be ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"type":"message_start"}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_rejects_invalid_event_json(monkeypatch) -> None:
    """Invalid JSON in a stream event must raise ProviderError."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ["data: {not-json}", "data: [DONE]"],
            status_code=200,
        ),
    )

    with pytest.raises(ProviderError, match="Provider returned invalid streaming event JSON."):
        list(provider.generate_stream("hello"))


def test_generate_stream_retries_then_succeeds(monkeypatch) -> None:
    """Stream should retry transient transport failures before first emitted chunk."""
    provider = _make_provider(max_retries=2)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.ConnectionError("temporary network error")
        return DummyStreamResponse(
            [
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    assert list(provider.generate_stream("hello")) == ["ok"]
    assert calls["count"] == 3


def test_generate_stream_fails_after_retry_exhausted(monkeypatch) -> None:
    """Exhausted stream retries should raise a ProviderError with clear context."""
    provider = _make_provider(max_retries=1)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        raise requests.Timeout("timed out")

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    with pytest.raises(ProviderError, match="Provider request failed"):
        list(provider.generate_stream("hello"))

    assert calls["count"] == 2


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, AuthenticationError),
        (403, AuthorizationError),
        (429, RateLimitError),
        (503, UpstreamServerError),
    ],
)
def test_generate_stream_maps_http_status_to_domain_errors(
    monkeypatch,
    status_code: int,
    expected_error: type[Exception],
) -> None:
    """Known HTTP statuses must map to stable domain exceptions in stream mode."""
    provider = _make_provider(max_retries=2)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return DummyStreamResponse([], status_code=status_code)

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        fake_post,
    )

    with pytest.raises(expected_error):
        list(provider.generate_stream("hello"))

    # Deterministic status responses should fail immediately (no retries).
    assert calls["count"] == 1


def test_generate_stream_rejects_non_object_delta(monkeypatch) -> None:
    """`content_block_delta` events must include an object delta."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"type":"content_block_delta","delta":"invalid"}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming event must contain object 'delta'.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_rejects_non_string_delta_text(monkeypatch) -> None:
    """Delta text must be string when present."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"type":"content_block_delta","delta":{"type":"text_delta","text":123}}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming delta 'text' must be a string.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_raises_on_error_event_message(monkeypatch) -> None:
    """Provider `error` stream events must raise domain errors with message context."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"type":"error","error":{"message":"upstream failed"}}'],
            status_code=200,
        ),
    )

    with pytest.raises(ProviderError, match="Provider stream error: upstream failed"):
        list(provider.generate_stream("hello"))


def test_generate_stream_handles_none_lines(monkeypatch) -> None:
    """A None line from iter_lines should be skipped safely."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                None,
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_returns_when_stream_ends_without_done(monkeypatch) -> None:
    """Provider should return cleanly when stream ends without explicit [DONE]."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}'],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_defensive_fallback_on_invalid_retry_config() -> None:
    """Defensive branch: negative max_retries should hit fallback ProviderError."""
    provider = _make_provider(max_retries=-1)

    with pytest.raises(ProviderError, match="Provider request failed unexpectedly."):
        list(provider.generate_stream("hello"))


def test_generate_stream_rejects_non_object_event_payload(monkeypatch) -> None:
    """Each decoded stream event must be an object."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: ["invalid"]'],
            status_code=200,
        ),
    )

    with pytest.raises(ProviderError, match="Provider streaming event must be an object."):
        list(provider.generate_stream("hello"))


def test_generate_stream_ignores_event_with_non_string_type(monkeypatch) -> None:
    """Events with non-string `type` should be ignored safely."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"type":123}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_raises_on_error_event_without_message(monkeypatch) -> None:
    """`error` events without a usable message still raise ProviderError."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"type":"error","error":{"code":"bad_request"}}'],
            status_code=200,
        ),
    )

    with pytest.raises(ProviderError, match="Provider stream returned an error event."):
        list(provider.generate_stream("hello"))


def test_generate_stream_ignores_non_text_delta_type(monkeypatch) -> None:
    """Only `text_delta` is consumed for streamed text output."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"type":"content_block_delta","delta":{"type":"input_json_delta","partial_json":"{}"}}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_ignores_missing_delta_text(monkeypatch) -> None:
    """Missing `text` in a text_delta event should be ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.anthropic_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"type":"content_block_delta","delta":{"type":"text_delta"}}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]
