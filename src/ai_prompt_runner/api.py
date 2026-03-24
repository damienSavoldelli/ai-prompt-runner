"""Public Python API for one-shot prompt execution."""

from ai_prompt_runner.core.models import PromptRequest
from ai_prompt_runner.core.runner import PromptRunner
from ai_prompt_runner.services.provider_factory import create_provider


def run_prompt(
    prompt: str,
    *,
    provider: str = "openai",
    system_prompt: str | None = None,
    api_endpoint: str | None = None,
    api_key: str | None = None,
    api_model: str | None = None,
    stream: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    timeout_seconds: int | None = None,
    max_retries: int | None = None,
) -> dict:
    """
    Execute a prompt through the configured provider and return normalized payload.

    This function is intentionally thin and reuses the same execution pipeline as the CLI:
    provider creation -> PromptRunner -> normalized response contract.
    """
    runner_provider = create_provider(
        provider_name=provider,
        api_endpoint=api_endpoint,
        api_key=api_key,
        api_model=api_model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
    runner = PromptRunner(provider=runner_provider)

    request = PromptRequest(
        prompt_text=prompt,
        provider=provider,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        stream=stream,
    )

    # Library mode does not stream to stdout; callers consume final payload only.
    return runner.run(request=request)
