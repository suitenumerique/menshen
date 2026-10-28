"""Tests for the TokenExchangeClient."""

import logging
from dataclasses import asdict

import httpx2
import pytest

from menshen_client.clients import TokenExchangeClient
from menshen_client.enums import TokenExchangeResponseTokenType, TokenType
from menshen_client.exceptions import ResponseParsingError
from menshen_client.schemas import (
    Configuration,
    IntrospectionRequest,
    IntrospectionResponse,
    RevocationRequest,
    TokenExchangeResponse,
)


def test_client_init():
    """Test the TokenExchangeClient instantiation."""
    config = Configuration(
        client_id="foo",
        client_secret="bar",
        server_root_url="https://menshen.example.org",
    )
    client = TokenExchangeClient(config=config)
    assert client.config == config
    assert isinstance(client.session, httpx2.Client)
    assert isinstance(client.session.auth, httpx2.BasicAuth)
    assert client.session.timeout == httpx2.Timeout(3.0)


@pytest.mark.parametrize("timeout", [1.5, None])
def test_client_init_with_custom_timeout(timeout):
    """Test the TokenExchangeClient instantiation with a custom requests timeout."""
    config = Configuration(
        client_id="foo",
        client_secret="bar",
        server_root_url="https://menshen.example.org",
        requests_timeout=timeout,
    )
    client = TokenExchangeClient(config=config)
    assert client.session.timeout == httpx2.Timeout(timeout)


def test_client_close(client):
    """Test the TokenExchangeClient close method."""
    assert not client.session.is_closed
    client.close()
    assert client.session.is_closed


def test_client_context_manager(config, httpx2_mock):
    """Test the TokenExchangeClient usage as a context manager."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
    )
    with TokenExchangeClient(config=config) as client:
        assert isinstance(client, TokenExchangeClient)
        assert not client.session.is_closed
        client.revoke(RevocationRequest(token="foo"))
    assert client.session.is_closed


def test_client_post_request(client, httpx2_mock, token_exchange_request, token_exchange_response):
    """Test the TokenExchangeClient sent request authentication and form data."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
        json=asdict(token_exchange_response),
    )
    client.exchange(token_exchange_request)

    request = httpx2_mock.get_request()
    assert request.headers["Authorization"] == "Basic Zm9vOmJhcg=="  # foo:bar
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    # Unset optional fields are not sent
    assert request.content == (
        b"subject_token=foo"
        b"&subject_token_type=urn%3Aietf%3Aparams%3Aoauth%3Atoken-type%3Aaccess_token"
        b"&grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Atoken-exchange"
    )


@pytest.mark.parametrize("status", [401, 403, 500, 502])
def test_client_exchange_raises_for_status(client, httpx2_mock, status, token_exchange_request):
    """Test the TokenExchangeClient exchange method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
        status_code=status,
    )
    with pytest.raises(httpx2.HTTPStatusError):
        client.exchange(token_exchange_request)


def test_client_exchange_raises_for_timeout(client, httpx2_mock, token_exchange_request):
    """Test the TokenExchangeClient exchange method with a request timeout."""
    httpx2_mock.add_exception(
        httpx2.ReadTimeout("Request took too much time dude."),
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
    )
    with pytest.raises(httpx2.TimeoutException):
        client.exchange(token_exchange_request)


def test_client_exchange_token(
    client, httpx2_mock, token_exchange_request, token_exchange_response
):
    """Test the TokenExchangeClient exchange method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
        status_code=200,
        json=asdict(token_exchange_response),
    )
    exchanged_token = client.exchange(token_exchange_request)

    assert isinstance(exchanged_token, TokenExchangeResponse)
    assert exchanged_token.access_token == "foo"
    assert exchanged_token.issued_token_type == TokenType.ACCESS_TOKEN
    assert exchanged_token.token_type == TokenExchangeResponseTokenType.BEARER
    assert exchanged_token.expires_in == 3600
    assert exchanged_token.grants[0].audience_id == "service:target"
    assert exchanged_token.grants[0].scope == "target:item:write"
    assert exchanged_token.grants[0].throttle.rate == "1rpm"
    assert exchanged_token.scope == "target:item:write"
    assert exchanged_token.refresh_token is None


