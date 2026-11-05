"""Menshen: revocation service tests for the token_exchange application."""

from uuid import uuid4

from django.utils import timezone
from structlog.testing import capture_logs

from token_exchange.factories import (
    ExchangedTokenFactory,
    ExpiredExchangedTokenFactory,
    ServiceProviderFactory,
)
from token_exchange.models import TokenTypeChoices
from token_exchange.services.revocation import RevocationService


def test_revocation_service_revoke_with_an_unknown_token(source_service):
    """Test the revocation service revocation with a token that does not exist."""
    with capture_logs() as log_events:
        RevocationService.revoke("foo", source_service)
    assert log_events == [
        {"event": "token_not_found", "log_level": "info"},
        {
            "event": "token_revocation_failed",
            "log_level": "error",
            "reason": "token_not_found",
        },
    ]


def test_revocation_service_revoke_with_an_expired_token(source_service):
    """Test the revocation service revocation with an expired token."""
    raw_token = str(uuid4())
    exchanged_token = ExpiredExchangedTokenFactory.create(
        source_service=source_service, raw_token=raw_token
    )

    with capture_logs() as log_events:
        RevocationService.revoke(raw_token, source_service)

    exchanged_token.refresh_from_db()
    assert not exchanged_token.is_revoked()
    assert {
        "event": "token_revocation_failed",
        "log_level": "error",
        "reason": "invalid_token",
    } in log_events


def test_revocation_service_revoke_with_a_revoked_token(source_service):
    """Test the revocation service revocation with an already revoked token."""
    raw_token = str(uuid4())
    revoked_at = timezone.now()
    exchanged_token = ExchangedTokenFactory.create(
        source_service=source_service, raw_token=raw_token, revoked_at=revoked_at
    )

    with capture_logs() as log_events:
        RevocationService.revoke(raw_token, source_service)

    exchanged_token.refresh_from_db()
    assert exchanged_token.revoked_at == revoked_at
    assert {
        "event": "token_revocation_failed",
        "log_level": "error",
        "reason": "invalid_token",
    } in log_events


def test_revocation_service_revoke_by_target_service(source_service, target_service):
    """Test that the target service (token audience) cannot revoke the token."""
    raw_token = str(uuid4())
    exchanged_token = ExchangedTokenFactory.create(
        source_service=source_service,
        audiences=[target_service.audience_id],
        raw_token=raw_token,
    )

    with capture_logs() as log_events:
        RevocationService.revoke(raw_token, target_service)

    exchanged_token.refresh_from_db()
    assert not exchanged_token.is_revoked()
    assert {
        "event": "token_revocation_failed",
        "log_level": "error",
        "reason": "not_source_service",
        "service": "service:target",
    } in log_events


def test_revocation_service_revoke_by_another_service(source_service, target_service):
    """Test that a service unrelated to the token cannot revoke it."""
    other_service = ServiceProviderFactory.create(audience_id="service:other")
    raw_token = str(uuid4())
    exchanged_token = ExchangedTokenFactory.create(
        source_service=source_service,
        audiences=[target_service.audience_id],
        raw_token=raw_token,
    )

    with capture_logs() as log_events:
        RevocationService.revoke(raw_token, other_service)

    exchanged_token.refresh_from_db()
    assert not exchanged_token.is_revoked()
    assert {
        "event": "token_revocation_failed",
        "log_level": "error",
        "reason": "not_source_service",
        "service": "service:other",
    } in log_events


def test_revocation_service_revoke(source_service, target_service):
    """Test the revocation service revocation by the source service."""
    raw_token = str(uuid4())
    exchanged_token = ExchangedTokenFactory.create(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        source_service=source_service,
        audiences=[target_service.audience_id],
        raw_token=raw_token,
    )
    assert not exchanged_token.is_revoked()

    with capture_logs() as log_events:
        response = RevocationService.revoke(raw_token, source_service)

    exchanged_token.refresh_from_db()
    assert exchanged_token.is_revoked()
    assert log_events == [
        {
            "event": "token_revoked",
            "log_level": "info",
            "token_jti": exchanged_token.subject_token_jti,
            "sub": exchanged_token.subject_sub,
            "email": exchanged_token.subject_email,
            "type": exchanged_token.token_type,
            "audiences": exchanged_token.audiences,
        }
    ]
    assert response is None
