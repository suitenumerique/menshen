"""Menshen: test fixtures for the token_exchange application."""

import base64

import pytest
from rest_framework.test import APIClient

from token_exchange.factories import (
    ActionScopeFactory,
    ActionScopeGrantFactory,
    ScopeGrantFactory,
    ServiceProviderCredentialsFactory,
    ServiceProviderFactory,
    TokenExchangeActionPermissionFactory,
    TokenExchangeRuleFactory,
)
from token_exchange.models import ServiceProvider


@pytest.fixture(autouse=True)
def ip_user_info(monkeypatch, settings) -> None:
    """Monkeypatch identity provider get_user_info_with_introspection method."""

    # Monkeypatch OIDC backend token introspection
    def mock_user_info(self, _):
        self.token_origin_audience = "service:source"
        return {
            "client_id": "service:source",
            "email": "jane.doe@example.org",
            "scope": "openid target:read target:write",
        }

    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection", mock_user_info
    )


@pytest.fixture(autouse=True)
def configure_token_exchange(db) -> None:
    """Configure token exchange between source and target services."""
    source_service = ServiceProviderFactory(audience_id="service:source")
    target_service = ServiceProviderFactory(audience_id="service:target")
    source_target_rule = TokenExchangeRuleFactory(
        source_service=source_service, target_service=target_service
    )
    ScopeGrantFactory(rule=source_target_rule, source_scope="openid", granted_scope="openid")
    ScopeGrantFactory(
        rule=source_target_rule, source_scope="target:read", granted_scope="target:read"
    )
    ScopeGrantFactory(
        rule=source_target_rule, source_scope="target:write", granted_scope="target:write"
    )
    write_target_action = ActionScopeFactory(name="action:write-to-target")
    read_target_action = ActionScopeFactory(name="action:read-target")
    ActionScopeGrantFactory(
        action=write_target_action, target_service=target_service, granted_scope="target:write"
    )
    ActionScopeGrantFactory(
        action=read_target_action, target_service=target_service, granted_scope="target:read"
    )
    TokenExchangeActionPermissionFactory(rule=source_target_rule, action=write_target_action)


def token_exchange_api_client(service_provider: ServiceProvider) -> APIClient:
    """Get TokenExchange API client logged in for a service provider."""
    credentials = ServiceProviderCredentialsFactory(service_provider=service_provider)
    encoded_credentials = base64.b64encode(
        bytes(f"{credentials.client_id}:{credentials.client_secret}", encoding="utf-8")
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=b"Basic " + encoded_credentials)
    return client


@pytest.fixture
def source_api_client(configure_token_exchange) -> APIClient:
    """Source server TX API client."""
    return token_exchange_api_client(ServiceProvider.objects.get(audience_id="service:source"))


@pytest.fixture
def target_api_client(configure_token_exchange) -> APIClient:
    """Target server TX API client."""
    return token_exchange_api_client(ServiceProvider.objects.get(audience_id="service:target"))
