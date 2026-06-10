"""Menshen: introspection service tests for the token_exchange application."""

import logging
from datetime import UTC, datetime, timedelta

import pytest

from token_exchange.enums import (
    TokenExchangeTokenTypeHint,
)
from token_exchange.exceptions import ExchangedTokenInstrospectionError
from token_exchange.factories import ExchangedTokenFactory, JWTExchangedTokenFactory
from token_exchange.models import ExchangedToken, TokenTypeChoices
from token_exchange.services.introspection import TokenExchangeIntrospectionService
from token_exchange.services.token import TokenGenerator
from token_exchange.structs import IntrospectionRequest, IntrospectionResponse


@pytest.mark.parametrize(("service", "request_"), [(None, None), (None, ""), ("", None)])
def test_introspection_service_instantiation_with_bad_args(service, request_):
    """Test the introspection service instantiation with bad arguments."""
    with pytest.raises(ExchangedTokenInstrospectionError, match=r"Empty request or service\."):
        TokenExchangeIntrospectionService(service=service, request=request_)


@pytest.mark.parametrize(
    "token_type_hint",
    [None, TokenExchangeTokenTypeHint.REFRESH_TOKEN, TokenExchangeTokenTypeHint.ACCESS_TOKEN],
)
def test_introspection_service_token_property_with_optional_type_hint(
    target_service, token_type_hint
):
    """Test the introspection service token cached property with the optional token_type_hint."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN, audiences=[target_service.audience_id]
    )
    request = IntrospectionRequest(
        token=str(exchanged_token.token), token_type_hint=token_type_hint
    )
    introspection_service = TokenExchangeIntrospectionService(
        service=target_service, request=request
    )

    assert isinstance(introspection_service.exchanged_token, ExchangedToken)
    assert introspection_service.exchanged_token == exchanged_token


def test_introspection_service_token_property_with_bad_type_hint(target_service):
    """Test the introspection service token property with a bad token_type_hint."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN, audiences=[target_service.audience_id]
    )
    request = IntrospectionRequest(
        token=str(exchanged_token.token), token_type_hint=TokenExchangeTokenTypeHint.JWT
    )
    introspection_service = TokenExchangeIntrospectionService(
        service=target_service, request=request
    )

    assert isinstance(introspection_service.exchanged_token, ExchangedToken)
    assert introspection_service.exchanged_token == exchanged_token


def test_introspection_service_token_property_when_token_not_found(target_service, caplog):
    """Test the introspection service token property when the token is not found."""
    request = IntrospectionRequest(token="foo")
    introspection_service = TokenExchangeIntrospectionService(
        service=target_service, request=request
    )

    with (
        caplog.at_level(logging.INFO),
        pytest.raises(ExchangedTokenInstrospectionError, match=r"Token not found\."),
    ):
        assert introspection_service.exchanged_token
    assert not introspection_service.is_token_valid()
    assert "Introspected token not found." in caplog.messages


@pytest.mark.parametrize(
    ("expires_at", "revoked_at"),
    [
        (datetime(2026, 1, 1, 0, 0, tzinfo=UTC), None),
        (datetime.now(tz=UTC) + timedelta(days=30), (datetime(2026, 1, 1, 0, 0, tzinfo=UTC))),
        (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        ),
    ],
)
def test_introspection_service_token_expired_or_revoked(
    target_service, expires_at, revoked_at, caplog
):
    """Test the introspection service with an expired or revoked token."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
        expires_at=expires_at,
        revoked_at=revoked_at,
    )
    request = IntrospectionRequest(token=str(exchanged_token.token))
    introspection_service = TokenExchangeIntrospectionService(
        service=target_service, request=request
    )
    with caplog.at_level(logging.INFO):
        assert not introspection_service.is_token_valid()
    assert (
        "Token introspected (invalid): "
        f"token_jti={introspection_service.exchanged_token.subject_token_jti}, "
        f"type={introspection_service.exchanged_token.token_type}, "
        f"kid={introspection_service.exchanged_token.jwt_kid or 'N/A'}"
    ) in caplog.messages


def test_introspection_service_token_with_bad_audiences(target_service, caplog):
    """Test the introspection service with a bad audience."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=["service:foo"],
    )
    request = IntrospectionRequest(token=str(exchanged_token.token))
    introspection_service = TokenExchangeIntrospectionService(
        service=target_service, request=request
    )
    with caplog.at_level(logging.INFO):
        assert not introspection_service.is_token_valid()
    assert (
        f"'{target_service.audience_id}' service tried to introspect an exchanged token "
        "that is beyond its audience"
    ) in caplog.messages


