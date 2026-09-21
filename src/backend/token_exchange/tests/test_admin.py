"""Menshen: admin tests for the token_exchange application."""

import re

import pytest

from token_exchange.factories import ServiceProviderFactory
from token_exchange.models import ServiceProviderCredentials


@pytest.mark.parametrize("use_special_chars", [True, False])
def test_service_provider_credentials_admin(admin_client, settings, use_special_chars):
    """Test new client credentials creation using Django admin."""
    settings.TOKEN_EXCHANGE_CLIENT_SECRET_USE_SPECIAL_CHARS = use_special_chars
    service_provider = ServiceProviderFactory.create()

    # No credentials should be associated
    assert ServiceProviderCredentials.objects.filter(service_provider=service_provider).count() == 0

    response = admin_client.post(
        "/admin/token_exchange/serviceprovidercredentials/add/",
        {
            "service_provider": service_provider.id,
            "client_id": "foo",
            "allowed_origins": "",
            "is_active": "on",
        },
        follow=True,
    )
    assert response.status_code == 200

    # A message with the client secret should be displayed
    assert any(
        re.match(r"Generated client_secret: .* \(will only be displayed once\)", m)
        for m in [str(message) for message in response.context["messages"]]
    )

    # And credentials with client secret should have been created
    credentials = ServiceProviderCredentials.objects.filter(service_provider=service_provider).get()
    assert credentials.client_id == "foo"
    assert isinstance(credentials.client_secret, str)
    assert len(credentials.client_secret)
