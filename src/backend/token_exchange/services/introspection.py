"""Menshen: services:introspection for the token_exchange application."""

import logging
from functools import cached_property

from token_exchange.exceptions import ExchangedTokenInstrospectionError
from token_exchange.models import (
    ExchangedToken,
    ServiceProvider,
    TokenTypeChoices,
)
from token_exchange.services.token import TokenGenerator
from token_exchange.structs import IntrospectionRequest, IntrospectionResponse

logger = logging.getLogger(__name__)


class TokenExchangeIntrospectionService:
    """
    Token exchange introspection service.

    Use this service to introspect an exchanged token.

    Note that the request is supposed to be valid when submitted to this service.

    """

    def __init__(self, service: ServiceProvider, request: IntrospectionRequest):
        """
        Initialize the service.

        Args:
            service: the sources service performing the token introspection request
            request: the token introspection request

        """
        if service is None or request is None:
            raise ExchangedTokenInstrospectionError("Empty request or service.")

        self._service: ServiceProvider = service
        self._request: IntrospectionRequest = request

    @cached_property
    def exchanged_token(self) -> ExchangedToken:
        """Get introspection request token from the database."""
        try:
            token = ExchangedToken.objects.get(token=self._request.token)
        except ExchangedToken.DoesNotExist as exc:
            logger.info("Introspected token not found.")
            raise ExchangedTokenInstrospectionError("Token not found.") from exc

        return token

    def is_token_valid(self) -> bool:
        """Check introspected token validity."""
        # Stored exchanged token validity
        try:
            token = self.exchanged_token
        except ExchangedTokenInstrospectionError:
            return False  # Token not found

        # Token has already expired or has been revoked
        if not token.is_valid():
            logger.warning(
                "Token introspected (invalid): token_jti=%s, type=%s, kid=%s",
                token.subject_token_jti,
                token.token_type,
                token.jwt_kid or "N/A",
            )
            return False

        # Check token audiences against requesting service
        if self._service.audience_id not in token.audiences:
            logger.error(
                "'%s' service tried to introspect an exchanged token that is beyond its audience",
                self._service.audience_id,
            )
            return False

        # JWT case
        if token.token_type == TokenTypeChoices.JWT:
            # JWT signature verification
            try:
                TokenGenerator.verify_jwt(token.token)
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
            "Token introspected (active): token_jti=%s, type=%s, kid=%s",
            self.exchanged_token.subject_token_jti,
            self.exchanged_token.token_type,
            self.exchanged_token.jwt_kid or "N/A",
        )
        return self.exchanged_token.to_introspection_response()
