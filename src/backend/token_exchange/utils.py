"""Menshen: token exchange utils."""

import hmac
import secrets
import string
from hashlib import sha256

from django.conf import settings


def generate_client_secret(length: int = 64, use_special_chars: bool = False) -> str:
    """Generate random client secret given a secret length."""
    alphabet = string.ascii_letters + string.digits
    if use_special_chars:
        alphabet += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_token(raw_token: str) -> str:
    """
    Hash a raw token value for storage and lookup.

    We use a keyed hash (HMAC-SHA256) rather than a password hasher because
    exchanged tokens must be looked up by their value (unlike passwords which
    are verified after fetching a row by username). The key (pepper) comes from
    the TOKEN_EXCHANGE_TOKEN_HASH_KEY setting and falls back to SECRET_KEY.

    This is safe without a per-value salt because emitted tokens are
    high-entropy random values (opaque tokens or signed JWTs).

    """
    key = settings.TOKEN_EXCHANGE_TOKEN_HASH_KEY or settings.SECRET_KEY
    if isinstance(key, str):
        key = key.encode()
    return hmac.new(key, raw_token.encode(), sha256).hexdigest()
