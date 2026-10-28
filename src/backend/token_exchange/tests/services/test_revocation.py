"""Menshen: revocation service tests for the token_exchange application."""

import logging
from uuid import uuid4

from token_exchange.factories import ExchangedTokenFactory
from token_exchange.models import TokenTypeChoices
from token_exchange.services.revocation import RevocationService


def test_revocation_service_revoke_with_an_unknown_token(target_service, caplog):
    """Test the revocation service revocation with a token that does not exist."""
    with caplog.at_level(logging.INFO):
        RevocationService.revoke("foo", target_service)
    assert "Token revocation failed (not found)." in caplog.messages


def test_revocation_service_revoke(target_service, caplog):
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
    assert (
        "Token revoked: "
        f"token_jti={exchanged_token.subject_token_jti}, "
        f"sub={exchanged_token.subject_sub}, "
        f"email={exchanged_token.subject_email}, "
        f"type={exchanged_token.token_type}, "
        f"audiences={exchanged_token.audiences}"
    ) in caplog.messages
    assert response is None
