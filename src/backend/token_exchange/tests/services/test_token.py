"""Menshen: tests for the token service module."""

from uuid import UUID

import pytest
from django.utils import timezone
from joserfc.jwt import Token

from token_exchange.services.token import TokenGenerator


def test_token_generator_generate_opaque_token():
    """Simple test for the opaque token generation."""
    token = TokenGenerator.generate_opaque_token()
    assert isinstance(token, str)

    # As stated in Python's documentation about the secrets.token_urlsafe function:
    #
    # > The text is Base64 encoded, so on average each byte results in approximately 1.3 characters.
    #
    # We use 32 bytes for this token.
    size = len(token)
    assert size >= 40
    assert size <= 44


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
    assert validated.claims["act"] == {"act": None, "sub": "actor"}
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
    with pytest.raises(ValueError, match="Invalid JWT claims: expired_token: The token is expired"):
        TokenGenerator.verify_jwt(token)
