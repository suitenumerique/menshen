"""Menshen: services:mixins for the token_exchange application."""

import logging

from token_exchange.exceptions import TokenExchangeError
from token_exchange.models import ExchangedToken, TokenTypeChoices
from token_exchange.services.token import TokenGenerator

logger = logging.getLogger(__name__)


class ExchangedTokenMixin:
    """
    A mixin to handle exchanged tokens.

    Use this mixin in services that need to access and perform actions on exchanged tokens.

    """

    @staticmethod
    def get_exchanged_token(token: str) -> ExchangedToken:
        """Get exchanged token from the database."""
        try:
            exchanged_token = ExchangedToken.objects.get(token=token)
        except ExchangedToken.DoesNotExist as exc:
            logger.info("Token not found.")
            raise TokenExchangeError("Token not found.") from exc

        return exchanged_token

    @staticmethod
    def is_token_valid(token: ExchangedToken, audience: str) -> bool:
        """Check exchanged token validity."""
        # Token has already expired or has been revoked
        if not token.is_valid():
            logger.warning(
                "Token is invalid: token_jti=%s, type=%s, kid=%s",
                token.subject_token_jti,
                token.token_type,
                token.jwt_kid or "N/A",
            )
            return False

        # Check token audiences against requesting service
        if audience not in token.audiences:
            logger.error(
                "'%s' service tried to act on an exchanged token that is beyond its audience",
                audience,
            )
            return False

        # JWT case
        if token.token_type == TokenTypeChoices.JWT:
            # JWT signature verification
            try:
                TokenGenerator.verify_jwt(token.token)
            except ValueError as exc:
                logger.warning(
                    "JWT signature verification failed (%s)",
                    str(exc),
                )
                return False

        return True
