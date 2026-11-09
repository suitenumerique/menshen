"""Menshen: exceptions for the oidc module."""


class IntrospectionInactiveTokenError(Exception):
    """Raised when the introspected token is not active."""
