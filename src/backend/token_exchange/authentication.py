"""Menshen: authentication backends for the token_exchange application."""

from django.http import HttpRequest
from ninja.errors import AuthenticationError
from ninja.security import HttpBasicAuth

from .models import ServiceProviderCredentials


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
            raise AuthenticationError(message="Service provider does not exist.") from exc

        if not credentials.is_active:
            raise AuthenticationError(message="Service provider inactive.")

        if not credentials.check_client_secret(password):
            raise AuthenticationError(message="Invalid service provider credentials.")

        return credentials.service_provider
