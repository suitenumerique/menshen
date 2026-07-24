"""Menshen: views for the token_exchange application."""

import logging

from django.conf import settings
from django.http import HttpRequest
from ninja import Form, NinjaAPI
from ninja.throttling import AuthRateThrottle

from .authentication import ServiceProviderBasicAuthentication
from .exceptions import APIError
from .schemas import (
    IntrospectionRequest,
    IntrospectionResponse,
    RevocationRequest,
    TokenExchangeRequest,
    TokenExchangeResponse,
)
from .services.introspection import IntrospectionService
from .services.request import RequestService
from .services.revocation import RevocationService

logger = logging.getLogger(__name__)

# For every endpoint service should be authenticated
api = NinjaAPI(auth=ServiceProviderBasicAuthentication())


# Menshen API exception handler
#
# Inspired by DRF's APIException
@api.exception_handler(APIError)
def api_exception(request, exc):
    """Raise API exception error handler."""
    return api.create_response(
        request, {"detail": exc.detail, "code": exc.code}, status=exc.status_code
    )


@api.post(
    "/exchange/",
    response=TokenExchangeResponse,
    throttle=[AuthRateThrottle(settings.TOKEN_EXCHANGE_EXCHANGE_ENDPOINT_THROTTLE_RATE)],
)
def exchange(
    request: HttpRequest, token_exchange_request: Form[TokenExchangeRequest]
) -> TokenExchangeResponse:
    """
    RFC 8693 Token Exchange endpoint.

    This endpoint allows exchanging an external SSO token
    for a new token with different audiences, scopes,
    or lifetime.

    POST /auth/token/exchange/
        Exchange a token according to RFC 8693
    """
    # Authenticated service provider
    source_service = request.auth  # ty: ignore

    # Forge token exchange response
    exchange_response, _ = RequestService.exchange(
        source_audience=source_service.audience_id, request=token_exchange_request, persist=True
    )

    return exchange_response


@api.post("/introspect/", response=IntrospectionResponse, exclude_none=True)
def introspect(
    request: HttpRequest, introspection_request: Form[IntrospectionRequest]
) -> IntrospectionResponse:
    """
    RFC 7662 Token Introspection endpoint.

    This endpoint allows validating exchanged tokens and retrieving
    their metadata.

    POST /auth/token/introspect/
        Introspect a token according to RFC 7662
    """
    # Authenticated service provider
    source_service = request.auth  # ty: ignore
    return IntrospectionService.introspect(introspection_request.token, source_service.audience_id)


@api.post("/revoke/", response=None)
def revoke(request: HttpRequest, token_revocation_request: Form[RevocationRequest]) -> None:
    """
    RFC 7009 Token Revocation endpoint.

    This endpoint allows revoking exchanged tokens before their
    natural expiration.

    POST /auth/token/revoke/
        Revoke a token according to RFC 7009
    """
    # Authenticated service provider
    source_service = request.auth  # ty: ignore
    RevocationService.revoke(token_revocation_request.token, source_service.audience_id)
