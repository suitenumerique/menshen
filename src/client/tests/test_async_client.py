"""Tests for the TokenExchangeAsyncClient."""

import logging
from dataclasses import asdict

import httpx2
import pytest

from menshen_client.client import TokenExchangeAsyncClient
from menshen_client.enums import TokenExchangeResponseTokenType, TokenType
from menshen_client.exceptions import ResponseParsingError
from menshen_client.schemas import (
    Configuration,
    IntrospectionRequest,
    IntrospectionResponse,
    RevocationRequest,
    TokenExchangeResponse,
)

pytestmark = pytest.mark.anyio


def test_async_client_init():
    """Test the TokenExchangeAsyncClient instantiation."""
    config = Configuration(
        client_id="foo",
        client_secret="bar",
        server_root_url="https://menshen.example.org",
    )
    async_client = TokenExchangeAsyncClient(config=config)
    assert async_client.config == config
    assert isinstance(async_client.session, httpx2.AsyncClient)
    assert isinstance(async_client.session.auth, httpx2.BasicAuth)
    assert async_client.session.timeout == httpx2.Timeout(3.0)


@pytest.mark.parametrize("timeout", [1.5, None])
def test_async_client_init_with_custom_timeout(timeout):
    """Test the TokenExchangeAsyncClient instantiation with a custom requests timeout."""
    config = Configuration(
        client_id="foo",
        client_secret="bar",
        server_root_url="https://menshen.example.org",
        requests_timeout=timeout,
    )
    async_client = TokenExchangeAsyncClient(config=config)
    assert async_client.session.timeout == httpx2.Timeout(timeout)


async def test_async_client_aclose(async_client):
    """Test the TokenExchangeAsyncClient aclose method."""
    assert not async_client.session.is_closed
    await async_client.aclose()
    assert async_client.session.is_closed


async def test_async_client_context_manager(config, httpx2_mock):
    """Test the TokenExchangeAsyncClient usage as an asynchronous context manager."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
    )
    async with TokenExchangeAsyncClient(config=config) as async_client:
        assert isinstance(async_client, TokenExchangeAsyncClient)
        assert not async_client.session.is_closed
        await async_client.revoke(RevocationRequest(token="foo"))
    assert async_client.session.is_closed


async def test_async_client_post_request(
    async_client, httpx2_mock, token_exchange_request, token_exchange_response
):
    """Test the TokenExchangeAsyncClient sent request authentication and form data."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
        json=asdict(token_exchange_response),
    )
    await async_client.exchange(token_exchange_request)

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
async def test_async_client_exchange_raises_for_status(
    async_client, httpx2_mock, status, token_exchange_request
):
    """Test the TokenExchangeAsyncClient exchange method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
        status_code=status,
    )
    with pytest.raises(httpx2.HTTPStatusError):
        await async_client.exchange(token_exchange_request)


async def test_async_client_exchange_raises_for_timeout(
    async_client, httpx2_mock, token_exchange_request
):
    """Test the TokenExchangeAsyncClient exchange method with a request timeout."""
    httpx2_mock.add_exception(
        httpx2.ReadTimeout("Request took too much time dude."),
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
    )
    with pytest.raises(httpx2.TimeoutException):
        await async_client.exchange(token_exchange_request)


async def test_async_client_exchange_token(
    async_client, httpx2_mock, token_exchange_request, token_exchange_response
):
    """Test the TokenExchangeAsyncClient exchange method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/exchange/",
        status_code=200,
        json=asdict(token_exchange_response),
    )
    exchanged_token = await async_client.exchange(token_exchange_request)

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


async def test_async_client_exchange_token_with_extra_field_in_response_payload(
    async_client, httpx2_mock, token_exchange_request, token_exchange_response, caplog
):
    """Test the TokenExchangeAsyncClient exchange method with an extra field in the response."""
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
        await async_client.exchange(token_exchange_request)
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
async def test_async_client_exchange_token_with_missing_fields_in_response_payload(  # noqa: PLR0913,PLR0917
    async_client, httpx2_mock, token_exchange_request, payload, missing, caplog
):
    """Test the TokenExchangeAsyncClient exchange method with missing fields in the response."""
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
        await async_client.exchange(token_exchange_request)
    assert (
        "Invalid token exchange response: TokenExchangeResponse.__init__() "
        f"missing {missing} required positional arguments" in caplog.messages[0]
    )


