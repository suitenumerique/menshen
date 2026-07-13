"""Menshen: revocation service tests for the token_exchange application."""

import logging

from token_exchange.factories import ExchangedTokenFactory, JWTExchangedTokenFactory
from token_exchange.models import TokenTypeChoices
from token_exchange.services.revocation import RevocationService
from token_exchange.services.token import TokenGenerator


def test_revocation_service_revoke_with_an_unknown_token(target_service, caplog):
    """Test the revocation service revocation with a token that does not exist."""
    with caplog.at_level(logging.INFO):
        RevocationService.revoke("foo", target_service.audience_id)
    assert "Token revocation failed (not found)." in caplog.messages


def test_revocation_service_revoke_with_invalid_jwt(target_service, settings, caplog):
    """Test the revocation service revocation with an invalid JWT."""
    exchanged_token = JWTExchangedTokenFactory(
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
    with caplog.at_level(logging.INFO):
        response = RevocationService.revoke(str(exchanged_token.token), target_service.audience_id)
    assert (
        "JWT signature verification failed (invalid_claim: Invalid claim: 'grants')"
    ) in caplog.messages
    assert ("Token revocation failed (invalid token).") in caplog.messages
    assert response is None


def test_revocation_service_revoke(target_service, caplog):
    """Test the revocation service revocation."""
    exchanged_token = ExchangedTokenFactory.create(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
    )
    assert not exchanged_token.is_revoked()

    with caplog.at_level(logging.INFO):
        response = RevocationService.revoke(str(exchanged_token.token), target_service.audience_id)

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
