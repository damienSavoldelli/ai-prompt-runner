import pytest
import requests

from ai_prompt_runner.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    RateLimitError,
    UpstreamServerError,
)
from ai_prompt_runner.services.google_provider import (
    GoogleProvider,
    GoogleProviderConfig,
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
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta/models",
    max_retries: int = 0,
) -> GoogleProvider:
    """Build provider instances with deterministic test defaults."""
    return GoogleProvider(
        GoogleProviderConfig(
            endpoint=endpoint,
            api_key="dummy",
            model="gemini-2.5-flash",
            timeout_seconds=5,
            max_retries=max_retries,
        )
    )


def test_generate_returns_text_and_normalizes_endpoint(monkeypatch) -> None:
    """Extract generated text and build expected generateContent endpoint."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["url"] = url
        observed["headers"] = headers
        observed["json"] = json
        observed["timeout"] = timeout
        return DummyResponse(
            {
                "candidates": [
                    {"content": {"parts": [{"text": "Echo: hello"}]}}
                ]
            },
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        fake_post,
    )

    result = provider.generate("hello")

    assert result == "Echo: hello"
    assert (
        observed["url"]
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    )
    assert observed["json"]["contents"][0]["parts"][0]["text"] == "hello"
    assert observed["timeout"] == 5


def test_generate_includes_system_instruction_when_provided(monkeypatch) -> None:
    """System prompt must be mapped to Gemini `systemInstruction` payload."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["payload"] = json
        return DummyResponse(
            {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        fake_post,
    )

    assert provider.generate("hello", system_prompt="You are strict.") == "ok"
    assert observed["payload"]["systemInstruction"]["parts"][0]["text"] == "You are strict."


def test_generate_retries_then_succeeds(monkeypatch) -> None:
    """Transient transport errors should be retried up to max_retries."""
    provider = _make_provider(max_retries=2)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.ConnectionError("temporary network error")
        return DummyResponse(
            {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ProviderError, match="Provider returned invalid JSON."):
        provider.generate("hello")


def test_generate_rejects_missing_candidates_list(monkeypatch) -> None:
    """Response payload must include a non-empty candidates list."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse({"response": "unused"}, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response must contain a non-empty 'candidates' list.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_object_candidate(monkeypatch) -> None:
    """Each candidate entry must be an object."""
    provider = _make_provider()

    payload = {"candidates": [123]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response candidate must be an object.",
    ):
        provider.generate("hello")


def test_generate_rejects_missing_content_object(monkeypatch) -> None:
    """Each candidate must include a content object."""
    provider = _make_provider()

    payload = {"candidates": [{}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response candidate must contain a 'content' object.",
    ):
        provider.generate("hello")


def test_generate_rejects_missing_parts_list(monkeypatch) -> None:
    """Candidate content must include a non-empty parts list."""
    provider = _make_provider()

    payload = {"candidates": [{"content": {}}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response content must contain a non-empty 'parts' list.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_object_part(monkeypatch) -> None:
    """Each part entry must be an object."""
    provider = _make_provider()

    payload = {"candidates": [{"content": {"parts": [123]}}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response part must be an object.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_string_part_text(monkeypatch) -> None:
    """Part text must be a string to satisfy provider contract."""
    provider = _make_provider()

    payload = {"candidates": [{"content": {"parts": [{"text": 123}]}}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response part must contain string 'text'.",
    ):
        provider.generate("hello")


def test_generate_defensive_fallback_on_invalid_retry_config() -> None:
    """
    Defensive path coverage: if a caller constructs an invalid config
    (negative max_retries), the loop is skipped and fallback error is raised.
    """
    provider = _make_provider(max_retries=-1)

    with pytest.raises(ProviderError, match="Provider request failed unexpectedly."):
        provider.generate("hello")


def test_generate_stream_yields_chunks_and_uses_stream_endpoint(monkeypatch) -> None:
    """Stream mode must emit chunks and target streamGenerateContent SSE endpoint."""
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
                'data: {"candidates":[{"content":{"parts":[{"text":"Echo: "}]}}]}',
                'data: {"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        fake_post,
    )

    chunks = list(provider.generate_stream("hello"))
    assert chunks == ["Echo: ", "hello"]
    assert (
        observed["url"]
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse"
    )
    assert observed["stream"] is True
    assert observed["timeout"] == 5


def test_generate_stream_includes_system_instruction_when_provided(monkeypatch) -> None:
    """Stream payload must include Gemini `systemInstruction` when provided."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout, stream):
        observed["payload"] = json
        return DummyStreamResponse(
            [
                'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        fake_post,
    )

    assert list(provider.generate_stream("hello", system_prompt="You are strict.")) == ["ok"]
    assert observed["payload"]["systemInstruction"]["parts"][0]["text"] == "You are strict."


def test_generate_stream_joins_multiple_text_parts(monkeypatch) -> None:
    """All text parts in the first candidate should be joined into one chunk."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"candidates":[{"content":{"parts":[{"text":"hello"},{"text":" world"}]}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["hello world"]


def test_generate_stream_ignores_blank_and_non_data_lines(monkeypatch) -> None:
    """Parser should skip blank lines and non-`data:` SSE lines."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                "",
                "event: message",
                'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_ignores_event_without_candidates(monkeypatch) -> None:
    """Events without candidates should be ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"event":"ping"}',
                'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}',
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
        "ai_prompt_runner.services.google_provider.requests.post",
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
                'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
        fake_post,
    )

    with pytest.raises(expected_error):
        list(provider.generate_stream("hello"))

    # Deterministic status responses should fail immediately (no retries).
    assert calls["count"] == 1


def test_generate_stream_rejects_non_object_event_payload(monkeypatch) -> None:
    """Each decoded stream event must be an object."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: ["invalid"]'],
            status_code=200,
        ),
    )

    with pytest.raises(ProviderError, match="Provider streaming event must be an object."):
        list(provider.generate_stream("hello"))


def test_generate_stream_raises_on_error_event_message(monkeypatch) -> None:
    """Provider `error` events must raise domain errors with message context."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"error":{"message":"upstream failed"}}'],
            status_code=200,
        ),
    )

    with pytest.raises(ProviderError, match="Provider stream error: upstream failed"):
        list(provider.generate_stream("hello"))


def test_generate_stream_raises_on_error_event_without_message(monkeypatch) -> None:
    """Error events without message should still raise ProviderError."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"error":{"code":"bad_request"}}'],
            status_code=200,
        ),
    )

    with pytest.raises(ProviderError, match="Provider stream returned an error event."):
        list(provider.generate_stream("hello"))


