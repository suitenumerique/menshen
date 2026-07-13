"""Menshen: service mixins tests for the token_exchange application."""

import logging
from datetime import UTC, datetime, timedelta

import pytest

from token_exchange.exceptions import TokenExchangeError
from token_exchange.factories import ExchangedTokenFactory, JWTExchangedTokenFactory
from token_exchange.models import TokenTypeChoices
from token_exchange.services.mixins import ExchangedTokenMixin
from token_exchange.services.token import TokenGenerator


def test_exchanged_token_mixin_when_token_not_found(caplog):
    """Test the ExchangedTokenMixin get_exchanged_token method when the token is not found."""
    with (
        caplog.at_level(logging.INFO),
        pytest.raises(TokenExchangeError, match=r"Token not found\."),
    ):
        ExchangedTokenMixin.get_exchanged_token("foo")
    assert "Token not found." in caplog.messages


def test_exchanged_token_mixin_get_exchanged_token(target_service):
    """Test the ExchangedTokenMixin get_exchanged_token method when the token exists."""
    exchanged_token = ExchangedTokenFactory.create(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
    )
    assert ExchangedTokenMixin.get_exchanged_token(str(exchanged_token.token)) == exchanged_token


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
def test_exchanged_token_mixin_token_expired_or_revoked(
    target_service, expires_at, revoked_at, caplog
):
    """Test the ExchangedTokenMixin with an expired or revoked token."""
    exchanged_token = ExchangedTokenFactory.build(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
        expires_at=expires_at,
        revoked_at=revoked_at,
    )
    with caplog.at_level(logging.INFO):
        assert not ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)
    assert (
        "Token is invalid: "
        f"token_jti={exchanged_token.subject_token_jti}, "
        f"type={exchanged_token.token_type}, "
        f"kid={exchanged_token.jwt_kid or 'N/A'}"
    ) in caplog.messages


def test_exchanged_token_mixin_token_with_bad_audiences(target_service, caplog):
    """Test the ExchangedTokenMixin with a bad audience."""
    exchanged_token = ExchangedTokenFactory.build(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=["service:foo"],
    )
    with caplog.at_level(logging.INFO):
        assert not ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)
    assert (
        f"'{target_service.audience_id}' service tried to act on an exchanged token "
        "that is beyond its audience"
    ) in caplog.messages


def test_exchanged_token_mixin_valid_access_token(target_service):
    """Test the ExchangedTokenMixin with a valid access token."""
    exchanged_token = ExchangedTokenFactory.build(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
    )
    assert ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)


def test_exchanged_token_mixin_valid_jwt(target_service):
    """Test the ExchangedTokenMixin with a valid JWT."""
    exchanged_token = JWTExchangedTokenFactory.build()
    assert ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)


def test_exchanged_token_mixin_invalid_jwt(target_service, settings):
    """Test the ExchangedTokenMixin with an invalid JWT."""
    exchanged_token = JWTExchangedTokenFactory.build(
        token=TokenGenerator.generate_jwt(
            sub="ef7d37b4-080c-4df7-b0f8-3560dc7138aa",
            email="jane.doe@example.org",
            audiences=["service:target"],
            scope="openid target:read target:write",
            expires_in=3600,
            kid=settings.TOKEN_EXCHANGE_JWT_CURRENT_KID,
            # Grants are missing
            grants=[],
        )
    )
    assert not ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)
