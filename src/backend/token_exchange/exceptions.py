"""Menshen: exceptions for the token_exchange application."""

from rest_framework.exceptions import APIException


class TokenExchangeError(Exception):
    """Base exception for the module."""


class TokenExchangeResourceServerIntrospectionError(APIException):
    """Exception raised when subject token introspection fails."""

    status_code = 422
    default_detail = "Subject token introspection failed."
    default_code = "invalid_introspection"


class TokenExchangeConfigurationError(APIException):
    """Exception raised when server configuration is not valid."""

    status_code = 500
    default_detail = "Server configuration is missing or invalid."
    default_code = "invalid_configuration"


class TokenExchangeIntrospectionError(APIException):
    """Exception raise when a token introspection fails."""

    status_code = 400
    default_detail = "Token introspection failed."
    default_code = "invalid_token"


class TokenExchangeIssuingError(APIException):
    """Exception raised when an error occured during token issuing."""

    status_code = 500
    default_detail = "Server cannot issue requested exchange token."
    default_code = "issuing_error"


class TokenExchangeInvalidTargetError(APIException):
    """Exception raised when an invalid target is submitted in a token exchange request."""

    status_code = 400
    default_detail = "Invalid target audience."
    default_code = "invalid_target"


class TokenExchangeInvalidScopesError(APIException):
    """Exception raised when invalid scopes are submitted in a token exchange request."""

    status_code = 403
    default_detail = "Invalid scopes."
    default_code = "invalid_scopes"


class TokenExchangeInvalidActionError(APIException):
    """Exception raised when an invalid action is submitted in a token exchange request."""

    status_code = 403
    default_detail = "Invalid action."
    default_code = "invalid_action"


class ExchangedTokenInstrospectionError(TokenExchangeError):
    """Exception raised when exchanged token introspection failed."""
