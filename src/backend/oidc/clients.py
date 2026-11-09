"""Menshen: authorization server clients for the oidc module."""

import httpx2
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from joserfc.jwk import KeySet


class AuthorizationServerClient:
    """
    Client for an OAuth 2.0 authorization server using JSON introspection responses.

    Reference: https://www.rfc-editor.org/info/rfc7662
    """

    accept_header: str = "application/json"

    def __init__(self, transport: httpx2.BaseTransport | None = None):
        """Read configuration from settings, an HTTP transport can be injected (tests)."""
        self.url = settings.OIDC_OP_URL
        self._url_introspection = settings.OIDC_OP_INTROSPECTION_ENDPOINT
        self._transport = transport

        missing = [
            name
            for name, value in [
                ("OIDC_OP_URL", self.url),
                ("OIDC_OP_INTROSPECTION_ENDPOINT", self._url_introspection),
            ]
            if not value
        ]
        if missing:
            raise ImproperlyConfigured(
                f"Could not instantiate {self.__class__.__name__}: "
                f"missing required settings: {', '.join(missing)}"
            )

    def _client(self) -> httpx2.Client:
        """Get a configured HTTP client."""
        return httpx2.Client(
            verify=settings.OIDC_VERIFY_SSL,
            timeout=settings.OIDC_TIMEOUT,
            proxy=settings.OIDC_PROXY,
            transport=self._transport,
        )

    def get_introspection(self, client_id: str, client_secret: str, token: str) -> str:
        """Retrieve the raw introspection response about a token."""
        with self._client() as client:
            response = client.post(
                self._url_introspection,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "token": token,
                },
                headers={"Accept": self.accept_header},
            )
        response.raise_for_status()
        return response.text


class JWTAuthorizationServerClient(AuthorizationServerClient):
    """
    Client for an OAuth 2.0 authorization server using JWT introspection responses.

    Reference: https://www.rfc-editor.org/info/rfc9701
    """

    accept_header: str = "application/token-introspection+jwt"

    def __init__(self, transport: httpx2.BaseTransport | None = None):
        """Also require the authorization server JWKS endpoint."""
        super().__init__(transport=transport)
        self._url_jwks = settings.OIDC_OP_JWKS_ENDPOINT

        if not self._url_jwks:
            raise ImproperlyConfigured(
                f"Could not instantiate {self.__class__.__name__}: "
                "missing required settings: OIDC_OP_JWKS_ENDPOINT"
            )

    def get_jwks(self) -> dict:
        """Retrieve the authorization server JWKS."""
        with self._client() as client:
            response = client.get(self._url_jwks)
        response.raise_for_status()
        return response.json()

    def import_public_keys(self) -> KeySet:
        """Retrieve and import the authorization server JWKS."""
        return KeySet.import_key_set(self.get_jwks())  # ty: ignore
