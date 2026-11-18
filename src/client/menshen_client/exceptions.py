"""Menshen client: exceptions."""


class MenshenClientError(Exception):
    """Base class for all Menshen client errors."""


class InvalidTokenError(MenshenClientError, ValueError):
    """Raised when a token is malformed or rejected by Menshen as such."""


class ResponseParsingError(MenshenClientError):
    """Raised when Menshen's client fails to parse the server response."""


class APIError(MenshenClientError):
    """Raised when Menshen responds with an error status code."""

    def __init__(self, message: str, *, status_code: int, url: str, body: str) -> None:
        """Instantiate the error with the failed response details."""
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.body = body


class ServerUnavailableError(MenshenClientError):
    """Raised when Menshen cannot be reached (network or transport failure)."""


class ServerTimeoutError(ServerUnavailableError):
    """Raised when a request to Menshen times out."""
