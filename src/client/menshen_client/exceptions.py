"""Menshen client: exceptions."""


class InvalidTokenError(ValueError):
    """Raised when a token is malformed or rejected by Menshen as such."""


class ResponseParsingError(Exception):
    """Raised when Menshen's client fails to parse the server response."""
