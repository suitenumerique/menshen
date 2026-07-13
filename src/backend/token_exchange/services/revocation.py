"""Menshen: services:revocation for the token_exchange application."""

import logging

from token_exchange.exceptions import TokenExchangeError

from .mixins import ExchangedTokenMixin

logger = logging.getLogger(__name__)


class RevocationService(ExchangedTokenMixin):
    """
    Token exchange revocation service.

    Use this service to revoke an exchanged token.

    Note that the request is supposed to be valid when submitted to this service.

    """

    @classmethod
    def revoke(cls, token: str, audience: str) -> None:
        """Generate token revocation response."""
        try:
            exchanged_token = cls.get_exchanged_token(token)
        except TokenExchangeError:
            logger.error("Token revocation failed (not found).")
            return

        if not cls.is_token_valid(exchanged_token, audience):
            logger.error("Token revocation failed (invalid token).")
            return

        exchanged_token.revoke()

        logger.info(
            "Token revoked: token_jti=%s, sub=%s, email=%s, type=%s, audiences=%s",
            exchanged_token.subject_token_jti,
            exchanged_token.subject_sub,
            exchanged_token.subject_email,
            exchanged_token.token_type,
            exchanged_token.audiences,
        )
