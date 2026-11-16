"""Menshen: authentication backends for the token_exchange application."""

import structlog
from django.http import HttpRequest
from ninja.errors import AuthenticationError
from ninja.security import HttpBasicAuth

from .models import ServiceProviderCredentials

logger = structlog.get_logger(__name__)


class ServiceProviderBasicAuthentication(HttpBasicAuth):
    """
    Authentication backend for the token exchanges API endpoints.

    A Service Provider can authenticate to have access to the endpoints.
    """

    def authenticate(self, request: HttpRequest, username: str, password: str):
        """Authenticate a service provider."""
        try:
            credentials = ServiceProviderCredentials.objects.select_related("service_provider").get(
                client_id=username,
            )
        except ServiceProviderCredentials.DoesNotExist as exc:
            logger.warning(
                "service_provider_authentication_failed",
                reason="unknown_client",
                client_id=username,
            )
            raise AuthenticationError(message="Service provider does not exist.") from exc

        if not credentials.is_active:
            logger.warning(
                "service_provider_authentication_failed",
                reason="inactive_client",
                client_id=username,
            )
            raise AuthenticationError(message="Service provider inactive.")

        if not credentials.check_client_secret(password):
            logger.warning(
                "service_provider_authentication_failed",
                reason="invalid_secret",
                client_id=username,
            )
            raise AuthenticationError(message="Invalid service provider credentials.")

        service_provider = credentials.service_provider
        structlog.contextvars.bind_contextvars(service_provider_id=str(service_provider.pk))
        return service_provider
