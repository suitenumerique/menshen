"""Menshen client: test fixtures."""

import pytest

from menshen_client.client import MenshenClient
from menshen_client.enums import MenshenSupportedTokenType, TokenExchangeResponseTokenType
from menshen_client.schemas import (
    MenshenConfiguration,
    MenshenJWTGrantClaim,
    MenshenJWTGrantClaimThrottling,
    TokenExchangeRequest,
    TokenExchangeResponse,
)


@pytest.fixture
def client_id() -> str:
    """Menshen configuration client_id."""
    return "foo"


@pytest.fixture
def client_secret() -> str:
    """Menshen configuration client_secret."""
    return "bar"


@pytest.fixture
def server_root_url() -> str:
    """Menshen configuration server_root_url."""
    return "https://menshen.example.org"


@pytest.fixture
def config(client_id, client_secret, server_root_url) -> MenshenConfiguration:
    """Menshen client test configuration."""
    return MenshenConfiguration(
        client_id=client_id, client_secret=client_secret, server_root_url=server_root_url
    )


@pytest.fixture
def client(config):
    """Get configured Menshen client."""
    return MenshenClient(config=config)


@pytest.fixture
def token_exchange_request():
    """Generate a token exchange request."""
    return TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=MenshenSupportedTokenType.ACCESS_TOKEN,
    )


@pytest.fixture
def token_exchange_response():
    """Generate a token exchange response."""
    return TokenExchangeResponse(
        access_token="foo",
        issued_token_type=MenshenSupportedTokenType.ACCESS_TOKEN,
        token_type=TokenExchangeResponseTokenType.BEARER,
        expires_in=3600,
        grants=[
            MenshenJWTGrantClaim(
                audience_id="service:target",
                scope="target:write",
                throttle=MenshenJWTGrantClaimThrottling(rate="1rpm"),
            )
        ],
        scope="target:write",
        refresh_token=None,
    )
