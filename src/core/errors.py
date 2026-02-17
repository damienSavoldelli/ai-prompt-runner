"""Custom exceptions for ai-prompt-runner."""


class PromptRunnerError(Exception):
    """Base exception for the application."""

class ProviderError(PromptRunnerError):
    """Raised when an AI provider request fails."""