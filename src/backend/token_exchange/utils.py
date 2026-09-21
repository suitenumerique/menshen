"""Menshen: token exchange utils."""

import secrets
import string


def generate_client_secret(length: int = 64, use_special_chars: bool = False) -> str:
    """Generate random client secret given a secret length."""
    alphabet = string.ascii_letters + string.digits
    if use_special_chars:
        alphabet += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    return "".join(secrets.choice(alphabet) for _ in range(length))
