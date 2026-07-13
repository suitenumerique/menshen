"""Menshen: services:introspection for the token_exchange application."""

import logging

from token_exchange.exceptions import TokenExchangeError
from token_exchange.structs import IntrospectionResponse

from .mixins import ExchangedTokenMixin

logger = logging.getLogger(__name__)


class IntrospectionService(ExchangedTokenMixin):
    """
    Token exchange introspection service.

    Use this service to introspect an exchanged token.

    Note that the request is supposed to be valid when submitted to this service.

    """

    @classmethod
    def introspect(cls, token: str, audience: str) -> IntrospectionResponse:
        """Introspect a given token for a service audience."""
        try:
            exchanged_token = cls.get_exchanged_token(token)
        except TokenExchangeError:
            logger.error("Token introspection failed (not found).")
            return IntrospectionResponse(active=False)

        if not cls.is_token_valid(exchanged_token, audience):
            logger.error("Token introspection failed (invalid token).")
            return IntrospectionResponse(active=False)

        logger.info(
            "Token introspected (active): token_jti=%s, type=%s, kid=%s",
            exchanged_token.subject_token_jti,
            exchanged_token.token_type,
            exchanged_token.jwt_kid or "N/A",
        )
        return exchanged_token.to_introspection_response()
