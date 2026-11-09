"""Test the Menshen client dataclasses."""

import re
from pathlib import Path

import pytest

from menshen_client import (
    OPAQUE_TOKEN_MIN_LENGTH,
    Configuration,
    IntrospectionRequest,
    InvalidTokenError,
    RevocationRequest,
    TokenType,
)

TOKEN = "MZGYrOI1nQNTwCriw0iJaGk-iF7Fdk2pdJB8LMYuCF0"  # noqa: S105
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJl"


@pytest.mark.parametrize("scheme", ["http", "https"])
@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (
            "menshen.example.org",
            (
                "menshen.example.org/auth/token/exchange/",
                "menshen.example.org/auth/token/introspect/",
                "menshen.example.org/auth/token/revoke/",
            ),
        ),
        (
            "menshen.example.org/",
            (
                "menshen.example.org/auth/token/exchange/",
                "menshen.example.org/auth/token/introspect/",
                "menshen.example.org/auth/token/revoke/",
            ),
        ),
        (
            "service.lasuite.org/menshen/",
            (
                "service.lasuite.org/menshen/auth/token/exchange/",
                "service.lasuite.org/menshen/auth/token/introspect/",
                "service.lasuite.org/menshen/auth/token/revoke/",
            ),
        ),
    ],
)
def test_menshen_configuration_properties(scheme, base_url, expected):
    """Test Configuration properties."""
    config = Configuration(
        client_id="foo",
        client_secret="bar",
        server_root_url=f"{scheme}://{base_url}",
    )
    assert config.token_url == f"{scheme}://{expected[0]}"
    assert config.introspection_url == f"{scheme}://{expected[1]}"
    assert config.revocation_url == f"{scheme}://{expected[2]}"


def test_menshen_configuration_properties_trailing_slashes():
    """Test Configuration properties URLs with missing trailing slashes."""
    config = Configuration(
        client_id="foo",
        client_secret="bar",
        server_root_url="https://menshen.example.org/",
        token_endpoint="/auth/token/exchange",
    )
    assert config.token_url == "https://menshen.example.org/auth/token/exchange/"


def test_opaque_token_min_length_is_in_sync_with_server():
    """The default opaque token min length should match the server's (fails if missing)."""
    server_settings = Path(__file__).parents[2] / "backend" / "menshen" / "settings.py"
    assert server_settings.exists(), f"Server sources not found: {server_settings}"
    match = re.search(
        r"TOKEN_EXCHANGE_OPAQUE_TOKEN_MIN_LENGTH = values\.\w+\(\s*default=(\d+),",
        server_settings.read_text(),
    )
    assert match, "Server TOKEN_EXCHANGE_OPAQUE_TOKEN_MIN_LENGTH setting not found"
    assert int(match.group(1)) == OPAQUE_TOKEN_MIN_LENGTH


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token", [TOKEN, JWT])
@pytest.mark.parametrize("padding", [(" ", ""), ("", "\n"), ("\t ", " \r\n")])
def test_token_requests_strip_token(request_klass, token, padding):
    """Leading and trailing whitespaces are stripped from the token."""
    request = request_klass(token=f"{padding[0]}{token}{padding[1]}")
    assert request.token == token


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token_type_hint", [None, TokenType.ACCESS_TOKEN, TokenType.JWT])
@pytest.mark.parametrize("token", [JWT, "a.b.c", f" {JWT}\n"])
def test_token_requests_is_jwt_given_token_shape(request_klass, token_type_hint, token):
    """JWT-shaped tokens are identified as JWTs whatever their type hint."""
    assert request_klass(token=token, token_type_hint=token_type_hint).is_jwt


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token", ["", "foo", TOKEN, "a.b", "a..c"])
def test_token_requests_is_jwt_given_type_hint(request_klass, token):
    """Tokens hinted as JWT are identified as JWTs whatever their shape."""
    assert request_klass(token=token, token_type_hint=TokenType.JWT).is_jwt


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token_type_hint", [None, TokenType.ACCESS_TOKEN])
@pytest.mark.parametrize("token", [TOKEN, "a.b", "a..c", "a.b.c.d", "a.b.c d", "é.b.c"])
def test_token_requests_is_not_jwt(request_klass, token_type_hint, token):
    """Tokens that are neither JWT-shaped nor hinted as JWT are not JWTs."""
    assert not request_klass(token=token, token_type_hint=token_type_hint).is_jwt


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token_type_hint", [None, TokenType.JWT])
def test_token_requests_reject_non_string_token(request_klass, token_type_hint):
    """Non-string tokens are always rejected."""
    with pytest.raises(InvalidTokenError, match="Invalid token format"):
        request_klass(token=None, token_type_hint=token_type_hint)
