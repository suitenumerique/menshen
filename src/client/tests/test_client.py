"""Tests for the MenshenClient."""

import logging
from dataclasses import asdict

import pytest
from requests import HTTPError

from menshen_client.client import MenshenClient
from menshen_client.enums import MenshenSupportedTokenType, TokenExchangeResponseTokenType
from menshen_client.exceptions import ResponseParsingError
from menshen_client.schemas import (
    IntrospectionRequest,
    IntrospectionResponse,
    MenshenConfiguration,
    RevocationRequest,
    TokenExchangeResponse,
)


def test_client_init():
    """Test the MenshenClient instantiation."""
    config = MenshenConfiguration(
        client_id="foo",
        client_secret="bar",
        server_root_url="https://menshen.example.org",
    )
    client = MenshenClient(config=config)
    assert client.config == config
    assert client.session
    assert client.session.auth.username == config.client_id  # ty: ignore
    assert client.session.auth.password == config.client_secret  # ty: ignore


@pytest.mark.parametrize("status", [401, 403, 500, 502])
def test_client_exchange_raises_for_status(client, responses, status, token_exchange_request):
    """Test the MenshenClient exchange method with an invalid response status."""
    responses.post(
        "https://menshen.example.org/auth/token/exchange/",
        status=status,
    )
    with pytest.raises(HTTPError):
        client.exchange(token_exchange_request)


def test_client_exchange_token(client, responses, token_exchange_request, token_exchange_response):
    """Test the MenshenClient exchange method with an invalid response status."""
    responses.post(
        "https://menshen.example.org/auth/token/exchange/",
        status=200,
        json=asdict(token_exchange_response),
    )
    exchanged_token = client.exchange(token_exchange_request)

    assert isinstance(exchanged_token, TokenExchangeResponse)
    assert exchanged_token.access_token == "foo"
    assert exchanged_token.issued_token_type == MenshenSupportedTokenType.ACCESS_TOKEN
    assert exchanged_token.token_type == TokenExchangeResponseTokenType.BEARER
    assert exchanged_token.expires_in == 3600
    assert exchanged_token.grants[0].audience_id == "service:target"
    assert exchanged_token.grants[0].scope == "target:write"
    assert exchanged_token.grants[0].throttle.rate == "1rpm"
    assert exchanged_token.scope == "target:write"
    assert exchanged_token.refresh_token is None


def test_client_exchange_token_with_extra_field_in_response_payload(
    client, responses, token_exchange_request, token_exchange_response, caplog
):
    """Test the MenshenClient exchange method with an extra field in the response."""
    payload = asdict(token_exchange_response)
    payload.update({"foo": "bar"})  # add an extra field
    responses.post(
        "https://menshen.example.org/auth/token/exchange/",
        status=200,
        json=payload,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid token exchange response"),
        caplog.at_level(logging.INFO),
    ):
        client.exchange(token_exchange_request)
    assert (
        "Invalid token exchange response: TokenExchangeResponse.__init__() "
        "got an unexpected keyword argument 'foo'" in caplog.messages
    )


@pytest.mark.parametrize(
    ("payload", "missing"),
    [
        ({}, 5),
        ({"access_token": "foo"}, 4),
        ({"access_token": "foo", "expires_in": 120}, 3),
    ],
)
def test_client_exchange_token_with_missing_fields_in_response_payload(  # noqa: PLR0913
    client, responses, token_exchange_request, payload, missing, caplog
):
    """Test the MenshenClient exchange method with missing fields in the response."""
    responses.post(
        "https://menshen.example.org/auth/token/exchange/",
        status=200,
        json=payload,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid token exchange response"),
        caplog.at_level(logging.INFO),
    ):
        client.exchange(token_exchange_request)
    assert (
        "Invalid token exchange response: TokenExchangeResponse.__init__() "
        f"missing {missing} required positional arguments" in caplog.messages[0]
    )


