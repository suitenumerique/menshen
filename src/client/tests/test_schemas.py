"""Test the Menshen client dataclasses."""

import re
import secrets
from pathlib import Path

import pytest

from menshen_client import (
    TOKEN_PATTERN,
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


def test_token_pattern_is_in_sync_with_server():
    """The opaque token pattern should match the server's generator (fails outside the monorepo)."""
    server_token_service = (
        Path(__file__).parents[2] / "backend" / "token_exchange" / "services" / "token.py"
    )
    assert server_token_service.exists(), f"Server sources not found: {server_token_service}"
    match = re.search(
        r"def generate_opaque_token\(\) -> str:.*?return (secrets\.token_urlsafe\(\d+\))\n",
        server_token_service.read_text(),
        flags=re.DOTALL,
    )
    assert match, "Server opaque token generator not found"
    assert match.group(1) == "secrets.token_urlsafe(32)"


@pytest.mark.parametrize("_", range(100))
def test_token_pattern_matches_generated_tokens(_):
    """Tokens generated as the server does should match the opaque token pattern."""
    assert re.fullmatch(TOKEN_PATTERN, secrets.token_urlsafe(32))


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token", [TOKEN, "a" * 43, "-" * 43, "_" * 43])
def test_token_requests_accept_valid_token(request_klass, token):
    """Valid opaque tokens are accepted by token requests."""
    assert request_klass(token=token).token == token


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token", [TOKEN, JWT])
@pytest.mark.parametrize("padding", [(" ", ""), ("", "\n"), ("\t ", " \r\n")])
def test_token_requests_strip_token(request_klass, token, padding):
    """Leading and trailing whitespaces are stripped from the token."""
    request = request_klass(token=f"{padding[0]}{token}{padding[1]}")
    assert request.token == token


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize(
    "token",
    [
        "",
        " " * 43,
        "foo",
        "a" * 42,
        "a" * 44,
        "a" * 32,
        TOKEN[:-1] + "=",
        TOKEN[:-1] + "+",
        TOKEN[:-1] + "/",
        TOKEN[:-1] + "é",
        TOKEN[:20] + " " + TOKEN[21:],
    ],
)
def test_token_requests_reject_malformed_token(request_klass, token):
    """Malformed opaque tokens are rejected when instantiating token requests."""
    with pytest.raises(InvalidTokenError, match="Invalid token format"):
        request_klass(token=token)


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token_type_hint", [None, TokenType.ACCESS_TOKEN, TokenType.JWT])
@pytest.mark.parametrize("token", [JWT, "a.b.c", f" {JWT}\n"])
def test_token_requests_skip_opaque_format_check_for_jwt_shaped_tokens(
    request_klass, token_type_hint, token
):
    """JWT-shaped tokens are not checked against the opaque token format."""
    request = request_klass(token=token, token_type_hint=token_type_hint)
    assert request.is_jwt


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token", ["", "foo", "a" * 16 + " " + "a" * 16, "a.b", "a..c"])
def test_token_requests_skip_opaque_format_check_for_jwt_type_hint(request_klass, token):
    """Tokens hinted as JWT are not checked against the opaque token format."""
    request = request_klass(token=token, token_type_hint=TokenType.JWT)
    assert request.is_jwt


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token", ["a.b", "a..c", "a.b.c.d", "a.b.c d", "é.b.c"])
def test_token_requests_check_opaque_format_for_non_jwt_shaped_tokens(request_klass, token):
    """Tokens that are not JWT-shaped (nor hinted as JWT) are checked as opaque tokens."""
    with pytest.raises(InvalidTokenError, match="Invalid token format"):
        request_klass(token=token, token_type_hint=TokenType.ACCESS_TOKEN)


@pytest.mark.parametrize("request_klass", [IntrospectionRequest, RevocationRequest])
@pytest.mark.parametrize("token_type_hint", [None, TokenType.JWT])
def test_token_requests_reject_non_string_token(request_klass, token_type_hint):
    """Non-string tokens are always rejected."""
    with pytest.raises(InvalidTokenError, match="Invalid token format"):
        request_klass(token=None, token_type_hint=token_type_hint)
