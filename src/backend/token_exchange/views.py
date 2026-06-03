"""Menshen: views for the token_exchange application."""

import logging
from datetime import timedelta

import msgspec
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .authentication import ServiceProviderBasicAuthentication
from .models import (
    ExchangedToken,
    IntrospectionResponse,
    TokenTypeChoices,
)
from .permissions import IsServiceProviderAuthenticated
from .serializers import TokenRevocationSerializer
from .services.request import TokenExchangeRequestService
from .structs import TokenExchangeRequest, TokenExchangeResponse
from .token_generator import TokenGenerator

logger = logging.getLogger(__name__)


class TokenExchangeView(APIView):
    """
    RFC 8693 Token Exchange endpoint.

    This endpoint allows exchanging an external SSO token
    for a new token with different audiences, scopes,
    or lifetime.

    POST /auth/token/exchange/
        Exchange a token according to RFC 8693
    """

    authentication_classes = [ServiceProviderBasicAuthentication]
    permission_classes = [IsServiceProviderAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    parser_classes = [FormParser, JSONParser]
    throttle_scope = "token_exchange"

    def post(self, request):  # noqa: PLR0911, PLR0912, PLR0915
        """
        Handle token exchange requests.

        Validates the request, checks scopes, generates a new token,
        and returns an RFC 8693 compliant response.
        """
        # Retrieve authenticated service provider
        source_service = request.user

        # !!!!!!!!!!!!
        # EXPERIMENTAL
        # !!!!!!!!!!!!
        #
        # This is a temporary parsing solution preparing the django-bolt migration
        try:
            token_exchange_request = msgspec.json.decode(request.body, type=TokenExchangeRequest)
        except msgspec.ValidationError as err:
            return Response(
                {
                    "error": "invalid_request",
                    "error_description": str(err),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Forge token exchange response
        token_exchange_request_service = TokenExchangeRequestService(
            service=source_service, request=token_exchange_request
        )
        exchange_response: TokenExchangeResponse = (
            token_exchange_request_service.generate_exchange_response()
        )

        # Create ExchangedToken record
        expires_at = timezone.now() + timedelta(seconds=exchange_response.expires_in)

        exchanged_token = ExchangedToken.objects.create(
            token=exchange_response.access_token,
            token_type=exchange_response.issued_token_type,
            jwt_kid=token_exchange_request_service.kid,
            subject_sub=token_exchange_request_service.user_info.sub,
            subject_email=token_exchange_request_service.user_info.email,
            audiences=token_exchange_request_service.audiences,
            scope=exchange_response.scope,
            grants=[grant.to_dict() for grant in token_exchange_request_service.grants],
            expires_at=expires_at,
            actor_token=token_exchange_request.actor_token
            if token_exchange_request.actor_token is not None
            else "",
            may_act=None,  # TODO: Parse from actor_token if needed  # noqa: FIX002
            subject_token_jti=token_exchange_request_service.user_info.jti,
            subject_token_scope=token_exchange_request_service.user_info.scope,
        )

        # Log the exchange
        logger.info(
            "Token exchanged: sub=%s, email=%s, audiences=%s, token_type=%s, "
            "expires_at=%s, subject_jti=%s, kid=%s, scopes_granted=%s, grants=%s",
            exchanged_token.subject_sub,
            exchanged_token.subject_email,
            exchanged_token.audiences,
            exchanged_token.token_type,
            exchanged_token.expires_at,
            exchanged_token.subject_token_jti,
            exchanged_token.jwt_kid,
            exchanged_token.scope,
            exchanged_token.grants,
        )

        return Response(exchange_response.to_dict(), status=status.HTTP_200_OK)


class TokenIntrospectionView(APIView):
    """
    RFC 7662 Token Introspection endpoint.

    This endpoint allows validating exchanged tokens and retrieving
    their metadata.

    POST /auth/token/introspect/
        Introspect a token according to RFC 7662
    """

    authentication_classes = [ServiceProviderBasicAuthentication]
    permission_classes = [IsServiceProviderAuthenticated]

    @staticmethod
    def _to_response(
        introspection_response: IntrospectionResponse, status: int = status.HTTP_200_OK
    ) -> Response:
        """Serialize the introspection response to a proper Django HTTP response."""
        return Response(introspection_response.to_dict(), status=status)

    def post(self, request):
        """
        Handle token introspection requests.

        Accepts a token and returns its validity and metadata.
        """
        # Default response payload
        inactive_introspection_response = IntrospectionResponse(active=False)

        # Get token from request (form-encoded or JSON)
        token = request.data.get("token")
        if not token:
            return self._to_response(inactive_introspection_response)

        # Look up the token
        try:
            exchanged_token = ExchangedToken.objects.get(token=token)
        except ExchangedToken.DoesNotExist:
            logger.info("Token introspected: token not found, active=False")
            return self._to_response(inactive_introspection_response)

        # Check if valid
        if not exchanged_token.is_valid():
            logger.info(
                "Token introspected: token_jti=%s, active=False, format=%s [invalid]",
                exchanged_token.subject_token_jti,
                exchanged_token.token_type,
            )
            return self._to_response(inactive_introspection_response)

        # For JWT tokens, verify signature
        if exchanged_token.token_type == TokenTypeChoices.JWT:
            try:
                TokenGenerator.verify_jwt(token)
            except ValueError as exc:
                logger.warning(
                    "Token introspected: JWT signature verification failed: %s",
                    str(exc),
                )
                return self._to_response(inactive_introspection_response)

        introspection_response = exchanged_token.to_introspection_response()
        logger.info(
            "Token introspected: token_jti=%s, active=%s, format=%s, kid=%s",
            exchanged_token.subject_token_jti,
            introspection_response.active,
            exchanged_token.token_type,
            exchanged_token.jwt_kid or "N/A",
        )
        return self._to_response(introspection_response)


class TokenRevocationView(APIView):
    """
    RFC 7009 Token Revocation endpoint.

    This endpoint allows revoking exchanged tokens before their
    natural expiration.

    POST /auth/token/revoke/
        Revoke a token according to RFC 7009
    """

    authentication_classes = [ServiceProviderBasicAuthentication]
    permission_classes = [IsServiceProviderAuthenticated]

    def post(self, request):
        """
        Handle token revocation requests.

        Accepts a token and revokes it.
        """
        # Validate request
        serializer = TokenRevocationSerializer(data=request.data)
        if not serializer.is_valid():
            # RFC 7009: Return 200 even for invalid requests
            return Response(status=status.HTTP_200_OK)

        token = serializer.validated_data["token"]

        # Look up the token
        try:
            exchanged_token = ExchangedToken.objects.get(
                token=token,
            )
        except ExchangedToken.DoesNotExist:
            # RFC 7009: Silent success even if token doesn't exist
            logger.info("Token revocation attempted: token not found")
            return Response(status=status.HTTP_200_OK)

        # Revoke the token
        exchanged_token.revoke()

        logger.info(
            "Token revoked: token_jti=%s, sub=%s, email=%s, type=%s, audiences=%s",
            exchanged_token.subject_token_jti,
            exchanged_token.subject_sub,
            exchanged_token.subject_email,
            exchanged_token.token_type,
            exchanged_token.audiences,
        )

        return Response(status=status.HTTP_200_OK)
