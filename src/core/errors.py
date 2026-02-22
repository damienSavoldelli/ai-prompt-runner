"""Custom exceptions for ai-prompt-runner."""


class PromptRunnerError(Exception):
    """Base exception for the application."""

class ProviderError(PromptRunnerError):
    """Raised when an AI provider request fails."""
    
class AuthenticationError(ProviderError):
    """Raised when provider returns HTTP 401."""


class AuthorizationError(ProviderError):
    """Raised when provider returns HTTP 403."""


class RateLimitError(ProviderError):
    """Raised when provider returns HTTP 429."""


class UpstreamServerError(ProviderError):
    """Raised when provider returns HTTP 5xx."""