def test_introspection_service_valid_access_token(target_service):
    """Test the introspection service with a valid access token."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
    )
    request = IntrospectionRequest(token=str(exchanged_token.token))
    introspection_service = TokenExchangeIntrospectionService(
        service=target_service, request=request
    )
    assert introspection_service.is_token_valid()


def test_introspection_service_valid_jwt(target_service):
    """Test the introspection service with a valid JWT."""
    exchanged_token = JWTExchangedTokenFactory()
    request = IntrospectionRequest(
        token=str(exchanged_token.token), token_type_hint=TokenExchangeTokenTypeHint.JWT
    )
    introspection_service = TokenExchangeIntrospectionService(
        service=target_service, request=request
    )
    assert introspection_service.is_token_valid()


def test_introspection_service_generate_response_with_invalid_jwt(target_service, settings, caplog):
    """Test the introspection service response generation with an invalid JWT."""
    exchanged_jwt = TokenGenerator.generate_jwt(
        sub="ef7d37b4-080c-4df7-b0f8-3560dc7138aa",
        email="jane.doe@example.org",
        audiences=["service:target"],
        scope="openid target:read target:write",
        expires_in=3600,
        kid=settings.TOKEN_EXCHANGE_JWT_CURRENT_KID,
        # Grants are missing
        grants=[],
    )

    exchanged_token = JWTExchangedTokenFactory(token=exchanged_jwt)
    request = IntrospectionRequest(
        token=str(exchanged_token.token), token_type_hint=TokenExchangeTokenTypeHint.JWT
    )
    introspection_service = TokenExchangeIntrospectionService(
        service=target_service, request=request
    )
    with caplog.at_level(logging.INFO):
        assert not introspection_service.is_token_valid()
    assert (
        "Token introspected: JWT signature verification failed: "
        "Invalid JWT claims: invalid_claim: Invalid claim: 'grants'"
    ) in caplog.messages

    response = introspection_service.generate_introspection_response()
    assert response == IntrospectionResponse(active=False)


def test_introspection_service_generate_response_with_valid_jwt(target_service, caplog):
    """Test the introspection service response generation with an valid JWT."""
    now = int(datetime.now(tz=UTC).timestamp())
    exchanged_token = JWTExchangedTokenFactory()
    request = IntrospectionRequest(
        token=str(exchanged_token.token), token_type_hint=TokenExchangeTokenTypeHint.JWT
    )
    introspection_service = TokenExchangeIntrospectionService(
        service=target_service, request=request
    )

    with caplog.at_level(logging.INFO):
        response = introspection_service.generate_introspection_response()
    assert response.active
    assert response.scope == "openid email profile"
    assert response.sub == "ef7d37b4-080c-4df7-b0f8-3560dc7138aa"
    assert response.email == "jane.doe@example.org"
    assert response.username == "jane.doe@example.org"
    assert response.token_type == "urn:ietf:params:oauth:token-type:jwt"
    assert response.exp
    assert response.exp > now
    assert response.iat
    # iat should be ~ now
    assert response.iat >= now - 2
    assert response.iat <= now + 2
    assert response.aud == ["service:target"]
    assert response.jti == exchanged_token.subject_token_jti
    assert response.client_id == "menshen"
    assert (
        "Token introspected (active): "
        f"token_jti={exchanged_token.subject_token_jti}, "
        f"type={exchanged_token.token_type}, "
        f"kid={exchanged_token.jwt_kid or 'N/A'}"
    ) in caplog.messages
