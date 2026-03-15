"""Application use case orchestration."""

from collections.abc import Callable
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from time import perf_counter

from ai_prompt_runner.core.errors import ProviderError
from ai_prompt_runner.core.models import (
    ExecutionContextMetadata,
    ExecutionRuntimeConfig,
    GenerationConfig,
    PromptRequest,
    PromptResponse,
    UsageMetadata,
)
from ai_prompt_runner.services.base import BaseProvider

from ai_prompt_runner.core.validators import validate_response_payload


class PromptRunner:
    """Runs prompts through a provider and returns normalized payload."""

    def __init__(self, provider: BaseProvider) -> None:
        self.provider = provider

    def _effective_prompt_for_provenance(self, request: PromptRequest) -> str:
        """
        Build deterministic prompt text used to compute provenance hash.

        This mirrors runtime prompt composition semantics:
        - with system prompt: SYSTEM + USER canonical representation
        - without system prompt: raw user prompt
        """
        if request.system_prompt is None:
            return request.prompt_text
        return f"SYSTEM:\n{request.system_prompt}\n\nUSER:\n{request.prompt_text}"

    def _prompt_hash(self, request: PromptRequest) -> str:
        """Return SHA256 digest for the effective prompt sent to providers."""
        digest = sha256(self._effective_prompt_for_provenance(request).encode("utf-8"))
        return f"sha256:{digest.hexdigest()}"

    def _runner_version(self) -> str:
        """Resolve installed runner package version for provenance metadata."""
        try:
            return version("ai-prompt-runner")
        except PackageNotFoundError:
            return "0.1.0-dev"

    def _resolve_provider_model_resolved(self) -> str | None:
        """
        Resolve provider-reported resolved model when available.

        Providers may not expose this (for example generic or local adapters),
        so this field is optional.
        """
        model_getter = getattr(self.provider, "get_last_model_resolved", None)
        if not callable(model_getter):
            return None

        model_resolved = model_getter()
        if model_resolved is None:
            return None
        if not isinstance(model_resolved, str):
            raise ProviderError("Provider resolved model metadata must be a string.")
        return model_resolved

    def _build_execution_context(
        self,
        request: PromptRequest,
    ) -> ExecutionContextMetadata:
        """Build additive execution provenance context from runner+provider state."""
        provider_config = getattr(self.provider, "config", None)
        api_endpoint = getattr(provider_config, "endpoint", None)
        timeout_seconds = getattr(provider_config, "timeout_seconds", None)
        max_retries = getattr(provider_config, "max_retries", None)
        model_requested = getattr(provider_config, "model", None)

        provider_protocol = getattr(self.provider, "provider_protocol", None)
        if provider_protocol is not None and not isinstance(provider_protocol, str):
            raise ProviderError("Provider protocol metadata must be a string.")
        if api_endpoint is not None and not isinstance(api_endpoint, str):
            raise ProviderError("Provider endpoint metadata must be a string.")
        if model_requested is not None and not isinstance(model_requested, str):
            raise ProviderError("Provider requested model metadata must be a string.")
        if timeout_seconds is not None and not isinstance(timeout_seconds, int):
            raise ProviderError("Provider timeout metadata must be an integer.")
        if max_retries is not None and not isinstance(max_retries, int):
            raise ProviderError("Provider retry metadata must be an integer.")

        runtime_config = ExecutionRuntimeConfig(
            stream=request.stream,
            system_prompt_provided=request.system_prompt is not None,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

        return ExecutionContextMetadata(
            provider_protocol=provider_protocol,
            api_endpoint=api_endpoint,
            model_requested=model_requested,
            model_resolved=self._resolve_provider_model_resolved(),
            runner_version=self._runner_version(),
            prompt_hash=self._prompt_hash(request),
            runtime=runtime_config,
        )

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

    def _resolve_provider_usage(self) -> UsageMetadata | None:
        """
        Resolve optional normalized usage from provider after a run.

        This keeps usage extraction in provider implementations while preserving
        a stable runner payload contract.
        """
        usage_getter = getattr(self.provider, "get_last_usage", None)
        if not callable(usage_getter):
            return None

        usage = usage_getter()
        if usage is None:
            return None
        if not isinstance(usage, UsageMetadata):
            raise ProviderError("Provider usage metadata must be a UsageMetadata object.")
        return usage

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
        usage = self._resolve_provider_usage()
        execution_context = self._build_execution_context(request)

        response = PromptResponse(
            prompt=request.prompt_text,
            response=answer_text,
            provider=request.provider,
            model=execution_context.model_resolved or execution_context.model_requested,
            execution_ms=execution_ms,
            usage=usage,
            execution_context=execution_context,
        )
        payload = response.to_dict()
        validate_response_payload(payload)
        return payload
