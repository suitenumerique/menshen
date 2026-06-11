"""Menshen: revocation service tests for the token_exchange application."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from django.core.exceptions import SuspiciousOperation

from token_exchange.enums import (
    TokenExchangeTokenTypeHint,
)
from token_exchange.exceptions import TokenExchangeExchangedTokenRevocationError
from token_exchange.factories import ExchangedTokenFactory, JWTExchangedTokenFactory
from token_exchange.models import ExchangedToken, TokenTypeChoices
from token_exchange.services.revocation import TokenExchangeRevocationService
from token_exchange.structs import TokenRevocationRequest


@pytest.mark.parametrize(("service", "request_"), [(None, None), (None, ""), ("", None)])
def test_revocation_service_instantiation_with_bad_args(service, request_):
    """Test the revocation service instantiation with bad arguments."""
    with pytest.raises(
        TokenExchangeExchangedTokenRevocationError, match=r"Empty request or service\."
    ):
        TokenExchangeRevocationService(service=service, request=request_)


def test_revocation_service_instantiation_with_base_request(target_service):
    """Test the revocation service instantiation with a base token revocation request."""
    request = TokenRevocationRequest(
        token="foo", token_type_hint=TokenExchangeTokenTypeHint.ACCESS_TOKEN
    )
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)

    assert revocation_service._service == target_service
    assert revocation_service._request == request
    assert revocation_service._token is None


@pytest.mark.parametrize(
    "token_type_hint",
    [None, TokenExchangeTokenTypeHint.REFRESH_TOKEN, TokenExchangeTokenTypeHint.ACCESS_TOKEN],
)
def test_revocation_service_token_property_with_optional_type_hint(target_service, token_type_hint):
    """Test the revocation service token property with the optional token_type_hint."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN, audiences=[target_service.audience_id]
    )
    request = TokenRevocationRequest(
        token=str(exchanged_token.token), token_type_hint=token_type_hint
    )
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)

    assert isinstance(revocation_service.token, ExchangedToken)
    assert revocation_service.token == exchanged_token


def test_revocation_service_token_property_with_bad_type_hint(target_service):
    """Test the revocation service token property with a bad token_type_hint."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN, audiences=[target_service.audience_id]
    )
    request = TokenRevocationRequest(
        token=str(exchanged_token.token), token_type_hint=TokenExchangeTokenTypeHint.JWT
    )
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)

    with pytest.raises(TokenExchangeExchangedTokenRevocationError, match=r"Token not found\."):
        assert revocation_service.token


def test_revocation_service_token_property_when_token_not_found(target_service, caplog):
    """Test the revocation service token property when the token is not found."""
    request = TokenRevocationRequest(token="foo")
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)

    with (
        caplog.at_level(logging.INFO),
        pytest.raises(TokenExchangeExchangedTokenRevocationError, match=r"Token not found\."),
    ):
        assert revocation_service.token
    assert not revocation_service.is_token_valid()
    assert "Token to revoke not found." in caplog.messages


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
def test_revocation_service_token_expired_or_revoked(
    target_service, expires_at, revoked_at, caplog
):
    """Test the revocation service with an expired or revoked token."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
        expires_at=expires_at,
        revoked_at=revoked_at,
    )
    request = TokenRevocationRequest(token=str(exchanged_token.token))
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)
    with caplog.at_level(logging.INFO):
        revocation_service.is_token_valid()
    assert (
        "Token to revoke (invalid): "
        f"token_jti={revocation_service.token.subject_token_jti}, "
        f"type={revocation_service.token.token_type}, "
        f"kid={revocation_service.token.jwt_kid or 'N/A'}"
    ) in caplog.messages


def test_revocation_service_token_with_bad_audiences(target_service, caplog):
    """Test the revocation service with an expired or revoked token."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=["service:foo"],
    )
    request = TokenRevocationRequest(token=str(exchanged_token.token))
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)
    with pytest.raises(SuspiciousOperation), caplog.at_level(logging.INFO):
        revocation_service.is_token_valid()
    assert (
        f"'{target_service.audience_id}' service tried to revoke an exchanged token "
        "that is beyond its audience"
    ) in caplog.messages


def test_revocation_service_valid_access_token(target_service):
    """Test the revocation service with a valid access token."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
    )
    request = TokenRevocationRequest(token=str(exchanged_token.token))
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)
    assert revocation_service.is_token_valid()


def test_revocation_service_valid_jwt(target_service):
    """Test the revocation service with a valid JWT."""
    exchanged_token = JWTExchangedTokenFactory()
    request = TokenRevocationRequest(
        token=str(exchanged_token.token), token_type_hint=TokenExchangeTokenTypeHint.JWT
    )
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)
    assert revocation_service.is_token_valid()


def test_revocation_service_revoke_with_invalid_token(target_service, caplog):
    """Test the revocation service revocation with an invalid token."""
    request = TokenRevocationRequest(token="foo")
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)

    with caplog.at_level(logging.INFO):
        revocation_service.revoke()
    assert "Token revocation failed (not found)." in caplog.messages


def test_revocation_service_revoke(target_service, caplog):
    """Test the revocation service revocation."""
    exchanged_token = ExchangedTokenFactory.create(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
    )
    assert not exchanged_token.is_revoked()

    request = TokenRevocationRequest(token=str(exchanged_token.token))
    revocation_service = TokenExchangeRevocationService(service=target_service, request=request)

    with caplog.at_level(logging.INFO):
        revocation_service.revoke()

    exchanged_token.refresh_from_db()
    assert exchanged_token.is_revoked()
    assert (
        "Token revoked: "
        f"token_jti={exchanged_token.subject_token_jti}, "
        f"sub={exchanged_token.subject_sub}, "
        f"email={exchanged_token.subject_email}, "
        f"type={exchanged_token.token_type}, "
        f"audiences={exchanged_token.audiences}"
    ) in caplog.messages
