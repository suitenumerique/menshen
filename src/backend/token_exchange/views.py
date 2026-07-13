"""Menshen: views for the token_exchange application."""

import logging

import msgspec
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .authentication import ServiceProviderBasicAuthentication
from .permissions import IsServiceProviderAuthenticated
from .services.introspection import IntrospectionService
from .services.request import RequestService
from .services.revocation import RevocationService
from .structs import (
    IntrospectionRequest,
    IntrospectionResponse,
    RevocationRequest,
    TokenExchangeRequest,
)

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
        if request.content_type != "application/json":
            return Response(
                {
                    "error": "invalid_request",
                    "error_description": "Request content-type is not JSON.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token_exchange_request = msgspec.json.decode(request.body, type=TokenExchangeRequest)
        except (msgspec.ValidationError, msgspec.DecodeError) as err:
            return Response(
                {
                    "error": "invalid_request",
                    "error_description": str(err),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Forge token exchange response
        exchange_response, exchanged_token = RequestService.exchange(
            source_audience=source_service.audience_id, request=token_exchange_request, persist=True
        )

        # Log the exchange
        logger.info(
            "Token exchanged: sub=%s, email=%s, audiences=%s, token_type=%s, "
            "expires_at=%s, subject_jti=%s, kid=%s, scopes_granted=%s, grants=%s",
            exchanged_token.subject_sub,  # ty: ignore
            exchanged_token.subject_email,  # ty: ignore
            exchanged_token.audiences,  # ty: ignore
            exchanged_token.token_type,  # ty: ignore
            exchanged_token.expires_at,  # ty: ignore
            exchanged_token.subject_token_jti,  # ty: ignore
            exchanged_token.jwt_kid,  # ty: ignore
            exchanged_token.scope,  # ty: ignore
            exchanged_token.grants,  # ty: ignore
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

    def post(self, request):
        """
        Handle token introspection requests.

        Accepts a token and returns its validity and metadata.
        """
        # Retrieve authenticated service provider
        source_service = request.user

        # !!!!!!!!!!!!
        # EXPERIMENTAL
        # !!!!!!!!!!!!
        #
        # This is a temporary parsing solution preparing the django-bolt migration
        try:
            introspection_request = msgspec.json.decode(request.body, type=IntrospectionRequest)
        except msgspec.ValidationError:
            return Response(
                IntrospectionResponse(active=False).to_dict(),
                status=status.HTTP_200_OK,
            )
        introspection_response = IntrospectionService.introspect(
            introspection_request.token, source_service.audience_id
        )

        return Response(introspection_response.to_dict(), status=status.HTTP_200_OK)


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
        # Retrieve authenticated service provider
        source_service = request.user

        # !!!!!!!!!!!!
        # EXPERIMENTAL
        # !!!!!!!!!!!!
        #
        # This is a temporary parsing solution preparing the django-bolt migration
        try:
            token_revocation_request = msgspec.json.decode(request.body, type=RevocationRequest)
        except msgspec.ValidationError:
            # RFC 7009: Return 200 even for invalid requests
            return Response(status=status.HTTP_200_OK)

        RevocationService.revoke(token_revocation_request.token, source_service.audience_id)

        return Response(status=status.HTTP_200_OK)
