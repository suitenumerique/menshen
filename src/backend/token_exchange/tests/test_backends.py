"""Menshen: OIDC resource server backends tests for the token_exchange application."""

import json
from unittest import mock

import pytest
from joserfc.jwt import Token
from lasuite.oidc_resource_server import backend as lasuite_backend
from structlog.testing import capture_logs

from token_exchange.backends import JWTResourceServerBackend, ResourceServerBackend

CLAIMS = {
    "active": True,
    "client_id": "service:source",
    "scope": "openid",
    "sub": "ef7d37b4-080c-4df7-b0f8-3560dc7138aa",
    "email": "jane.doe@example.org",
}


@pytest.fixture(autouse=True)
def oidc_rs_settings(settings):
    """Configure the resource server credentials required to instantiate backends."""
    settings.OIDC_RS_CLIENT_ID = "menshen"
    settings.OIDC_RS_CLIENT_SECRET = "secret"  # noqa: S105
    settings.OIDC_OP_JWKS_ENDPOINT = "https://oidc.example.org/jwks"


def test_default_backend_class(settings):
    """Test the default resource server backend logs introspection responses."""
    assert settings.OIDC_RS_BACKEND_CLASS == "token_exchange.backends.ResourceServerBackend"


@pytest.mark.parametrize("backend_class", [ResourceServerBackend, JWTResourceServerBackend])
def test_backends_override_lasuite_introspect(backend_class):
    """
    Test our backends override lasuite's `_introspect` private method.

    This test should fail if this method is renamed or removed upstream.
    """
    lasuite_class = getattr(lasuite_backend, backend_class.__name__)
    assert backend_class.__mro__[2] is lasuite_class
    assert "_introspect" in vars(lasuite_class)


def test_resource_server_backend_logs_introspection_response():
    """Test the JSON introspection response is logged."""
    backend = ResourceServerBackend()
    with (
        mock.patch.object(backend, "_get_introspection", return_value=json.dumps(CLAIMS)),
        capture_logs() as log_events,
    ):
        token = backend._introspect("access-token")  # noqa: SLF001

    assert token.claims == CLAIMS
    assert log_events == [
        {
            "event": "subject_token_introspection_response",
            "log_level": "debug",
            "claims": CLAIMS,
        }
    ]
    assert "access-token" not in str(log_events)


def test_jwt_resource_server_backend_logs_introspection_response():
    """Test the decoded JWT introspection response is logged."""
    backend = JWTResourceServerBackend()
    with (
        mock.patch.object(
            lasuite_backend.JWTResourceServerBackend,
            "_introspect",
            return_value=Token({}, CLAIMS),
        ) as mock_introspect,
        capture_logs() as log_events,
    ):
        token = backend._introspect("access-token")  # noqa: SLF001

    mock_introspect.assert_called_once_with("access-token")
    assert token.claims == CLAIMS
    assert log_events == [
        {
            "event": "subject_token_introspection_response",
            "log_level": "debug",
            "claims": CLAIMS,
        }
    ]
