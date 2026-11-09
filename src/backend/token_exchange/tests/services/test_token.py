"""Menshen: tests for the token service module."""

import re
import secrets
from unittest import mock
from uuid import UUID

import pytest
from django.utils import timezone
from joserfc.jwt import Token

from token_exchange.services.token import TokenGenerator


def test_token_generator_generate_opaque_token(monkeypatch):
    """Test the opaque token generation with the default length."""
    token_urlsafe = mock.Mock(wraps=secrets.token_urlsafe)
    monkeypatch.setattr("token_exchange.services.token.secrets.token_urlsafe", token_urlsafe)

    token = TokenGenerator.generate_opaque_token()

    # 32 bytes encoded in base64url (without padding) give 43 characters
    token_urlsafe.assert_called_once_with(32)
    assert isinstance(token, str)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)


@pytest.mark.parametrize(
    ("length", "nbytes"),
    [(1, 1), (2, 1), (3, 2), (4, 3), (43, 32), (44, 33), (45, 34), (46, 34), (64, 48), (100, 75)],
)
def test_token_generator_generate_opaque_token_length(monkeypatch, settings, length, nbytes):
    """Test the opaque token generation with a configured length (in characters)."""
    settings.TOKEN_EXCHANGE_OPAQUE_TOKEN_LENGTH = length
    token_urlsafe = mock.Mock(wraps=secrets.token_urlsafe)
    monkeypatch.setattr("token_exchange.services.token.secrets.token_urlsafe", token_urlsafe)

    token = TokenGenerator.generate_opaque_token()

    token_urlsafe.assert_called_once_with(nbytes)
    assert re.fullmatch(rf"[A-Za-z0-9_-]{{{length}}}", token)


def test_token_generator_load_key_set_configuration_not_set(settings):
    """Test the signing keys importation from settings when it's not configured."""
    settings.TOKEN_EXCHANGE_JWT_SIGNING_KEYS = {}
    with pytest.raises(ValueError, match="TOKEN_EXCHANGE_JWT_SIGNING_KEYS is empty."):
        TokenGenerator._load_key_set()


def test_token_generator_generate_jwt_ensure_signing_key_exists():
    """Test the signing key exists during JWT generation."""
    with pytest.raises(
        ValueError, match="Key ID 'fake' not found in TOKEN_EXCHANGE_JWT_SIGNING_KEYS"
    ):
        TokenGenerator.generate_jwt(
            sub="john.doe@example.org",
            email="john.doe@example.org",
            audiences=[
                "service0.example.org",
            ],
            scope="service0 service1",
            expires_in=30,
            kid="fake",
        )


def test_token_generator_generate_jwt(monkeypatch, settings):
    """Test JWT generation with legit data."""
    now = timezone.now()
    now_as_timestamp = int(now.timestamp())
    monkeypatch.setattr(timezone, "now", lambda: now)

    token: str = TokenGenerator.generate_jwt(
        sub="john.doe@example.org",
        email="john.doe@example.org",
        audiences=[
            "service0.example.org",
        ],
        scope="service0 service1",
        expires_in=30,
        kid=settings.TOKEN_EXCHANGE_JWT_CURRENT_KID,
    )

    validated: Token = TokenGenerator.verify_jwt(token)
    assert validated.header == {
        "alg": settings.TOKEN_EXCHANGE_JWT_ALGORITHM,
        "kid": settings.TOKEN_EXCHANGE_JWT_CURRENT_KID,
        "typ": "JWT",
    }
    assert validated.claims["act"] == {"sub": "actor"}
    assert validated.claims["aud"] == ["service0.example.org"]
    assert validated.claims["email"] == "john.doe@example.org"
    assert validated.claims["exp"] == now_as_timestamp + 30
    assert validated.claims["iat"] == now_as_timestamp
    assert validated.claims["scope"] == ["service0", "service1"]
    assert validated.claims["sub"] == "john.doe@example.org"
    assert str(UUID(validated.claims["jti"], version=4)) == validated.claims["jti"]


def test_token_generator_verify_jwt_invalid_token():
    """Test JWT verification with an invalid token."""
    with pytest.raises(ValueError, match="Invalid JWT: decode_error: Invalid JSON Web Signature"):
        TokenGenerator.verify_jwt("foo")


def test_token_generator_verify_jwt_invalid_claims(settings):
    """Test JWT verification with a invalid claims."""
    token: str = TokenGenerator.generate_jwt(
        sub="john.doe@example.org",
        email="john.doe@example.org",
        audiences=[
            "service0.example.org",
        ],
        scope="service0 service1",
        expires_in=-1,
        kid=settings.TOKEN_EXCHANGE_JWT_CURRENT_KID,
    )
    with pytest.raises(ValueError, match="expired_token: The token is expired"):
        TokenGenerator.verify_jwt(token)
