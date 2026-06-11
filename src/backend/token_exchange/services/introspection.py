"""Menshen: services:introspection for the token_exchange application."""

import logging

from django.core.exceptions import SuspiciousOperation

from token_exchange.exceptions import TokenExchangeExchangedTokenInstrospectionError
from token_exchange.models import (
    TOKEN_TYPE_HINT_CHOICES_MAPPING,
    ExchangedToken,
    ServiceProvider,
    TokenTypeChoices,
)
from token_exchange.services.token import TokenGenerator
from token_exchange.structs import IntrospectionResponse, TokenIntrospectionRequest

logger = logging.getLogger(__name__)


class TokenExchangeIntrospectionService:
    """
    Token exchange introspection service.

    Use this service to introspect an exchanged token.

    Note that the request is supposed to be valid when submitted to this service.

    """

    def __init__(self, service: ServiceProvider, request: TokenIntrospectionRequest):
        """
        Initialize the service.

        Args:
            service: the sources service performing the token introspection request
            request: the token introspection request

        """
        if service is None or request is None:
            raise TokenExchangeExchangedTokenInstrospectionError("Empty request or service.")

        self._service: ServiceProvider = service
        self._request: TokenIntrospectionRequest = request
        self._token: ExchangedToken | None = None

    @property
    def token(self) -> ExchangedToken:
        """Get introspection request token from the database."""
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
            logger.info("Introspected token not found.")
            raise TokenExchangeExchangedTokenInstrospectionError("Token not found.") from exc

        return self._token

    def is_token_valid(self) -> bool:
        """Check introspected token validity."""
        # Stored exchanged token validity
        try:
            is_valid_: bool = self.token.is_valid()
        except TokenExchangeExchangedTokenInstrospectionError:
            return False  # Token not found

        # Token has already expired or has been revoked
        if not is_valid_:
            logger.warning(
                "Token introspected (invalid): token_jti=%s, format=%s, kid=%s",
                self.token.subject_token_jti,
                self.token.token_type,
                self.token.jwt_kid or "N/A",
            )
            return False

        # Check token audiences against requesting service
        if self._service.audience_id not in self.token.audiences:
            logger.error(
                "'%s' service tried to introspect an exchanged token that is beyond its audience",
                self._service.audience_id,
            )
            raise SuspiciousOperation()

        # Not JWT case
        if self.token.token_type != TokenTypeChoices.JWT:
            return is_valid_

        # JWT signature verification
        try:
            TokenGenerator.verify_jwt(self.token.token)
        except ValueError as exc:
            logger.warning(
                "Token introspected: JWT signature verification failed: %s",
                str(exc),
            )
            return False
        return True

    def generate_introspection_response(self) -> IntrospectionResponse:
        """Generate token introspection response."""
        if not self.is_token_valid():
            return IntrospectionResponse(active=False)
        logger.info(
            "Token introspected (active): token_jti=%s, format=%s, kid=%s",
            self.token.subject_token_jti,
            self.token.token_type,
            self.token.jwt_kid or "N/A",
        )
        return self.token.to_introspection_response()
