"""Menshen: services:revocation for the token_exchange application."""

import structlog

from token_exchange.exceptions import TokenExchangeError
from token_exchange.models import ServiceProvider

from .mixins import ExchangedTokenMixin

logger = structlog.get_logger(__name__)


class RevocationService(ExchangedTokenMixin):
    """
    Token exchange revocation service.

    Use this service to revoke an exchanged token.

    Only the service that requested the exchanged token (the source service) is
    allowed to revoke it (RFC 7009 section 2.1).

    Note that the request is supposed to be valid when submitted to this service.

    """

    @classmethod
    def revoke(cls, token: str, source_service: ServiceProvider) -> None:
        """Generate token revocation response."""
        try:
            exchanged_token = cls.get_exchanged_token(token)
        except TokenExchangeError:
            logger.error("token_revocation_failed", reason="token_not_found")
            return

        if not exchanged_token.is_valid():
            logger.error("token_revocation_failed", reason="invalid_token")
            return

        # RFC 7009 (section 2.1): only the client the token was issued to can
        # revoke it. With RFC 8693, the token is issued to the service that
        # requested the exchange (the source service), not to its audiences.
        if exchanged_token.source_service_id != source_service.id:
            logger.error(
                "token_revocation_failed",
                reason="not_source_service",
                service=source_service.audience_id,
            )
            return

        exchanged_token.revoke()

        logger.info(
            "token_revoked",
            token_jti=exchanged_token.subject_token_jti,
            sub=exchanged_token.subject_sub,
            email=exchanged_token.subject_email,
            type=exchanged_token.token_type,
            audiences=exchanged_token.audiences,
        )
