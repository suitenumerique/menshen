"""Menshen: introspection service tests for the token_exchange application."""

from datetime import UTC, datetime

from structlog.testing import capture_logs

from token_exchange.factories import JWTExchangedTokenFactory
from token_exchange.services.introspection import IntrospectionService
from token_exchange.services.token import TokenGenerator


def test_instrospection_service_revoke_with_an_unknown_token(target_service):
    """Test the instrospection service response generation with a token that does not exist."""
    with capture_logs() as log_events:
        IntrospectionService.introspect("foo", target_service)
    assert log_events == [
        {"event": "token_not_found", "log_level": "info"},
        {
            "event": "token_introspection_failed",
            "log_level": "error",
            "reason": "token_not_found",
        },
    ]


def test_introspection_service_introspect_with_valid_jwt(target_service, settings):
    """Test the introspection service response generation with a valid JWT."""
    now = int(datetime.now(tz=UTC).timestamp())
    raw_jwt = TokenGenerator.generate_jwt(
        sub="ef7d37b4-080c-4df7-b0f8-3560dc7138aa",
        email="jane.doe@example.org",
        audiences=["service:target"],
        scope="openid target:read target:write",
        expires_in=3600,
        kid=settings.TOKEN_EXCHANGE_JWT_CURRENT_KID,
        grants=[],
    )
    exchanged_token = JWTExchangedTokenFactory(raw_token=raw_jwt)

    with capture_logs() as log_events:
        response = IntrospectionService.introspect(raw_jwt, target_service)
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
    assert response.aud == "service:target"
    assert response.jti == exchanged_token.subject_token_jti
    assert response.client_id == exchanged_token.source_service.audience_id  # ty: ignore
    assert log_events == [
        {
            "event": "token_introspected",
            "log_level": "info",
            "token_jti": exchanged_token.subject_token_jti,
            "type": exchanged_token.token_type,
            "kid": exchanged_token.jwt_kid or "N/A",
        }
    ]
