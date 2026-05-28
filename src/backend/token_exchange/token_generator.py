"""Menshen: Token generator for RFC 8693 token exchange."""

import secrets
from datetime import timedelta
from functools import cache

from django.conf import settings
from django.utils import timezone
from joserfc import jwt
from joserfc.errors import ClaimError, InvalidKeyIdError
from joserfc.jwk import KeySet, RSAKey
from joserfc.jwt import Token

from token_exchange.structs import (
    MenshenJWTClaims,
    TokenExchangeJWTActClaim,
    TokenExchangeJWTMayActClaim,
)


class TokenGenerator:
    """Generator for exchanged tokens (opaque or JWT)."""

    key_set: KeySet

    @classmethod
    @cache
    def _load_key_set(cls):
        """Load configured key set and init the class key_set attribute."""
        cls.key_set = KeySet(
            [
                RSAKey.import_key(pem, {"use": "sig", "kid": kid})
                for kid, pem in settings.TOKEN_EXCHANGE_JWT_SIGNING_KEYS.items()
            ]
        )
        if cls.key_set is None or not len(cls.key_set.keys):
            raise ValueError("TOKEN_EXCHANGE_JWT_SIGNING_KEYS is empty.")

    @staticmethod
    def generate_opaque_token() -> str:
        """
        Generate a secure opaque token.

        Returns:
            str: A URL-safe random token

        """
        return secrets.token_urlsafe(32)

    @classmethod
    def generate_jwt(  # noqa: PLR0913
        cls,
        sub: str,
        email: str,
        audiences: list[str],
        scope: str | list[str],
        expires_in: int,
        kid: str,
        may_act: TokenExchangeJWTMayActClaim | None = None,
        grants: list[dict] | None = None,
    ) -> str:
        """
        Generate a signed JWT according to RFC 8693.

        Args:
            sub: Subject identifier
            email: Subject email
            audiences: List of audience strings
            scope: Space-separated scopes or list of scopes
            expires_in: Token lifetime in seconds
            may_act: Optional may_act claim for delegation
            kid: Key ID for signing
            grants: Optional list of grant dicts with throttle info

        Returns:
            str: A signed JWT

        Raises:
            ValueError: If kid is not provided or not found in signing keys

        """
        cls._load_key_set()
        try:
            cls.key_set.get_by_kid(kid)
        except InvalidKeyIdError as exc:
            raise ValueError(
                f"Key ID '{kid}' not found in TOKEN_EXCHANGE_JWT_SIGNING_KEYS"
            ) from exc

        # Prepare scope as list if it's a string
        scopes: list = (scope.split() if scope else []) if isinstance(scope, str) else scope or []

        # Prepare claims
        claims = MenshenJWTClaims(
            sub=sub,
            aud=audiences,
            scope=scopes,
            exp=int((timezone.now() + timedelta(seconds=expires_in)).timestamp()),
            email=email,
            grants=grants,
            # Extract subject from actor_token if possible, or use a placeholder
            act=TokenExchangeJWTActClaim(sub="actor"),  # Simplified for now
            may_act=may_act,
        )

        # Prepare header with kid
        header = {
            "kid": kid,
            "alg": settings.TOKEN_EXCHANGE_JWT_ALGORITHM,
        }

        # Sign the JWT
        token = jwt.encode(header, claims.to_dict(), cls.key_set)
        return token.decode("utf-8") if isinstance(token, bytes) else token

    @classmethod
    def verify_jwt(cls, token: str) -> Token:
        """
        Verify a JWT signature supporting multiple keys (rotation).

        Args:
            token: The JWT string to verify

        Returns:
            dict: The decoded claims if valid

        Raises:
            ValueError: If token is invalid or signature verification fails

        """
        cls._load_key_set()

        # Decode JSON base64 string
        try:
            decoded: Token = jwt.decode(token, cls.key_set)
        except Exception as exc:
            raise ValueError(f"Invalid JWT: {exc}") from exc

        # Validate claims (including exp and iat)
        try:
            MenshenJWTClaims.to_jwt_claims_registry().validate(decoded.claims)
        except ClaimError as exc:
            raise ValueError(f"Invalid JWT claims: {exc}") from exc

        return decoded