def test_generate_stream_rejects_non_list_candidates(monkeypatch) -> None:
    """Candidates must be a list when present."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"candidates":"invalid"}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming event must contain list 'candidates'.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_ignores_empty_candidates(monkeypatch) -> None:
    """Empty candidates arrays are allowed and should be ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"candidates":[]}',
                'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_rejects_non_object_candidate(monkeypatch) -> None:
    """Each candidate entry must be an object."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"candidates":[123]}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming candidate must be an object.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_rejects_missing_content_object(monkeypatch) -> None:
    """Candidate must include a content object."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"candidates":[{}]}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming candidate must contain a 'content' object.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_rejects_non_list_parts(monkeypatch) -> None:
    """Stream content must contain list `parts`."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"candidates":[{"content":{"parts":"invalid"}}]}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming content must contain list 'parts'.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_ignores_empty_parts(monkeypatch) -> None:
    """Empty parts arrays should be ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"candidates":[{"content":{"parts":[]}}]}',
                'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_rejects_non_object_part(monkeypatch) -> None:
    """Each part must be an object."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"candidates":[{"content":{"parts":[123]}}]}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming part must be an object.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_ignores_parts_without_text(monkeypatch) -> None:
    """Parts without `text` are ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"candidates":[{"content":{"parts":[{"inlineData":{}}]}}]}',
                'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_rejects_non_string_part_text(monkeypatch) -> None:
    """Part text must be string when present."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"candidates":[{"content":{"parts":[{"text":123}]}}]}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming part text must be a string.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_handles_none_lines(monkeypatch) -> None:
    """A None line from iter_lines should be skipped safely."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                None,
                'data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}',
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
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}'],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_defensive_fallback_on_invalid_retry_config() -> None:
    """Defensive branch: negative max_retries should hit fallback ProviderError."""
    provider = _make_provider(max_retries=-1)

    with pytest.raises(ProviderError, match="Provider request failed unexpectedly."):
        list(provider.generate_stream("hello"))
