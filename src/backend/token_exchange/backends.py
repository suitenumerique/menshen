"""Menshen: OIDC resource server backends for the token_exchange application."""

import structlog
from joserfc.jwt import Token
from lasuite.oidc_resource_server import backend as lasuite_backend

logger = structlog.get_logger(__name__)


class IntrospectionLoggingMixin:
    """
    Log the authorization server introspection response.

    The response is logged once decoded (and decrypted/verified for JWT
    introspection responses), with the debug level as it contains personal
    data (e.g. `sub` or `email`).
    """

    def _introspect(self, access_token: str) -> Token:
        """Introspect an access token and log the introspection response claims."""
        token = super()._introspect(access_token)  # ty: ignore[unresolved-attribute]
        logger.debug("subject_token_introspection_response", claims=token.claims)
        return token


class ResourceServerBackend(IntrospectionLoggingMixin, lasuite_backend.ResourceServerBackend):
    """Resource server backend for JSON introspection responses (RFC 7662)."""


class JWTResourceServerBackend(IntrospectionLoggingMixin, lasuite_backend.JWTResourceServerBackend):
    """Resource server backend for JWT introspection responses (RFC 9701)."""