def test_client_exchange_token_with_extra_field_in_response_payload(
    client, httpx2_mock, token_exchange_request, token_exchange_response, caplog
):
    """Test the TokenExchangeClient exchange method with an extra field in the response."""
    payload = asdict(token_exchange_response)
    payload.update({"foo": "bar"})  # add an extra field
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
        status_code=200,
        json=payload,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid token exchange response"),
        caplog.at_level(logging.INFO, logger="menshen_client"),
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
def test_client_exchange_token_with_missing_fields_in_response_payload(  # noqa: PLR0913,PLR0917
    client, httpx2_mock, token_exchange_request, payload, missing, caplog
):
    """Test the TokenExchangeClient exchange method with missing fields in the response."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
        status_code=200,
        json=payload,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid token exchange response"),
        caplog.at_level(logging.INFO, logger="menshen_client"),
    ):
        client.exchange(token_exchange_request)
    assert (
        "Invalid token exchange response: TokenExchangeResponse.__init__() "
        f"missing {missing} required positional arguments" in caplog.messages[0]
    )


@pytest.mark.parametrize("body", ["not json", None, ""])
def test_client_exchange_token_with_invalid_response_body(
    client, httpx2_mock, token_exchange_request, caplog, body
):
    """Test the TokenExchangeClient exchange method with an invalid response body."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
        status_code=200,
        text=body,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid token exchange response"),
        caplog.at_level(logging.INFO, logger="menshen_client"),
    ):
        client.exchange(token_exchange_request)
    assert (
        "Invalid token exchange response: Expecting value: line 1 column 1 (char 0)"
        in caplog.messages
    )


@pytest.mark.parametrize("status", [401, 403, 500, 502])
def test_client_introspect_raises_for_status(client, httpx2_mock, status):
    """Test the TokenExchangeClient introspect method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
        status_code=status,
    )
    with pytest.raises(httpx2.HTTPStatusError):
        client.introspect(IntrospectionRequest(token="foo"))


def test_client_introspect_raises_for_timeout(client, httpx2_mock):
    """Test the TokenExchangeClient introspect method with a request timeout."""
    httpx2_mock.add_exception(
        httpx2.ReadTimeout("Request took too much time dude."),
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
    )
    with pytest.raises(httpx2.TimeoutException):
        client.introspect(IntrospectionRequest(token="foo"))


def test_client_introspect_token(client, httpx2_mock):
    """Test the TokenExchangeClient introspect method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
        status_code=200,
        json=asdict(IntrospectionResponse(active=True)),
    )
    user_info = client.introspect(IntrospectionRequest(token="foo"))

    assert isinstance(user_info, IntrospectionResponse)
    assert user_info.active


def test_client_introspect_token_with_extra_field_in_response_payload(client, httpx2_mock, caplog):
    """Test the TokenExchangeClient introspect method with an extra field in the response."""
    payload = asdict(IntrospectionResponse(active=True))
    payload.update({"foo": "bar"})  # add an extra field
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
        status_code=200,
        json=payload,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid introspection response"),
        caplog.at_level(logging.INFO, logger="menshen_client"),
    ):
        client.introspect(IntrospectionRequest(token="foo"))
    assert (
        "Invalid introspection response: IntrospectionResponse.__init__() "
        "got an unexpected keyword argument 'foo'" in caplog.messages
    )


def test_client_introspect_token_with_missing_fields_in_response_payload(  # noqa: PLR0913
    client, httpx2_mock, caplog
):
    """Test the TokenExchangeClient introspect method with missing fields in the response."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
        status_code=200,
        json={},
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid introspection response"),
        caplog.at_level(logging.INFO, logger="menshen_client"),
    ):
        client.introspect(IntrospectionRequest(token="foo"))
    assert (
        "Invalid introspection response: IntrospectionResponse.__init__() "
        "missing 1 required positional argument: 'active'" in caplog.messages[0]
    )


@pytest.mark.parametrize("body", ["not json", None, ""])
def test_client_introspect_token_with_invalid_response_body(client, httpx2_mock, caplog, body):
    """Test the TokenExchangeClient introspect method with an invalid response body."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
        status_code=200,
        text=body,
    )
    with (
        pytest.raises(ResponseParsingError, match="Invalid introspection response"),
        caplog.at_level(logging.INFO, logger="menshen_client"),
    ):
        client.introspect(IntrospectionRequest(token="foo"))
    assert (
        "Invalid introspection response: Expecting value: line 1 column 1 (char 0)"
        in caplog.messages
    )


@pytest.mark.parametrize("status", [401, 403, 500, 502])
def test_client_revoke_raises_for_status(client, httpx2_mock, status):
    """Test the TokenExchangeClient revoke method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
        status_code=status,
    )
    with pytest.raises(httpx2.HTTPStatusError):
        client.revoke(RevocationRequest(token="foo"))


def test_client_revoke_raises_for_timeout(client, httpx2_mock):
    """Test the TokenExchangeClient revoke method with a request timeout."""
    httpx2_mock.add_exception(
        httpx2.ReadTimeout("Request took too much time dude."),
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
    )
    with pytest.raises(httpx2.TimeoutException):
        client.revoke(RevocationRequest(token="foo"))


@pytest.mark.parametrize("body", [None, "", "{}", '{"foo": "bar"}'])
def test_client_revoke_token(client, httpx2_mock, body):
    """Test the TokenExchangeClient revoke method with various response content."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
        status_code=200,
        text=body,
    )
    revocation_response = client.revoke(RevocationRequest(token="foo"))
    assert revocation_response is None
