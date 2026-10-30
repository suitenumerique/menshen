"""Menshen: revocation service tests for the token_exchange application."""

import logging
from uuid import uuid4

from token_exchange.factories import ExchangedTokenFactory
from token_exchange.models import TokenTypeChoices
from token_exchange.services.revocation import RevocationService


def test_revocation_service_revoke_with_an_unknown_token(target_service, caplog, get_log_events):
    """Test the revocation service revocation with a token that does not exist."""
    with caplog.at_level(logging.INFO):
        RevocationService.revoke("foo", target_service)
    assert "token_revocation_failed" in get_log_events()


def test_revocation_service_revoke(target_service, caplog, get_log_events):
    """Test the revocation service revocation."""
    raw_token = str(uuid4())
    exchanged_token = ExchangedTokenFactory.create(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
        raw_token=raw_token,
    )
    assert not exchanged_token.is_revoked()

    with caplog.at_level(logging.INFO):
        response = RevocationService.revoke(raw_token, target_service)

    exchanged_token.refresh_from_db()
    assert exchanged_token.is_revoked()
    assert "token_revoked" in get_log_events()
    assert response is None
