"""Menshen: model fields for the token_exchange application."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def get_fernet() -> MultiFernet:
    """
    Get the Fernet instance used to encrypt/decrypt secrets stored in the database.

    Keys are read from the TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS setting (comma
    separated Fernet keys): the first key encrypts, all keys decrypt (key rotation). If the
    setting is not defined, we fall back to a key derived from SECRET_KEY.
    """
    raw_keys: str = settings.TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS or ""
    keys = [key.strip() for key in raw_keys.split(",") if key.strip()]
    if not keys:
        digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        keys = [base64.urlsafe_b64encode(digest).decode("ascii")]

    try:
        return MultiFernet([Fernet(key) for key in keys])
    except ValueError as exc:
        raise ImproperlyConfigured(
            "TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS must contain valid Fernet keys."
        ) from exc


class EncryptedTextField(models.TextField):
    """
    A text field encrypted at rest.

    Use this field for secrets Menshen needs to read back (e.g. credentials sent to an
    identity provider), hence that cannot be hashed. Empty values are stored as-is.
    """

    def get_prep_value(self, value):
        """Encrypt the value before saving it to the database."""
        value = super().get_prep_value(value)
        if not value:
            return value
        return get_fernet().encrypt(value.encode("utf-8")).decode("ascii")

    def from_db_value(self, value, expression, connection):
        """Decrypt the value read from the database."""
        if not value:
            return value
        try:
            return get_fernet().decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ImproperlyConfigured(
                "Cannot decrypt an encrypted field value: check the "
                "TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS setting."
            ) from exc
