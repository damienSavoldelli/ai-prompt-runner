"""Application use case orchestration."""

from collections.abc import Callable
from time import perf_counter

from ai_prompt_runner.core.errors import ProviderError
from ai_prompt_runner.core.models import GenerationConfig, PromptRequest, PromptResponse
from ai_prompt_runner.services.base import BaseProvider

from ai_prompt_runner.core.validators import validate_response_payload


class PromptRunner:
    """Runs prompts through a provider and returns normalized payload."""

    def __init__(self, provider: BaseProvider) -> None:
        self.provider = provider

    def _resolve_generation_config(
        self,
        request: PromptRequest,
    ) -> GenerationConfig | None:
        """Build optional runtime controls payload for provider calls."""
        return request.generation_config()

    def _call_generate(self, request: PromptRequest) -> str:
        """Call provider.generate with optional system prompt passthrough."""
        generation_config = self._resolve_generation_config(request)

        if request.system_prompt is None:
            if generation_config is None:
                return self.provider.generate(prompt=request.prompt_text)
            return self.provider.generate(
                prompt=request.prompt_text,
                generation_config=generation_config,
            )
        if generation_config is None:
            return self.provider.generate(
                prompt=request.prompt_text,
                system_prompt=request.system_prompt,
            )
        return self.provider.generate(
            prompt=request.prompt_text,
            system_prompt=request.system_prompt,
            generation_config=generation_config,
        )

    def _generate_response_text(
        self,
        request: PromptRequest,
        on_stream_chunk: Callable[[str], None] | None,
    ) -> str:
        """Generate response text with optional streaming fallback behavior."""
        if not request.stream:
            return self._call_generate(request)

        generation_config = self._resolve_generation_config(request)

        # Keep stream support optional: if a provider does not implement
        # streaming, fallback to non-stream execution.
        stream_fn = getattr(self.provider, "generate_stream", None)
        if not callable(stream_fn):
            return self._call_generate(request)

        try:
            if request.system_prompt is None:
                if generation_config is None:
                    stream_iter = stream_fn(prompt=request.prompt_text)
                else:
                    stream_iter = stream_fn(
                        prompt=request.prompt_text,
                        generation_config=generation_config,
                    )
            else:
                if generation_config is None:
                    stream_iter = stream_fn(
                        prompt=request.prompt_text,
                        system_prompt=request.system_prompt,
                    )
                else:
                    stream_iter = stream_fn(
                        prompt=request.prompt_text,
                        system_prompt=request.system_prompt,
                        generation_config=generation_config,
                    )
        except NotImplementedError:
            return self._call_generate(request)

        chunks: list[str] = []
        for chunk in stream_iter:
            if not isinstance(chunk, str):
                raise ProviderError("Provider stream chunks must be strings.")
            chunks.append(chunk)
            if on_stream_chunk is not None:
                on_stream_chunk(chunk)
        return "".join(chunks)

    def run(
        self,
        request: PromptRequest,
        on_stream_chunk: Callable[[str], None] | None = None,
    ) -> dict:
        """Execute prompt request and return JSON-serializable payload."""
        start = perf_counter()
        answer_text = self._generate_response_text(
            request=request,
            on_stream_chunk=on_stream_chunk,
        )
        execution_ms = int((perf_counter() - start) * 1000)

        response = PromptResponse(
            prompt=request.prompt_text,
            response=answer_text,
            provider=request.provider,
            execution_ms=execution_ms,
        )
        payload = response.to_dict()
        validate_response_payload(payload)
        return payload
