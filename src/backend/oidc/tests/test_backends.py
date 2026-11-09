"""Menshen: tests for the oidc backends."""

import json
import logging
import time

import httpx2
import pytest
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from joserfc import jwe, jwt
from joserfc.jwk import ECKey, RSAKey

from oidc.backends import JWTResourceServerBackend, ResourceServerBackend
from oidc.exceptions import IntrospectionInactiveTokenError

ACTIVE_INTROSPECTION = {
    "active": True,
    "client_id": "service:source",
    "scope": "openid target:read",
    "sub": "user-sub",
    "iss": "http://fake.local",
}


def json_transport(payload, status_code=200) -> httpx2.MockTransport:
    """Mock an authorization server returning a JSON introspection response."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx2.MockTransport(lambda _: httpx2.Response(status_code, text=text))


# ResourceServerBackend


@pytest.mark.parametrize("setting", ["OIDC_RS_CLIENT_ID", "OIDC_RS_CLIENT_SECRET"])
def test_resource_server_backend_missing_settings(settings, setting):
    """The backend requires client credentials."""
    setattr(settings, setting, None)
    with pytest.raises(ImproperlyConfigured, match="missing required settings"):
        ResourceServerBackend()


def test_resource_server_backend_active_token():
    """An active token introspection should return the user info."""
    backend = ResourceServerBackend(transport=json_transport(ACTIVE_INTROSPECTION))
    assert backend.get_user_info_with_introspection("token") == ACTIVE_INTROSPECTION


def test_resource_server_backend_inactive_token(caplog):
    """An inactive token should raise a dedicated error."""
    backend = ResourceServerBackend(transport=json_transport({"active": False}))
    with (
        pytest.raises(IntrospectionInactiveTokenError, match="Introspected user is not active"),
        caplog.at_level(logging.INFO),
    ):
        backend.get_user_info_with_introspection("token")
    assert "Token introspection refused because user is not active" in caplog.messages


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not json", "Invalid JSON for introspection"),
        ("[1, 2]", "Invalid JSON for introspection"),
        ({"client_id": "service:source"}, "Failed to validate token's claims"),
        ({**ACTIVE_INTROSPECTION, "iss": "http://other.local"}, "Failed to validate"),
        (
            {"active": True, "client_id": "service:source"},
            "Token introspection failed due to missing 'scope' claim.",
        ),
        (
            {**ACTIVE_INTROSPECTION, "scope": "target:read"},
            "Introspection response is missing required scopes.",
        ),
        (
            {"active": True, "scope": "openid"},
            "Introspection response does not provide source audience.",
        ),
    ],
)
def test_resource_server_backend_invalid_introspection(payload, message):
    """Invalid introspection responses should raise SuspiciousOperation."""
    backend = ResourceServerBackend(transport=json_transport(payload))
    with pytest.raises(SuspiciousOperation, match=message):
        backend.get_user_info_with_introspection("token")


def test_resource_server_backend_configured_scopes_and_audience_claim(settings):
    """Required scopes and the audience claim should follow settings."""
    settings.OIDC_RS_SCOPES = ["target:read"]
    settings.OIDC_RS_AUDIENCE_CLAIM = "aud"
    payload = {"active": True, "scope": "target:read", "aud": "service:source"}

    backend = ResourceServerBackend(transport=json_transport(payload))
    assert backend.get_user_info_with_introspection("token") == payload

    backend = ResourceServerBackend(transport=json_transport(ACTIVE_INTROSPECTION))
    with pytest.raises(SuspiciousOperation, match="does not provide source audience"):
        backend.get_user_info_with_introspection("token")


def test_resource_server_backend_http_status_error():
    """An HTTP error status from the authorization server is suspicious."""
    backend = ResourceServerBackend(transport=json_transport({}, status_code=401))
    with pytest.raises(SuspiciousOperation, match="Could not fetch introspection"):
        backend.get_user_info_with_introspection("token")


def test_resource_server_backend_transport_error():
    """Transport errors should propagate."""

    def handler(request):
        raise httpx2.ConnectError("Connection refused", request=request)

    backend = ResourceServerBackend(transport=httpx2.MockTransport(handler))
    with pytest.raises(httpx2.ConnectError):
        backend.get_user_info_with_introspection("token")


# JWTResourceServerBackend


@pytest.fixture(name="rs_key")
def rs_key_fixture(settings) -> RSAKey:
    """Generate the resource server encryption key and configure it in settings."""
    key = RSAKey.generate_key(2048)
    settings.OIDC_RS_PRIVATE_KEY_STR = key.as_pem(private=True).decode()
    return key


@pytest.fixture(name="as_key")
def as_key_fixture() -> ECKey:
    """Generate the authorization server signing key."""
    return ECKey.generate_key("P-256", parameters={"kid": "as-key"})


def jwt_transport(
    as_key: ECKey,
    rs_key: RSAKey,
    claims: dict | None = None,
    jwks_status_code: int = 200,
) -> httpx2.MockTransport:
    """Mock an authorization server returning a JWE(JWS) introspection response."""
    if claims is None:
        claims = {
            "iss": "http://fake.local",
            "aud": "menshen",
            "iat": int(time.time()),
            "token_introspection": ACTIVE_INTROSPECTION,
        }
    jws = jwt.encode({"alg": "ES256", "kid": "as-key"}, claims, as_key)
    token = jwe.encrypt_compact(
        {"alg": "RSA-OAEP", "enc": "A256GCM"},
        jws,
        rs_key,
        registry=jwe.JWERegistry(algorithms=["RSA-OAEP", "A256GCM"]),
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/jwks":
            return httpx2.Response(jwks_status_code, json={"keys": [as_key.as_dict(private=False)]})
        return httpx2.Response(200, text=token)

    return httpx2.MockTransport(handler)


@pytest.fixture(autouse=True)
def jwks_endpoint(settings):
    """Configure the authorization server JWKS endpoint."""
    settings.OIDC_OP_JWKS_ENDPOINT = "http://fake.local/jwks"


def test_jwt_resource_server_backend_active_token(as_key, rs_key):
    """A valid JWT introspection response should return the user info."""
    backend = JWTResourceServerBackend(transport=jwt_transport(as_key, rs_key))
    assert backend.get_user_info_with_introspection("token") == ACTIVE_INTROSPECTION


def test_jwt_resource_server_backend_inactive_token(as_key, rs_key):
    """An inactive token should raise a dedicated error."""
    claims = {
        "iss": "http://fake.local",
        "aud": "menshen",
        "token_introspection": {"active": False},
    }
    backend = JWTResourceServerBackend(transport=jwt_transport(as_key, rs_key, claims))
    with pytest.raises(IntrospectionInactiveTokenError):
        backend.get_user_info_with_introspection("token")


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "http://other.local", "aud": "menshen", "token_introspection": {}},
        {"iss": "http://fake.local", "aud": "other", "token_introspection": {}},
        {"iss": "http://fake.local", "aud": "menshen"},
        {"iss": "http://fake.local", "aud": "menshen", "token_introspection": "foo"},
    ],
)
def test_jwt_resource_server_backend_invalid_claims(as_key, rs_key, claims):
    """Invalid enclosing JWT claims are suspicious."""
    backend = JWTResourceServerBackend(transport=jwt_transport(as_key, rs_key, claims))
    with pytest.raises(SuspiciousOperation):
        backend.get_user_info_with_introspection("token")


def test_jwt_resource_server_backend_wrong_encryption_key(settings, as_key, rs_key):
    """A response encrypted for another key cannot be decrypted."""
    transport = jwt_transport(as_key, rs_key)
    settings.OIDC_RS_PRIVATE_KEY_STR = RSAKey.generate_key(2048).as_pem(private=True).decode()
    backend = JWTResourceServerBackend(transport=transport)
    with pytest.raises(SuspiciousOperation, match="Token decryption failed"):
        backend.get_user_info_with_introspection("token")


def test_jwt_resource_server_backend_wrong_signing_key(as_key, rs_key):
    """A response signed by another key cannot be decoded."""
    transport = jwt_transport(as_key, rs_key)
    other_key = ECKey.generate_key("P-256", parameters={"kid": "as-key"})

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/jwks":
            return httpx2.Response(200, json={"keys": [other_key.as_dict(private=False)]})
        return transport.handle_request(request)

    backend = JWTResourceServerBackend(transport=httpx2.MockTransport(handler))
    with pytest.raises(SuspiciousOperation, match="Token decoding failed"):
        backend.get_user_info_with_introspection("token")


def test_jwt_resource_server_backend_jwks_error(as_key, rs_key):
    """Failing to fetch the authorization server JWKS is suspicious."""
    backend = JWTResourceServerBackend(
        transport=jwt_transport(as_key, rs_key, jwks_status_code=500)
    )
    with pytest.raises(SuspiciousOperation, match="Could not get authorization server JWKS"):
        backend.get_user_info_with_introspection("token")


@pytest.mark.parametrize(
    ("private_key", "message"),
    [
        (None, "OIDC_RS_PRIVATE_KEY_STR setting is missing or empty."),
        ("not a key", "OIDC_RS_PRIVATE_KEY_STR setting is wrong."),
    ],
)
def test_jwt_resource_server_backend_private_key_misconfigured(
    settings, as_key, rs_key, private_key, message
):
    """The resource server private key should be properly configured."""
    transport = jwt_transport(as_key, rs_key)
    settings.OIDC_RS_PRIVATE_KEY_STR = private_key
    backend = JWTResourceServerBackend(transport=transport)
    with pytest.raises(ImproperlyConfigured, match=message):
        backend.get_user_info_with_introspection("token")
