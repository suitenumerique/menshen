"""Menshen: views for the token_exchange application."""

from http import HTTPStatus

import structlog
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from ninja import Form, NinjaAPI
from ninja.errors import Throttled, ValidationError
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

# For every endpoint service should be authenticated
api = NinjaAPI(
    auth=ServiceProviderBasicAuthentication(),
    docs_url=settings.TOKEN_EXCHANGE_API_DOCS_URL
    if settings.TOKEN_EXCHANGE_API_DOCS_ENABLED
    else None,
    openapi_url=settings.TOKEN_EXCHANGE_API_OPENAPI_URL
    if settings.TOKEN_EXCHANGE_API_OPENAPI_ENABLED
    else None,
)

logger = structlog.get_logger(__name__)


# Menshen API exception handler
#
# Inspired by DRF's APIException
@api.exception_handler(APIError)
def api_exception(request: HttpRequest, exc: APIError) -> HttpResponse:
    """Raise API exception error handler."""
    if exc.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        logger.error(
            "api_error",
            code=exc.code,
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.path,
            exc_info=exc,
        )
    else:
        logger.warning(
            "api_error",
            code=exc.code,
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.path,
        )
    return api.create_response(
        request, {"detail": exc.detail, "code": exc.code}, status=exc.status_code
    )


@api.exception_handler(ValidationError)
def validation_error(request: HttpRequest, exc: ValidationError) -> HttpResponse:
    """Log request validation errors and return django-ninja's default response."""
    # Only log the error location, type and message: the input value and the
    # context may contain submitted tokens.
    logger.warning(
        "request_validation_failed",
        path=request.path,
        errors=[
            {"loc": list(error.get("loc", [])), "type": error.get("type"), "msg": error.get("msg")}
            for error in exc.errors
        ],
    )
    return api.create_response(request, {"detail": exc.errors}, status=422)


@api.exception_handler(Throttled)
def throttled(request: HttpRequest, exc: Throttled) -> HttpResponse:
    """Log throttled requests and return django-ninja's default response."""
    logger.warning("request_throttled", path=request.path, wait=exc.wait)
    return api.create_response(request, {"detail": str(exc)}, status=exc.status_code)


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
        source_service=source_service, request=token_exchange_request, persist=True
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
    target_service = request.auth  # ty: ignore
    return IntrospectionService.introspect(introspection_request.token, target_service)


@api.post("/revoke/", response=None)
def revoke(request: HttpRequest, token_revocation_request: Form[RevocationRequest]) -> None:
    """
    RFC 7009 Token Revocation endpoint.

    This endpoint allows revoking exchanged tokens before their
    natural expiration. Only the service that requested the token
    exchange (the source service) is allowed to revoke a token.

    POST /auth/token/revoke/
        Revoke a token according to RFC 7009
    """
    # Authenticated service provider
    source_service = request.auth  # ty: ignore
    RevocationService.revoke(token_revocation_request.token, source_service)
