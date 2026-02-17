"""Application use case orchestration."""

from src.core.models import PromptRequest, PromptResponse
from src.services.base import BaseProvider


class PromptRunner:
    """Runs prompts through a provider and returns normalized payload."""

    def __init__(self, provider: BaseProvider) -> None:
        self.provider = provider

    def run(self, request: PromptRequest) -> dict:
        """Execute prompt request and return JSON-serializable payload."""
        answer_text = self.provider.generate(prompt=request.prompt_text)

        response = PromptResponse(
            prompt=request.prompt_text,
            response=answer_text,
            provider=request.provider,
        )
        return response.to_dict()