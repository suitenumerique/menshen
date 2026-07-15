"""Menshen: test fixtures for the token_exchange application."""

import base64
from uuid import uuid4

import pytest
from ninja.testing import TestClient

from token_exchange.api import api
from token_exchange.factories import (
    ActionScopeFactory,
    ActionScopeGrantFactory,
    ScopeGrantFactory,
    ServiceProviderCredentialsFactory,
    ServiceProviderFactory,
    TokenExchangeActionPermissionFactory,
    TokenExchangeRuleFactory,
)
from token_exchange.models import ServiceProvider, TokenExchangeRule
from token_exchange.services.token import TokenGenerator


@pytest.fixture(autouse=True)
def ip_user_info(monkeypatch, settings) -> None:
    """Monkeypatch identity provider get_user_info_with_introspection method."""

    # Monkeypatch OIDC backend token introspection
    def mock_user_info(self, _):
        self.token_origin_audience = "service:source"
        return {
            "active": True,
            "client_id": "service:source",
            "email": "jane.doe@example.org",
            "scope": "openid target:read target:write",
            "jti": uuid4(),
            "sub": uuid4(),
        }

    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection", mock_user_info
    )


@pytest.fixture(name="source_service")
def source_service_fixture(db) -> ServiceProvider:
    """Generate the standard source service."""
    return ServiceProviderFactory.create(audience_id="service:source")


@pytest.fixture(name="target_service")
def target_service_fixture(db) -> ServiceProvider:
    """Generate the standard target service."""
    return ServiceProviderFactory.create(audience_id="service:target")


@pytest.fixture(name="source_target_rule")
def source_target_rule_fixture(db, source_service, target_service) -> TokenExchangeRule:
    """Generate the standard target service."""
    return TokenExchangeRuleFactory.create(
        source_service=source_service, target_service=target_service
    )


@pytest.fixture(autouse=True, name="configure_token_exchange")
def configure_token_exchange_fixture(db, target_service, source_target_rule) -> None:
    """Configure token exchange between source and target services."""
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


def token_exchange_api_client(service_provider: ServiceProvider) -> TestClient:
    """Get TokenExchange API client logged in for a service provider."""
    credentials = ServiceProviderCredentialsFactory(service_provider=service_provider)
    encoded_credentials = base64.b64encode(
        bytes(f"{credentials.client_id}:{credentials.client_secret}", encoding="utf-8")
    )
    return TestClient(api, headers={"Authorization": "Basic " + encoded_credentials.decode()})


@pytest.fixture
def source_api_client(configure_token_exchange) -> TestClient:
    """Source server TX API client."""
    return token_exchange_api_client(ServiceProvider.objects.get(audience_id="service:source"))


@pytest.fixture
def target_api_client(configure_token_exchange) -> TestClient:
    """Target server TX API client."""
    return token_exchange_api_client(ServiceProvider.objects.get(audience_id="service:target"))


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """
    Taken from codeinthehole.

    https://til.codeinthehole.com/posts/how-to-inspect-and-clear-pythons-functoolslrucache/

    """
    # Clear the LRU cache.
    TokenGenerator._load_key_set.cache_clear()

    # Execute the test...
    # Note that, as we don't have a teardown, there is no need to yield here.
