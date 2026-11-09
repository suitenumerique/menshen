"""Tests for the TokenExchangeAsyncClient."""

import logging
from dataclasses import asdict, replace

import httpx2
import pytest

from menshen_client.clients import TokenExchangeAsyncClient
from menshen_client.enums import TokenExchangeResponseTokenType, TokenType
from menshen_client.exceptions import InvalidTokenError, ResponseParsingError
from menshen_client.schemas import (
    Configuration,
    IntrospectionRequest,
    IntrospectionResponse,
    RevocationRequest,
    TokenExchangeResponse,
)

pytestmark = pytest.mark.anyio

TOKEN = "MZGYrOI1nQNTwCriw0iJaGk-iF7Fdk2pdJB8LMYuCF0"  # noqa: S105
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJl"


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
        await async_client.revoke(RevocationRequest(token=TOKEN))
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
        await async_client.introspect(IntrospectionRequest(token=TOKEN))


async def test_async_client_introspect_raises_for_timeout(async_client, httpx2_mock):
    """Test the TokenExchangeAsyncClient introspect method with a request timeout."""
    httpx2_mock.add_exception(
        httpx2.ReadTimeout("Request took too much time dude."),
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
    )
    with pytest.raises(httpx2.TimeoutException):
        await async_client.introspect(IntrospectionRequest(token=TOKEN))


async def test_async_client_introspect_token(async_client, httpx2_mock):
    """Test the TokenExchangeAsyncClient introspect method with an invalid response status."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/introspect/",
        status_code=200,
        json=asdict(IntrospectionResponse(active=True)),
    )
    user_info = await async_client.introspect(IntrospectionRequest(token=TOKEN))

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
        await async_client.introspect(IntrospectionRequest(token=TOKEN))
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
        await async_client.introspect(IntrospectionRequest(token=TOKEN))
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
        await async_client.introspect(IntrospectionRequest(token=TOKEN))
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
        await async_client.revoke(RevocationRequest(token=TOKEN))


async def test_async_client_revoke_raises_for_timeout(async_client, httpx2_mock):
    """Test the TokenExchangeAsyncClient revoke method with a request timeout."""
    httpx2_mock.add_exception(
        httpx2.ReadTimeout("Request took too much time dude."),
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
    )
    with pytest.raises(httpx2.TimeoutException):
        await async_client.revoke(RevocationRequest(token=TOKEN))


@pytest.mark.parametrize("body", [None, "", "{}", '{"foo": "bar"}'])
async def test_async_client_revoke_token(async_client, httpx2_mock, body):
    """Test the TokenExchangeAsyncClient revoke method with various response content."""
    httpx2_mock.add_response(
        method="POST",
        url="https://menshen.example.org/auth/token/revoke/",
        status_code=200,
        text=body,
    )
    revocation_response = await async_client.revoke(RevocationRequest(token=TOKEN))
    assert revocation_response is None


@pytest.mark.parametrize(
    ("method", "request_klass", "endpoint"),
    [
        ("introspect", IntrospectionRequest, "introspect"),
        ("revoke", RevocationRequest, "revoke"),
    ],
)
async def test_async_client_maps_server_422_to_invalid_token_error(
    async_client, httpx2_mock, method, request_klass, endpoint
):
    """A 422 from the server is surfaced as an InvalidTokenError."""
    httpx2_mock.add_response(
        method="POST",
        url=f"https://menshen.example.org/auth/token/{endpoint}/",
        status_code=422,
    )
    with pytest.raises(InvalidTokenError, match="Token rejected by the server") as exc_info:
        await getattr(async_client, method)(request_klass(token=TOKEN))
    assert isinstance(exc_info.value.__cause__, httpx2.HTTPStatusError)


@pytest.mark.parametrize(
    ("method", "request_klass", "endpoint"),
    [
        ("introspect", IntrospectionRequest, "introspect"),
        ("revoke", RevocationRequest, "revoke"),
    ],
)
@pytest.mark.parametrize(
    ("token", "token_type_hint"),
    [
        (TOKEN, None),
        (TOKEN, TokenType.ACCESS_TOKEN),
        ("a" * 64, None),
        ("-" * 43, None),
        ("_" * 43, None),
        (f" {TOKEN}\n", None),
        (JWT, None),
        (JWT, TokenType.ACCESS_TOKEN),
        ("foo", TokenType.JWT),  # Hinted JWTs are left to the server
    ],
)
async def test_async_client_token_validation_accepts_token(  # noqa: PLR0913,PLR0917
    async_client, httpx2_mock, method, request_klass, endpoint, token, token_type_hint
):
    """Valid opaque tokens and JWTs are sent to the server."""
    httpx2_mock.add_response(
        method="POST",
        url=f"https://menshen.example.org/auth/token/{endpoint}/",
        json={"active": True},
    )
    await getattr(async_client, method)(request_klass(token=token, token_type_hint=token_type_hint))
    assert len(httpx2_mock.get_requests()) == 1


@pytest.mark.parametrize(
    ("method", "request_klass"),
    [("introspect", IntrospectionRequest), ("revoke", RevocationRequest)],
)
@pytest.mark.parametrize(
    "token",
    [
        "",
        " " * 43,
        "foo",
        "a" * 32,
        "a" * 42,
        TOKEN[:-1] + "=",
        TOKEN[:-1] + "+",
        TOKEN[:-1] + "/",
        TOKEN[:-1] + "é",
        TOKEN[:20] + " " + TOKEN[21:],
        "a.b",
        "a..c",
        "a.b.c.d",
        "é.b.c",
    ],
)
async def test_async_client_token_validation_rejects_malformed_opaque_token(
    async_client, httpx2_mock, method, request_klass, token
):
    """Malformed opaque tokens are rejected without any network call."""
    with pytest.raises(InvalidTokenError, match="Invalid token format"):
        await getattr(async_client, method)(request_klass(token=token))
    assert not httpx2_mock.get_requests()


@pytest.mark.parametrize(
    ("method", "request_klass", "endpoint"),
    [
        ("introspect", IntrospectionRequest, "introspect"),
        ("revoke", RevocationRequest, "revoke"),
    ],
)
@pytest.mark.parametrize("min_length", [32, 43, 64])
async def test_async_client_token_validation_with_configured_min_length(  # noqa: PLR0913,PLR0917
    config, httpx2_mock, method, request_klass, endpoint, min_length
):
    """The opaque token min length is configurable."""
    async_client = TokenExchangeAsyncClient(
        config=replace(config, opaque_token_min_length=min_length)
    )

    with pytest.raises(InvalidTokenError, match="Invalid token format"):
        await getattr(async_client, method)(request_klass(token="a" * (min_length - 1)))
    assert not httpx2_mock.get_requests()

    httpx2_mock.add_response(
        method="POST",
        url=f"https://menshen.example.org/auth/token/{endpoint}/",
        json={"active": True},
    )
    await getattr(async_client, method)(request_klass(token="a" * min_length))
    assert len(httpx2_mock.get_requests()) == 1
