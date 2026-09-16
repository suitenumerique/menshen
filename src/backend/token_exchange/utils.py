"""Menshen: token exchange utils."""

import secrets
import string

from django.conf import settings


def generate_client_secret(length: int = settings.TOKEN_EXCHANGE_CLIENT_SECRET_LENGTH) -> str:
    """Generate random client secret given a secret length."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    return "".join(secrets.choice(alphabet) for _ in range(length))
