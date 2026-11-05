"""Menshen: revocation service tests for the token_exchange application."""

import logging
from uuid import uuid4

from django.utils import timezone

from token_exchange.factories import (
    ExchangedTokenFactory,
    ExpiredExchangedTokenFactory,
    ServiceProviderFactory,
)
from token_exchange.models import TokenTypeChoices
from token_exchange.services.revocation import RevocationService


def test_revocation_service_revoke_with_an_unknown_token(source_service, caplog):
    """Test the revocation service revocation with a token that does not exist."""
    with caplog.at_level(logging.INFO):
        RevocationService.revoke("foo", source_service)
    assert "Token revocation failed (not found)." in caplog.messages


def test_revocation_service_revoke_with_an_expired_token(source_service, caplog):
    """Test the revocation service revocation with an expired token."""
    raw_token = str(uuid4())
    exchanged_token = ExpiredExchangedTokenFactory.create(
        source_service=source_service, raw_token=raw_token
    )

    with caplog.at_level(logging.INFO):
        RevocationService.revoke(raw_token, source_service)

    exchanged_token.refresh_from_db()
    assert not exchanged_token.is_revoked()
    assert "Token revocation failed (invalid token)." in caplog.messages


def test_revocation_service_revoke_with_a_revoked_token(source_service, caplog):
    """Test the revocation service revocation with an already revoked token."""
    raw_token = str(uuid4())
    revoked_at = timezone.now()
    exchanged_token = ExchangedTokenFactory.create(
        source_service=source_service, raw_token=raw_token, revoked_at=revoked_at
    )

    with caplog.at_level(logging.INFO):
        RevocationService.revoke(raw_token, source_service)

    exchanged_token.refresh_from_db()
    assert exchanged_token.revoked_at == revoked_at
    assert "Token revocation failed (invalid token)." in caplog.messages


def test_revocation_service_revoke_by_target_service(source_service, target_service, caplog):
    """Test that the target service (token audience) cannot revoke the token."""
    raw_token = str(uuid4())
    exchanged_token = ExchangedTokenFactory.create(
        source_service=source_service,
        audiences=[target_service.audience_id],
        raw_token=raw_token,
    )

    with caplog.at_level(logging.INFO):
        RevocationService.revoke(raw_token, target_service)

    exchanged_token.refresh_from_db()
    assert not exchanged_token.is_revoked()
    assert (
        "'service:target' service tried to revoke an exchanged token it did not request"
        in caplog.messages
    )


def test_revocation_service_revoke_by_another_service(source_service, target_service, caplog):
    """Test that a service unrelated to the token cannot revoke it."""
    other_service = ServiceProviderFactory.create(audience_id="service:other")
    raw_token = str(uuid4())
    exchanged_token = ExchangedTokenFactory.create(
        source_service=source_service,
        audiences=[target_service.audience_id],
        raw_token=raw_token,
    )

    with caplog.at_level(logging.INFO):
        RevocationService.revoke(raw_token, other_service)

    exchanged_token.refresh_from_db()
    assert not exchanged_token.is_revoked()
    assert (
        "'service:other' service tried to revoke an exchanged token it did not request"
        in caplog.messages
    )


def test_revocation_service_revoke(source_service, target_service, caplog):
    """Test the revocation service revocation by the source service."""
    raw_token = str(uuid4())
    exchanged_token = ExchangedTokenFactory.create(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        source_service=source_service,
        audiences=[target_service.audience_id],
        raw_token=raw_token,
    )
    assert not exchanged_token.is_revoked()

    with caplog.at_level(logging.INFO):
        response = RevocationService.revoke(raw_token, source_service)

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
    assert response is None
