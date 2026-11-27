"""Menshen: authentication tests for the token_exchange application."""

import pytest
import structlog
from django.http import HttpRequest
from ninja.errors import AuthenticationError
from structlog.testing import capture_logs

from token_exchange.authentication import ServiceProviderBasicAuthentication
from token_exchange.factories import ServiceProviderCredentialsFactory


@pytest.mark.django_db
def test_authentication_binds_service_provider_id():
    """Test that authentication binds the service provider id for logging."""
    credentials = ServiceProviderCredentialsFactory.create(client_secret="secret")

    service_provider = ServiceProviderBasicAuthentication().authenticate(
        HttpRequest(), credentials.client_id, "secret"
    )

    assert structlog.contextvars.get_contextvars()["service_provider_id"] == str(
        service_provider.pk
    )


@pytest.mark.django_db
def test_authentication_does_not_bind_service_provider_id_on_failure():
    """Test that a failed authentication does not bind a service provider id."""
    credentials = ServiceProviderCredentialsFactory.create(client_secret="secret")

    with pytest.raises(AuthenticationError):
        ServiceProviderBasicAuthentication().authenticate(
            HttpRequest(), credentials.client_id, "invalid"
        )

    assert "service_provider_id" not in structlog.contextvars.get_contextvars()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_id", "client_secret", "is_active", "reason"),
    [
        ("unknown", "secret", True, "unknown_client"),
        (None, "secret", False, "inactive_client"),
        (None, "invalid", True, "invalid_secret"),
    ],
)
def test_authentication_logs_failure(client_id, client_secret, is_active, reason):
    """Test that authentication failures are logged with their reason (but not the secret)."""
    credentials = ServiceProviderCredentialsFactory.create(
        client_secret="secret", is_active=is_active
    )
    client_id = client_id or credentials.client_id

    with capture_logs() as log_events, pytest.raises(AuthenticationError):
        ServiceProviderBasicAuthentication().authenticate(HttpRequest(), client_id, client_secret)

    assert log_events == [
        {
            "event": "service_provider_authentication_failed",
            "log_level": "warning",
            "reason": reason,
            "client_id": client_id,
        }
    ]
