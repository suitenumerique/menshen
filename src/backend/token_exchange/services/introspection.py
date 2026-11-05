"""Menshen: services:introspection for the token_exchange application."""

import structlog

from token_exchange.exceptions import TokenExchangeError
from token_exchange.models import ServiceProvider
from token_exchange.schemas import IntrospectionResponse

from .mixins import ExchangedTokenMixin

logger = structlog.get_logger(__name__)


class IntrospectionService(ExchangedTokenMixin):
    """
    Token exchange introspection service.

    Use this service to introspect an exchanged token.

    Note that the request is supposed to be valid when submitted to this service.

    """

    @classmethod
    def introspect(cls, token: str, target_service: ServiceProvider) -> IntrospectionResponse:
        """Introspect a given token from a target service."""
        try:
            exchanged_token = cls.get_exchanged_token(token)
        except TokenExchangeError:
            logger.error("token_introspection_failed", reason="token_not_found")
            return IntrospectionResponse(active=False)

        if not cls.is_token_valid(exchanged_token, target_service.audience_id):
            logger.error("token_introspection_failed", reason="invalid_token")
            return IntrospectionResponse(active=False)

        logger.info(
            "token_introspected",
            token_jti=exchanged_token.subject_token_jti,
            type=exchanged_token.token_type,
            kid=exchanged_token.jwt_kid or "N/A",
        )
        return exchanged_token.to_introspection_response()
