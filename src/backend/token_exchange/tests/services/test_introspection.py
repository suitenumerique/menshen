"""Menshen: introspection service tests for the token_exchange application."""

import logging
from datetime import UTC, datetime

from token_exchange.factories import JWTExchangedTokenFactory
from token_exchange.services.introspection import IntrospectionService
from token_exchange.services.token import TokenGenerator
from token_exchange.structs import IntrospectionResponse


def test_instrospection_service_revoke_with_an_unknown_token(target_service, caplog):
    """Test the instrospection service response generation with a token that does not exist."""
    with caplog.at_level(logging.INFO):
        IntrospectionService.introspect("foo", target_service.audience_id)
    assert "Token introspection failed (not found)." in caplog.messages


def test_introspection_service_introspect_with_invalid_jwt(target_service, settings, caplog):
    """Test the introspection service response generation with an invalid JWT."""
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
        response = IntrospectionService.introspect(
            str(exchanged_token.token), target_service.audience_id
        )
    assert (
        "JWT signature verification failed (invalid_claim: Invalid claim: 'grants')"
    ) in caplog.messages
    assert response == IntrospectionResponse(active=False)


def test_introspection_service_introspect_with_valid_jwt(target_service, caplog):
    """Test the introspection service response generation with an valid JWT."""
    now = int(datetime.now(tz=UTC).timestamp())
    exchanged_token = JWTExchangedTokenFactory()

    with caplog.at_level(logging.INFO):
        response = IntrospectionService.introspect(
            str(exchanged_token.token), target_service.audience_id
        )
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
