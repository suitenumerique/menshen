"""Menshen: services:revocation for the token_exchange application."""

import logging

from django.core.exceptions import SuspiciousOperation

from token_exchange.exceptions import TokenExchangeExchangedTokenRevocationError
from token_exchange.models import (
    TOKEN_TYPE_HINT_CHOICES_MAPPING,
    ExchangedToken,
    ServiceProvider,
)
from token_exchange.structs import TokenRevocationRequest

logger = logging.getLogger(__name__)


class TokenExchangeRevocationService:
    """
    Token exchange revocation service.

    Use this service to revoke an exchanged token.

    Note that the request is supposed to be valid when submitted to this service.

    """

    def __init__(self, service: ServiceProvider, request: TokenRevocationRequest):
        """
        Initialize the service.

        Args:
            service: the sources service performing the token revocation request
            request: the token revocation request

        """
        if service is None or request is None:
            raise TokenExchangeExchangedTokenRevocationError("Empty request or service.")

        self._service: ServiceProvider = service
        self._request: TokenRevocationRequest = request
        self._token: ExchangedToken | None = None

    @property
    def token(self) -> ExchangedToken:
        """Get request token from the database."""
        if self._token:
            return self._token

        # Token database request parameters
        db_kwargs = {"token": self._request.token}

        # Perform matching between TokenExchangeTokenTypeHint and TokenTypeChoices
        if (
            self._request.token_type_hint
            and self._request.token_type_hint in TOKEN_TYPE_HINT_CHOICES_MAPPING
            and TOKEN_TYPE_HINT_CHOICES_MAPPING[self._request.token_type_hint]
        ):
            # Add token type filtering
            db_kwargs.update(
                {"token_type": str(TOKEN_TYPE_HINT_CHOICES_MAPPING[self._request.token_type_hint])}
            )

        try:
            self._token = ExchangedToken.objects.get(**db_kwargs)
        except ExchangedToken.DoesNotExist as exc:
            logger.info("Token to revoke not found.")
            raise TokenExchangeExchangedTokenRevocationError("Token not found.") from exc

        return self._token

    def is_token_valid(self) -> bool:
        """Check token validity to ensure we to nothing if not."""
        try:
            is_valid_: bool = self.token.is_valid()
        except TokenExchangeExchangedTokenRevocationError:
            return False  # Token not found

        # Token has already expired or has been revoked
        if not is_valid_:
            logger.warning(
                "Token to revoke (invalid): token_jti=%s, type=%s, kid=%s",
                self.token.subject_token_jti,
                self.token.token_type,
                self.token.jwt_kid or "N/A",
            )
            return False

        # Check token audiences against requesting service
        if self._service.audience_id not in self.token.audiences:
            logger.error(
                "'%s' service tried to revoke an exchanged token that is beyond its audience",
                self._service.audience_id,
            )
            raise SuspiciousOperation()
        return True

    def revoke(self) -> None:
        """Generate token revocation response."""
        if not self.is_token_valid():
            logger.error("Token revocation failed (not found).")
            return

        self.token.revoke()

        logger.info(
            "Token revoked: token_jti=%s, sub=%s, email=%s, type=%s, audiences=%s",
            self.token.subject_token_jti,
            self.token.subject_sub,
            self.token.subject_email,
            self.token.token_type,
            self.token.audiences,
        )
