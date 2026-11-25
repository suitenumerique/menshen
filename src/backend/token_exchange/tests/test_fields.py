"""Menshen: model fields tests for the token_exchange application."""

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from token_exchange.factories import IdentityProviderCredentialsFactory
from token_exchange.fields import get_fernet
from token_exchange.models import IdentityProviderCredentials

pytestmark = pytest.mark.django_db


def _raw_client_secret(credentials: IdentityProviderCredentials) -> str:
    """Get the client secret as stored in the database."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT client_secret FROM {IdentityProviderCredentials._meta.db_table} "  # noqa: S608
            "WHERE id = %s",
            [credentials.pk],
        )
        row = cursor.fetchone()
    assert row is not None
    return row[0]


def test_get_fernet_falls_back_to_secret_key(settings):
    """Test a key derived from SECRET_KEY is used when no key is configured."""
    settings.TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS = None
    token = get_fernet().encrypt(b"foo")

    settings.SECRET_KEY = "another-secret-key"
    with pytest.raises(Exception):  # noqa: B017, PT011
        get_fernet().decrypt(token)


def test_get_fernet_invalid_key(settings):
    """Test invalid Fernet keys raise a configuration error."""
    settings.TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS = "not-a-fernet-key"
    with pytest.raises(ImproperlyConfigured, match="valid Fernet keys"):
        get_fernet()


def test_encrypted_text_field_round_trip(settings):
    """Test secrets are stored encrypted and read back decrypted."""
    settings.TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS = Fernet.generate_key().decode()
    credentials = IdentityProviderCredentialsFactory.create(client_secret="s3cr3t")

    raw_value = _raw_client_secret(credentials)
    assert raw_value != "s3cr3t"
    assert "s3cr3t" not in raw_value

    credentials = IdentityProviderCredentials.objects.get(pk=credentials.pk)
    assert credentials.client_secret == "s3cr3t"


def test_encrypted_text_field_empty_value():
    """Test empty values are stored as-is."""
    credentials = IdentityProviderCredentialsFactory.create(private_key="")
    credentials = IdentityProviderCredentials.objects.get(pk=credentials.pk)
    assert credentials.private_key == ""


def test_encrypted_text_field_key_rotation(settings):
    """Test values encrypted with a previous key can still be decrypted."""
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    settings.TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS = old_key
    credentials = IdentityProviderCredentialsFactory.create(client_secret="s3cr3t")

    # Rotate keys: the new key encrypts, the old one still decrypts
    settings.TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS = f"{new_key}, {old_key}"
    credentials = IdentityProviderCredentials.objects.get(pk=credentials.pk)
    assert credentials.client_secret == "s3cr3t"

    # Once saved again, the value is encrypted with the new key only
    credentials.save()
    settings.TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS = new_key
    credentials = IdentityProviderCredentials.objects.get(pk=credentials.pk)
    assert credentials.client_secret == "s3cr3t"


def test_encrypted_text_field_unknown_key(settings):
    """Test reading a value encrypted with an unknown key raises a configuration error."""
    settings.TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS = Fernet.generate_key().decode()
    credentials = IdentityProviderCredentialsFactory.create()

    settings.TOKEN_EXCHANGE_IDP_CREDENTIALS_ENCRYPTION_KEYS = Fernet.generate_key().decode()
    with pytest.raises(ImproperlyConfigured, match="Cannot decrypt"):
        IdentityProviderCredentials.objects.get(pk=credentials.pk)
