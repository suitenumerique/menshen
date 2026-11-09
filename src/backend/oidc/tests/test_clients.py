"""Menshen: tests for the oidc clients."""

import json

import httpx2
import pytest
from django.core.exceptions import ImproperlyConfigured
from joserfc.jwk import ECKey, KeySet

from oidc.clients import AuthorizationServerClient, JWTAuthorizationServerClient


@pytest.mark.parametrize(
    ("setting", "value"),
    [("OIDC_OP_URL", None), ("OIDC_OP_INTROSPECTION_ENDPOINT", "")],
)
def test_authorization_server_client_missing_settings(settings, setting, value):
    """The client requires the authorization server URL and introspection endpoint."""
    setattr(settings, setting, value)
    with pytest.raises(ImproperlyConfigured, match=f"missing required settings: {setting}"):
        AuthorizationServerClient()


def test_authorization_server_client_get_introspection(settings):
    """The client should POST the token and client credentials to the introspection endpoint."""
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, text='{"active": true}')

    client = AuthorizationServerClient(transport=httpx2.MockTransport(handler))
    assert client.url == settings.OIDC_OP_URL
    assert client.get_introspection("menshen", "secret", "token") == '{"active": true}'

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == settings.OIDC_OP_INTROSPECTION_ENDPOINT
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert request.content == b"client_id=menshen&client_secret=secret&token=token"


def test_authorization_server_client_get_introspection_http_error():
    """The client should raise on HTTP error status."""
    client = AuthorizationServerClient(
        transport=httpx2.MockTransport(lambda _: httpx2.Response(500))
    )
    with pytest.raises(httpx2.HTTPStatusError):
        client.get_introspection("menshen", "secret", "token")


def test_jwt_authorization_server_client_missing_jwks_endpoint(settings):
    """The JWT client requires the authorization server JWKS endpoint."""
    settings.OIDC_OP_JWKS_ENDPOINT = None
    with pytest.raises(
        ImproperlyConfigured, match="missing required settings: OIDC_OP_JWKS_ENDPOINT"
    ):
        JWTAuthorizationServerClient()


def test_jwt_authorization_server_client_get_introspection_accept_header():
    """The JWT client should ask for a JWT introspection response."""
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, text="jwt")

    client = JWTAuthorizationServerClient(transport=httpx2.MockTransport(handler))
    assert client.get_introspection("menshen", "secret", "token") == "jwt"
    assert requests[0].headers["Accept"] == "application/token-introspection+jwt"


def test_jwt_authorization_server_client_import_public_keys(settings):
    """The JWT client should fetch and import the authorization server JWKS."""
    settings.OIDC_OP_JWKS_ENDPOINT = "http://fake.local/jwks"
    key = ECKey.generate_key("P-256", parameters={"kid": "as-key"})
    jwks = {"keys": [key.as_dict(private=False)]}

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "GET"
        assert str(request.url) == "http://fake.local/jwks"
        return httpx2.Response(200, text=json.dumps(jwks))

    client = JWTAuthorizationServerClient(transport=httpx2.MockTransport(handler))
    assert client.get_jwks() == jwks

    key_set = client.import_public_keys()
    assert isinstance(key_set, KeySet)
    assert key_set.get_by_kid("as-key").as_dict() == key.as_dict(private=False)


def test_jwt_authorization_server_client_get_jwks_http_error():
    """The JWT client should raise on JWKS HTTP error status."""
    client = JWTAuthorizationServerClient(
        transport=httpx2.MockTransport(lambda _: httpx2.Response(404))
    )
    with pytest.raises(httpx2.HTTPStatusError):
        client.get_jwks()
