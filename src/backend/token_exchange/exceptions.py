"""Menshen: exceptions for the token_exchange application."""


class TokenExchangeError(Exception):
    """Base exception for the module."""


class ExchangedTokenIntrospectionError(TokenExchangeError):
    """Exception raised when exchanged token introspection failed."""


class ExchangedTokenRevocationError(TokenExchangeError):
    """Exception raised when echanged token revocation failed."""


class APIError(Exception):
    """Base API-related exception."""

    status_code: int = 500
    default_detail: str = "An error occured while processing your request."
    default_code: str = "unknown"

    def __init__(self, detail: str | None = None, code: str | None = None):
        """Set defaults."""
        self.detail: str = detail or self.default_detail
        self.code: str = code or self.default_code


class TokenExchangeResourceServerIntrospectionError(APIError):
    """Exception raised when subject token introspection fails."""

    status_code: int = 422
    default_detail: str = "Subject token introspection failed."
    default_code: str = "invalid_introspection"


class TokenExchangeConfigurationError(APIError):
    """Exception raised when server configuration is not valid."""

    status_code: int = 500
    default_detail: str = "Server configuration is missing or invalid."
    default_code: str = "invalid_configuration"


class TokenExchangeIntrospectionError(APIError):
    """Exception raise when a token introspection fails."""

    status_code: int = 400
    default_detail: str = "Token introspection failed."
    default_code: str = "invalid_token"


class TokenExchangeIssuingError(APIError):
    """Exception raised when an error occured during token issuing."""

    status_code: int = 500
    default_detail: str = "Server cannot issue requested exchange token."
    default_code: str = "issuing_error"


class TokenExchangeInvalidTargetError(APIError):
    """Exception raised when an invalid target is submitted in a token exchange request."""

    status_code: int = 400
    default_detail: str = "Invalid target audience."
    default_code: str = "invalid_target"


class TokenExchangeInvalidScopesError(APIError):
    """Exception raised when invalid scopes are submitted in a token exchange request."""

    status_code: int = 403
    default_detail: str = "Invalid scopes."
    default_code: str = "invalid_scopes"


class TokenExchangeInvalidActionError(APIError):
    """Exception raised when an invalid action is submitted in a token exchange request."""

    status_code: int = 403
    default_detail: str = "Invalid action."
    default_code: str = "invalid_action"
