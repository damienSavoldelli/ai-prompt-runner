import pytest
import requests

from ai_prompt_runner.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    RateLimitError,
    UpstreamServerError,
)
from ai_prompt_runner.core.models import GenerationConfig
from ai_prompt_runner.services.openai_compatible_provider import (
    OpenAICompatibleProvider,
    OpenAICompatibleProviderConfig,
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
    endpoint: str = "https://api.openai.com/v1",
    max_retries: int = 0,
) -> OpenAICompatibleProvider:
    """Build provider instances with deterministic test defaults."""
    return OpenAICompatibleProvider(
        OpenAICompatibleProviderConfig(
            endpoint=endpoint,
            api_key="dummy",
            model="gpt-4o-mini",
            timeout_seconds=5,
            max_retries=max_retries,
        )
    )


def test_generate_returns_text_and_normalizes_endpoint(monkeypatch) -> None:
    """
    Validate nominal behavior:
    - the endpoint is normalized to /chat/completions
    - the provider extracts text from choices[0].message.content
    """
    provider = _make_provider(endpoint="https://api.openai.com/v1")
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["url"] = url
        observed["headers"] = headers
        observed["json"] = json
        observed["timeout"] = timeout
        return DummyResponse(
            {"choices": [{"message": {"content": "Echo: hello"}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    result = provider.generate("hello")

    assert result == "Echo: hello"
    assert observed["url"] == "https://api.openai.com/v1/chat/completions"
    assert observed["json"]["model"] == "gpt-4o-mini"
    assert observed["json"]["messages"][0]["role"] == "user"
    assert observed["json"]["messages"][0]["content"] == "hello"
    assert observed["timeout"] == 5


def test_generate_preserves_full_chat_completions_endpoint(monkeypatch) -> None:
    """
    If caller already provides /chat/completions, provider must not duplicate
    the suffix.
    """
    provider = _make_provider(
        endpoint="https://api.openai.com/v1/chat/completions",
    )
    called = {"url": ""}

    def fake_post(url, headers, json, timeout):
        called["url"] = url
        return DummyResponse(
            {"choices": [{"message": {"content": "ok"}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    assert provider.generate("hello") == "ok"
    assert called["url"] == "https://api.openai.com/v1/chat/completions"


def test_generate_includes_system_message_when_provided(monkeypatch) -> None:
    """System prompt must be serialized as the first role message."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["messages"] = json["messages"]
        return DummyResponse(
            {"choices": [{"message": {"content": "ok"}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    assert provider.generate("hello", system_prompt="You are strict.") == "ok"
    assert observed["messages"][0] == {"role": "system", "content": "You are strict."}
    assert observed["messages"][1] == {"role": "user", "content": "hello"}


def test_generate_includes_runtime_controls_when_provided(monkeypatch) -> None:
    """Runtime controls should be forwarded to OpenAI-compatible payload keys."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["payload"] = json
        return DummyResponse(
            {"choices": [{"message": {"content": "ok"}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    result = provider.generate(
        "hello",
        generation_config=GenerationConfig(
            temperature=0.2,
            max_tokens=120,
            top_p=0.95,
        ),
    )

    assert result == "ok"
    assert observed["payload"]["temperature"] == 0.2
    assert observed["payload"]["max_tokens"] == 120
    assert observed["payload"]["top_p"] == 0.95


def test_generate_extracts_usage_metadata(monkeypatch) -> None:
    """Usage counters must be normalized and exposed via provider hook."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(
            {
                "choices": [{"message": {"content": "ok"}}],
                "model": "gpt-4o-mini-2026-02-15",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
            status_code=200,
        ),
    )

    assert provider.generate("hello") == "ok"
    usage = provider.get_last_usage()
    assert usage is not None
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 20
    assert usage.total_tokens == 30
    assert provider.get_last_model_resolved() == "gpt-4o-mini-2026-02-15"


def test_generate_retries_then_succeeds(monkeypatch) -> None:
    """Transient transport errors should be retried up to max_retries."""
    provider = _make_provider(max_retries=2)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.ConnectionError("temporary network error")
        return DummyResponse(
            {"choices": [{"message": {"content": "ok"}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
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
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
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
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
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
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
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
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ProviderError, match="Provider returned invalid JSON."):
        provider.generate("hello")


def test_generate_rejects_missing_choices(monkeypatch) -> None:
    """Response payload must include a non-empty choices list."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyResponse({"response": "unused"}, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response must contain a non-empty 'choices' list.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_string_message_content(monkeypatch) -> None:
    """content must be a plain string to satisfy provider contract."""
    provider = _make_provider()

    payload = {"choices": [{"message": {"content": 123}}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response message must contain string 'content'.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_object_choice(monkeypatch) -> None:
    """Each choice entry must be an object."""
    provider = _make_provider()

    payload = {"choices": [123]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response choice must be an object.",
    ):
        provider.generate("hello")


def test_generate_rejects_missing_message_object(monkeypatch) -> None:
    """Each choice must include a message object."""
    provider = _make_provider()

    payload = {"choices": [{}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response choice must contain a 'message' object.",
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


def test_generate_stream_yields_chunks_and_enables_stream_flag(monkeypatch) -> None:
    """Stream mode must emit chunks from SSE events and send stream=true in payload."""
    provider = _make_provider(endpoint="https://api.openai.com/v1")
    observed = {}

    def fake_post(url, headers, json, timeout, stream):
        observed["url"] = url
        observed["json"] = json
        observed["stream"] = stream
        observed["timeout"] = timeout
        return DummyStreamResponse(
            [
                'data: {"choices":[{"delta":{"content":"Echo: "}}]}',
                'data: {"choices":[{"delta":{"content":"hello"}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    chunks = list(provider.generate_stream("hello"))
    assert chunks == ["Echo: ", "hello"]
    assert observed["url"] == "https://api.openai.com/v1/chat/completions"
    assert observed["json"]["stream"] is True
    assert observed["stream"] is True
    assert observed["timeout"] == 5


def test_generate_stream_includes_system_message_when_provided(monkeypatch) -> None:
    """Stream payload must include system role message when system_prompt is provided."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout, stream):
        observed["messages"] = json["messages"]
        return DummyStreamResponse(
            [
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    assert list(provider.generate_stream("hello", system_prompt="You are strict.")) == ["ok"]
    assert observed["messages"][0] == {"role": "system", "content": "You are strict."}
    assert observed["messages"][1] == {"role": "user", "content": "hello"}


def test_generate_stream_includes_runtime_controls_and_stream_options(monkeypatch) -> None:
    """Stream payload should include runtime controls and usage stream options."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout, stream):
        observed["payload"] = json
        return DummyStreamResponse(
            [
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    chunks = list(
        provider.generate_stream(
            "hello",
            generation_config=GenerationConfig(
                temperature=0.2,
                max_tokens=120,
                top_p=0.95,
            ),
        )
    )

    assert chunks == ["ok"]
    assert observed["payload"]["temperature"] == 0.2
    assert observed["payload"]["max_tokens"] == 120
    assert observed["payload"]["top_p"] == 0.95
    assert observed["payload"]["stream_options"] == {"include_usage": True}


def test_generate_stream_extracts_usage_metadata(monkeypatch) -> None:
    """Usage metadata from stream events should be captured and normalized."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                'data: {"model":"gpt-4o-mini-2026-02-15","usage":{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30}}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]
    usage = provider.get_last_usage()
    assert usage is not None
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 20
    assert usage.total_tokens == 30
    assert provider.get_last_model_resolved() == "gpt-4o-mini-2026-02-15"


def test_generate_stream_ignores_blank_and_non_data_lines(monkeypatch) -> None:
    """Parser should skip blank lines and SSE lines that are not `data:` payloads."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                "",
                "event: message",
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_ignores_delta_events_without_content(monkeypatch) -> None:
    """Delta events without content are valid and should be ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"choices":[{"delta":{"role":"assistant"}}]}',
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
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
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
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
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
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
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    with pytest.raises(ProviderError, match="Provider request failed"):
        list(provider.generate_stream("hello"))

    assert calls["count"] == 2


def test_generate_stream_ignores_event_without_choices(monkeypatch) -> None:
    """Events without `choices` are allowed and should be ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"event":"ping"}',
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_rejects_non_object_event_payload(monkeypatch) -> None:
    """Each decoded stream event must be an object."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: ["invalid"]'],
            status_code=200,
        ),
    )

    with pytest.raises(ProviderError, match="Provider streaming event must be an object."):
        list(provider.generate_stream("hello"))


def test_generate_stream_rejects_non_list_choices(monkeypatch) -> None:
    """Streaming event `choices` must be a list when present."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"choices":"invalid"}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming event must contain list 'choices'.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_ignores_empty_choices(monkeypatch) -> None:
    """Empty choices arrays are allowed and should be ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"choices":[]}',
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_rejects_non_object_choice(monkeypatch) -> None:
    """The first streaming choice must be an object."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"choices":[123]}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming choice must be an object.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_ignores_event_without_delta(monkeypatch) -> None:
    """Streaming choices without `delta` should be ignored."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                'data: {"choices":[{"message":{"content":"ignore"}}]}',
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_rejects_non_object_delta(monkeypatch) -> None:
    """When present, `delta` must be an object."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"choices":[{"delta":"invalid"}]}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming choice must contain object 'delta'.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_rejects_non_string_delta_content(monkeypatch) -> None:
    """Delta content must be text when provided."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"choices":[{"delta":{"content":123}}]}'],
            status_code=200,
        ),
    )

    with pytest.raises(
        ProviderError,
        match="Provider streaming delta 'content' must be a string.",
    ):
        list(provider.generate_stream("hello"))


def test_generate_stream_handles_none_lines(monkeypatch) -> None:
    """A None line from iter_lines should be skipped safely."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            [
                None,
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            ],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_returns_when_stream_ends_without_done(monkeypatch) -> None:
    """Provider should return cleanly when stream ends without an explicit [DONE]."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyStreamResponse(
            ['data: {"choices":[{"delta":{"content":"ok"}}]}'],
            status_code=200,
        ),
    )

    assert list(provider.generate_stream("hello")) == ["ok"]


def test_generate_stream_defensive_fallback_on_invalid_retry_config() -> None:
    """Defensive branch: negative max_retries should hit fallback ProviderError."""
    provider = _make_provider(max_retries=-1)

    with pytest.raises(ProviderError, match="Provider request failed unexpectedly."):
        list(provider.generate_stream("hello"))
