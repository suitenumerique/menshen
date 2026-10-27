"""Menshen: services:mixins for the token_exchange application."""

import logging

from token_exchange.exceptions import TokenExchangeError
from token_exchange.models import ExchangedToken
from token_exchange.utils import hash_token

logger = logging.getLogger(__name__)


class ExchangedTokenMixin:
    """
    A mixin to handle exchanged tokens.

    Use this mixin in services that need to access and perform actions on exchanged tokens.

    """

    @staticmethod
    def get_exchanged_token(token: str) -> ExchangedToken:
        """Get exchanged token from the database (tokens are stored hashed)."""
        try:
            exchanged_token = ExchangedToken.objects.select_related("source_service").get(
                token=hash_token(token)
            )
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

        # Note: JWT signature re-verification is not needed here since the token
        # is looked up by the exact hash of its value: a presented token can only
        # match a record we issued ourselves, and any alteration of the token
        # would result in a different hash (hence, a failed lookup).
        return True