@pytest.mark.parametrize("body", ["not json", None, ""])
async def test_async_client_exchange_token_with_invalid_response_body(
    async_client, httpx2_mock, token_exchange_request, caplog, body
):
    """Test the TokenExchangeAsyncClient exchange method with an invalid response body."""
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
        await async_client.exchange(token_exchange_request)
    assert (
        "Invalid token exchange response: Expecting value: line 1 column 1 (char 0)"
        in caplog.messages
    )


@pytest.mark.parametrize("status", [401, 403, 500, 502])
async def test_async_client_introspect_raises_for_status(async_client, httpx2_mock, status):
    """Test the TokenExchangeAsyncClient introspect method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
        status_code=status,
    )
    with pytest.raises(httpx2.HTTPStatusError):
        await async_client.introspect(IntrospectionRequest(token="foo"))


async def test_async_client_introspect_raises_for_timeout(async_client, httpx2_mock):
    """Test the TokenExchangeAsyncClient introspect method with a request timeout."""
    httpx2_mock.add_exception(
        httpx2.ReadTimeout("Request took too much time dude."),
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
    )
    with pytest.raises(httpx2.TimeoutException):
        await async_client.introspect(IntrospectionRequest(token="foo"))


async def test_async_client_introspect_token(async_client, httpx2_mock):
    """Test the TokenExchangeAsyncClient introspect method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
        status_code=200,
        json=asdict(IntrospectionResponse(active=True)),
    )
    user_info = await async_client.introspect(IntrospectionRequest(token="foo"))

    assert isinstance(user_info, IntrospectionResponse)
    assert user_info.active


async def test_async_client_introspect_token_with_extra_field_in_response_payload(
    async_client, httpx2_mock, caplog
):
    """Test the TokenExchangeAsyncClient introspect method with an extra field in the response."""
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
        await async_client.introspect(IntrospectionRequest(token="foo"))
    assert (
        "Invalid introspection response: IntrospectionResponse.__init__() "
        "got an unexpected keyword argument 'foo'" in caplog.messages
    )


async def test_async_client_introspect_token_with_missing_fields_in_response_payload(  # noqa: PLR0913
    async_client, httpx2_mock, caplog
):
    """Test the TokenExchangeAsyncClient introspect method with missing fields in the response."""
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
        await async_client.introspect(IntrospectionRequest(token="foo"))
    assert (
        "Invalid introspection response: IntrospectionResponse.__init__() "
        "missing 1 required positional argument: 'active'" in caplog.messages[0]
    )


@pytest.mark.parametrize("body", ["not json", None, ""])
async def test_async_client_introspect_token_with_invalid_response_body(
    async_client, httpx2_mock, caplog, body
):
    """Test the TokenExchangeAsyncClient introspect method with an invalid response body."""
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
        await async_client.introspect(IntrospectionRequest(token="foo"))
    assert (
        "Invalid introspection response: Expecting value: line 1 column 1 (char 0)"
        in caplog.messages
    )


@pytest.mark.parametrize("status", [401, 403, 500, 502])
async def test_async_client_revoke_raises_for_status(async_client, httpx2_mock, status):
    """Test the TokenExchangeAsyncClient revoke method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
        status_code=status,
    )
    with pytest.raises(httpx2.HTTPStatusError):
        await async_client.revoke(RevocationRequest(token="foo"))


async def test_async_client_revoke_raises_for_timeout(async_client, httpx2_mock):
    """Test the TokenExchangeAsyncClient revoke method with a request timeout."""
    httpx2_mock.add_exception(
        httpx2.ReadTimeout("Request took too much time dude."),
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
    )
    with pytest.raises(httpx2.TimeoutException):
        await async_client.revoke(RevocationRequest(token="foo"))


@pytest.mark.parametrize("body", [None, "", "{}", '{"foo": "bar"}'])
async def test_async_client_revoke_token(async_client, httpx2_mock, body):
    """Test the TokenExchangeAsyncClient revoke method with various response content."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
        status_code=200,
        text=body,
    )
    revocation_response = await async_client.revoke(RevocationRequest(token="foo"))
    assert revocation_response is None