@pytest.mark.parametrize("body", ["not json", None, ""])
def test_client_exchange_token_with_invalid_response_body(
    client, responses, token_exchange_request, caplog, body
):
    """Test the MenshenClient exchange method with an invalid response body."""
    responses.post(
        "https://menshen.example.org/auth/token/exchange/",
        status=200,
        body=body,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid token exchange response"),
        caplog.at_level(logging.INFO),
    ):
        client.exchange(token_exchange_request)
    assert (
        "Invalid token exchange response: Expecting value: line 1 column 1 (char 0)"
        in caplog.messages
    )


@pytest.mark.parametrize("status", [401, 403, 500, 502])
def test_client_introspect_raises_for_status(client, responses, status):
    """Test the MenshenClient introspect method with an invalid response status."""
    responses.post(
        "https://menshen.example.org/auth/token/introspect/",
        status=status,
    )
    with pytest.raises(HTTPError):
        client.introspect(IntrospectionRequest(token="foo"))


def test_client_introspect_token(client, responses):
    """Test the MenshenClient introspect method with an invalid response status."""
    responses.post(
        "https://menshen.example.org/auth/token/introspect/",
        status=200,
        json=asdict(IntrospectionResponse(active=True)),
    )
    user_info = client.introspect(IntrospectionRequest(token="foo"))

    assert isinstance(user_info, IntrospectionResponse)
    assert user_info.active


def test_client_introspect_token_with_extra_field_in_response_payload(client, responses, caplog):
    """Test the MenshenClient introspect method with an extra field in the response."""
    payload = asdict(IntrospectionResponse(active=True))
    payload.update({"foo": "bar"})  # add an extra field
    responses.post(
        "https://menshen.example.org/auth/token/introspect/",
        status=200,
        json=payload,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid introspection response"),
        caplog.at_level(logging.INFO),
    ):
        client.introspect(IntrospectionRequest(token="foo"))
    assert (
        "Invalid introspection response: IntrospectionResponse.__init__() "
        "got an unexpected keyword argument 'foo'" in caplog.messages
    )


def test_client_introspect_token_with_missing_fields_in_response_payload(  # noqa: PLR0913
    client, responses, caplog
):
    """Test the MenshenClient introspect method with missing fields in the response."""
    responses.post(
        "https://menshen.example.org/auth/token/introspect/",
        status=200,
        json={},
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid introspection response"),
        caplog.at_level(logging.INFO),
    ):
        client.introspect(IntrospectionRequest(token="foo"))
    assert (
        "Invalid introspection response: IntrospectionResponse.__init__() "
        "missing 1 required positional argument: 'active'" in caplog.messages[0]
    )


@pytest.mark.parametrize("body", ["not json", None, ""])
def test_client_introspect_token_with_invalid_response_body(client, responses, caplog, body):
    """Test the MenshenClient introspect method with an invalid response body."""
    responses.post(
        "https://menshen.example.org/auth/token/introspect/",
        status=200,
        body=body,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid introspection response"),
        caplog.at_level(logging.INFO),
    ):
        client.introspect(IntrospectionRequest(token="foo"))
    assert (
        "Invalid introspection response: Expecting value: line 1 column 1 (char 0)"
        in caplog.messages
    )


@pytest.mark.parametrize("status", [401, 403, 500, 502])
def test_client_revoke_raises_for_status(client, responses, status):
    """Test the MenshenClient revoke method with an invalid response status."""
    responses.post(
        "https://menshen.example.org/auth/token/revoke/",
        status=status,
    )
    with pytest.raises(HTTPError):
        client.revoke(RevocationRequest(token="foo"))


@pytest.mark.parametrize("body", [None, "", "{}", '{"foo": "bar"}'])
def test_client_revoke_token(client, responses, body):
    """Test the MenshenClient revoke method with various response content."""
    responses.post(
        "https://menshen.example.org/auth/token/revoke/",
        status=200,
        body=body,
    )
    revocation_response = client.revoke(RevocationRequest(token="foo"))
    assert revocation_response is None
