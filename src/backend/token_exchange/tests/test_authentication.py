"""Menshen: authentication tests for the token_exchange application."""

import pytest
import structlog
from django.http import HttpRequest
from ninja.errors import AuthenticationError

from token_exchange.authentication import ServiceProviderBasicAuthentication
from token_exchange.factories import ServiceProviderCredentialsFactory


@pytest.fixture(autouse=True)
def clear_structlog_context():
    """Clear structlog context vars around each test."""
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


def test_authentication_binds_service_provider_id(db):
    """Test that authentication binds the service provider id for logging."""
    credentials = ServiceProviderCredentialsFactory.create(client_secret="secret")

    service_provider = ServiceProviderBasicAuthentication().authenticate(
        HttpRequest(), credentials.client_id, "secret"
    )

    assert structlog.contextvars.get_contextvars()["service_provider_id"] == str(
        service_provider.pk
    )


def test_authentication_does_not_bind_service_provider_id_on_failure(db):
    """Test that a failed authentication does not bind a service provider id."""
    credentials = ServiceProviderCredentialsFactory.create(client_secret="secret")

    with pytest.raises(AuthenticationError):
        ServiceProviderBasicAuthentication().authenticate(
            HttpRequest(), credentials.client_id, "invalid"
        )

    assert "service_provider_id" not in structlog.contextvars.get_contextvars()
