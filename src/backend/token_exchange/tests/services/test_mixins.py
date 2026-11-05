"""Menshen: service mixins tests for the token_exchange application."""

from datetime import UTC, datetime, timedelta
from unittest import mock
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from token_exchange.exceptions import TokenExchangeError
from token_exchange.factories import ExchangedTokenFactory, JWTExchangedTokenFactory
from token_exchange.models import TokenTypeChoices
from token_exchange.services.mixins import ExchangedTokenMixin
from token_exchange.services.token import TokenGenerator


def test_exchanged_token_mixin_when_token_not_found():
    """Test the ExchangedTokenMixin get_exchanged_token method when the token is not found."""
    with (
        capture_logs() as log_events,
        pytest.raises(TokenExchangeError, match=r"Token not found\."),
    ):
        ExchangedTokenMixin.get_exchanged_token("foo")
    assert log_events == [{"event": "token_not_found", "log_level": "info"}]


def test_exchanged_token_mixin_get_exchanged_token(target_service):
    """Test the ExchangedTokenMixin get_exchanged_token method when the token exists."""
    raw_token = str(uuid4())
    exchanged_token = ExchangedTokenFactory.create(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
        raw_token=raw_token,
    )
    assert ExchangedTokenMixin.get_exchanged_token(raw_token) == exchanged_token


def test_exchanged_token_mixin_get_exchanged_token_with_wrong_hash_key(target_service, settings):
    """Test the ExchangedTokenMixin get_exchanged_token method with another hash key."""
    raw_token = str(uuid4())
    ExchangedTokenFactory.create(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
        raw_token=raw_token,
    )
    # Rotating the hash key invalidates outstanding tokens
    settings.TOKEN_EXCHANGE_TOKEN_HASH_KEY = "another-key"
    with pytest.raises(TokenExchangeError, match=r"Token not found\."):
        ExchangedTokenMixin.get_exchanged_token(raw_token)


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
def test_exchanged_token_mixin_token_expired_or_revoked(target_service, expires_at, revoked_at):
    """Test the ExchangedTokenMixin with an expired or revoked token."""
    exchanged_token = ExchangedTokenFactory.build(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
        expires_at=expires_at,
        revoked_at=revoked_at,
    )
    with capture_logs() as log_events:
        assert not ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)
    assert log_events == [
        {
            "event": "exchanged_token_invalid",
            "log_level": "warning",
            "token_jti": exchanged_token.subject_token_jti,
            "type": exchanged_token.token_type,
            "kid": "N/A",
        }
    ]


def test_exchanged_token_mixin_token_with_bad_audiences(target_service):
    """Test the ExchangedTokenMixin with a bad audience."""
    exchanged_token = ExchangedTokenFactory.build(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=["service:foo"],
    )
    with capture_logs() as log_events:
        assert not ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)
    assert log_events == [
        {
            "event": "token_audience_mismatch",
            "log_level": "error",
            "audience": target_service.audience_id,
            "audiences": ["service:foo"],
        }
    ]


def test_exchanged_token_mixin_valid_access_token(target_service):
    """Test the ExchangedTokenMixin with a valid access token."""
    exchanged_token = ExchangedTokenFactory.build(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
    )
    assert ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)


def test_exchanged_token_mixin_token_without_source_service(target_service):
    """Test the ExchangedTokenMixin with a token whose source service does not exist."""
    exchanged_token = ExchangedTokenFactory.build(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
        source_service=None,
    )
    with capture_logs() as log_events:
        assert not ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)
    assert log_events == [
        {
            "event": "exchanged_token_invalid",
            "log_level": "warning",
            "token_jti": exchanged_token.subject_token_jti,
            "type": exchanged_token.token_type,
            "kid": "N/A",
        }
    ]


def test_exchanged_token_mixin_valid_jwt(target_service):
    """Test the ExchangedTokenMixin with a valid JWT."""
    exchanged_token = JWTExchangedTokenFactory.build()
    assert ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)


def test_exchanged_token_mixin_jwt_without_signature_re_verification(target_service, monkeypatch):
    """
    Test the ExchangedTokenMixin does not re-verify the JWT signature.

    Since the token is looked up by the exact hash of its value, the signature
    is not re-verified when validating an exchanged JWT: a JWT signed with a
    key that has since been rotated remains introspectable until it expires.

    """
    mock_verify = mock.Mock(side_effect=ValueError("key rotated"))
    monkeypatch.setattr(TokenGenerator, "verify_jwt", mock_verify)
    exchanged_token = JWTExchangedTokenFactory.build()
    assert ExchangedTokenMixin.is_token_valid(exchanged_token, target_service.audience_id)
    mock_verify.assert_not_called()
