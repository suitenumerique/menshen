"""Menshen: authentication backends for the token_exchange application."""

from rest_framework.authentication import BasicAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from .models import ServiceProviderCredentials


class ServiceProviderBasicAuthentication(BasicAuthentication):
    """
    Authentication backend for the token exchanges API endpoints.

    A Service Provider can authenticate to have access to the endpoints.
    """

    www_authenticate_realm = "token-exchange"

    def authenticate_credentials(self, userid: str, password: str, request: Request | None = None):
        """Authenticate a service provider."""
        try:
            credentials = ServiceProviderCredentials.objects.select_related("service_provider").get(
                client_id=userid,
                client_secret=password,
            )
        except ServiceProviderCredentials.DoesNotExist as exc:
            raise AuthenticationFailed("Service provider does not exist.") from exc

        if not credentials.is_active:
            raise AuthenticationFailed("Service provider inactive or deleted.")

        credentials.service_provider.is_authenticated = True

        return (credentials.service_provider, None)
