"""Menshen: request service tests for the token_exchange application."""

import logging
from unittest.mock import Mock

import pytest
from django.core.exceptions import SuspiciousOperation
from pytest_django.asserts import assertNumQueries
from requests import ConnectionError as ConnectionError_
from requests import HTTPError

from token_exchange.enums import (
    AllowedRequestedTokenType,
    AllowedSubjectTokenType,
    TokenExchangeResponseTokenType,
    TokenType,
)
from token_exchange.exceptions import (
    TokenExchangeConfigurationError,
    TokenExchangeIntrospectionError,
    TokenExchangeInvalidActionError,
    TokenExchangeInvalidScopesError,
    TokenExchangeInvalidTargetError,
    TokenExchangeIssuingError,
    TokenExchangeResourceServerIntrospectionError,
)
from token_exchange.factories import (
    ActionScopeFactory,
    ActionScopeGrantFactory,
    TokenExchangeActionPermissionFactory,
)
from token_exchange.models import ExchangedToken
from token_exchange.services.request import RequestService
from token_exchange.services.token import TokenGenerator
from token_exchange.structs import MenshenJWTGrantClaim, TokenExchangeRequest


def test_request_service_validate_target_only_unknown_audiences(source_service, caplog):
    """Test the request service validate target method with only unknown audiences."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:foo",
    )
    with (
        pytest.raises(
            TokenExchangeInvalidTargetError,
            match=r"Only unknown audience\(s\) requested",
        ),
        caplog.at_level(logging.INFO),
    ):
        RequestService.exchange(source_service.audience_id, request)
    assert "Only unknown audience(s) requested: service:foo" in caplog.messages


def test_request_service_validate_target_with_unknown_audience(source_service, caplog):
    """Test the request service validate target method with unknown audience."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:target service:foo",
    )
    with (
        pytest.raises(
            TokenExchangeInvalidTargetError,
            match=r"Unknown audience\(s\) requested.",
        ),
        caplog.at_level(logging.INFO),
    ):
        RequestService.exchange(source_service.audience_id, request)
    assert "Unknown audience(s) requested: service:foo" in caplog.messages


def test_request_service_introspect_subject_token_request_failure(
    source_service, settings, monkeypatch
):
    """Test the request service introspect subject token method when the request fails."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:target",
    )

    # HTTPError
    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection",
        Mock(side_effect=HTTPError("Connection fails")),
    )
    with pytest.raises(
        TokenExchangeResourceServerIntrospectionError, match="Failed to introspect subject token"
    ):
        RequestService.exchange(source_service.audience_id, request)

    # ConnectionError
    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection",
        Mock(side_effect=ConnectionError_("Connection fails")),
    )
    with pytest.raises(
        TokenExchangeResourceServerIntrospectionError, match="Failed to introspect subject token"
    ):
        RequestService.exchange(source_service.audience_id, request)


def test_request_service_introspect_subject_token_suspicious_introspection_response_audience(
    source_service, monkeypatch, settings, caplog
):
    """
    Test the request service introspect subject token method when suspicious audience raises.

    Invalid introspection response audience_id case.

    """
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:target",
    )

    # Monkeypatch OIDC backend token introspection
    def mock_user_info(self, _):
        self.token_origin_audience = "service:source"
        return {"active": True, "client_id": "service:suspicious"}

    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection", mock_user_info
    )
    with pytest.raises(SuspiciousOperation), caplog.at_level(logging.INFO):
        RequestService.exchange(source_service.audience_id, request)

    assert (
        "Introspected token audience is different from requesting service: "
        "service:suspicious, service:source"
    ) in caplog.messages


def test_request_service_introspect_subject_token_missing_identity(
    source_service, monkeypatch, settings, caplog
):
    """Test the request service introspect subject token method when not identity is returned."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:target",
    )

    # Monkeypatch OIDC backend token introspection
    def mock_user_info(self, _):
        self.token_origin_audience = "service:source"
        return {"active": True, "client_id": "service:source"}

    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection", mock_user_info
    )
    with (
        pytest.raises(
            TokenExchangeIntrospectionError,
            match=r"Subject token introspection failed to provide an identity \(sub\)",
        ),
        caplog.at_level(logging.WARNING),
    ):
        RequestService.exchange(source_service.audience_id, request)

    assert "Introspection response has no 'sub'" in caplog.messages


def test_request_service_validate_pure_scopes_from_request(source_service):
    """
    Test the request service validate pure scopes method with scopes from the request.

    Add expected scopes in the request; expected scopes are those granted by linked services rules.

    """
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:target",
        scope="target:read target:write",
    )
    response, _ = RequestService.exchange(source_service.audience_id, request)

    # Scopes from request scope are granted
    assert response.scope == "target:read target:write"
    assert set(response.grants) == {
        MenshenJWTGrantClaim(audience_id="service:target", scope=scope, throttle=None)
        for scope in response.scope.split(" ")
    }


def test_request_service_validate_pure_scopes_from_request_with_extra_scopes(source_service):
    """Test the request service validate pure scopes method with extra scopes from the request."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:target",
        scope="target:read target:write extra",
    )
    with pytest.raises(
        TokenExchangeInvalidScopesError, match="You cannot request more scope than rules allow"
    ):
        RequestService.exchange(source_service.audience_id, request)


def test_request_service_validate_scope_action_from_request_with_granted_required_source_scope(
    source_service, target_service, source_target_rule, monkeypatch, settings
):
    """
    Test the request service validate scope action method with scopes from the request.

    In this case, one extra TokenExhangeActionPermission has an additional required source scope
    and the user has this scope.

    """
    # Add extra TokenExchangeActionPermissionFactory with required_source_scope
    extra_action = ActionScopeFactory(name="action:update-target")
    ActionScopeGrantFactory(
        action=extra_action, target_service=target_service, granted_scope="target:update"
    )
    TokenExchangeActionPermissionFactory(
        rule=source_target_rule,
        action=extra_action,
        required_source_scope="target:update",
    )

    # Monkeypatch OIDC backend token introspection
    def mock_user_info(self, _):
        self.token_origin_audience = "service:source"
        return {
            "active": True,
            "client_id": "service:source",
            "email": "jane.doe@example.org",
            "scope": "openid target:read target:write target:update",
            "jti": "beb588cf-6ba4-4158-942e-09d221e95968",
            "sub": "ab99a1fc-bfb8-407e-bc3b-a572ea22e0cb",
        }

    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection", mock_user_info
    )

    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:target",
        scope="action:update-target",
    )
    with assertNumQueries(4):
        response, _ = RequestService.exchange(source_service.audience_id, request)

    # Scopes from request action are granted
    assert response.scope == "target:update"
    assert response.grants == [
        MenshenJWTGrantClaim(audience_id="service:target", scope="target:update", throttle=None)
    ]


def test_request_service_validate_scope_action_from_request_when_action_has_no_permission(
    source_service, target_service, caplog
):
    """
    Test the request service validate scope action method with scopes from the request.

    In this case, an extra TokenExchangeActionPermission is required but not defined,
    thus the action cannot be granted.

    """
    # Add extra TokenExchangeActionPermissionFactory with required_source_scope
    extra_action = ActionScopeFactory(name="action:update-target")
    ActionScopeGrantFactory(
        action=extra_action, target_service=target_service, granted_scope="target:update"
    )

    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:target",
        scope="action:update-target",
    )
    with (
        pytest.raises(
            TokenExchangeInvalidScopesError,
            match="You cannot request more scope than rules allow.",
        ),
        caplog.at_level(logging.INFO),
    ):
        RequestService.exchange(source_service.audience_id, request)

    # Scopes from request action are not granted
    assert (
        "Unsatisfied requested accesses ({'service:target:action:update-target'}) "
        "given rules ({'service:target:action:write-to-target'})"
    ) in caplog.messages


def test_request_service_validate_scope_action_from_request_when_action_cannot_be_granted(
    source_service, target_service, source_target_rule, caplog
):
    """
    Test the request service validate scope action method with scopes from the request.

    In this case, one TokenExhangeActionPermission has a required source scope
    and the user has not this scope, thus the action cannot be granted.

    """
    # Add extra TokenExchangeActionPermissionFactory with required_source_scope
    extra_action = ActionScopeFactory(name="action:update-target")
    ActionScopeGrantFactory(
        action=extra_action, target_service=target_service, granted_scope="target:update"
    )
    TokenExchangeActionPermissionFactory(
        rule=source_target_rule,
        action=extra_action,
        required_source_scope="target:update",
    )

    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        audience="service:target",
        scope="action:update-target",
    )
    with (
        pytest.raises(
            TokenExchangeInvalidActionError,
            match="All required source scopes are not satisfied for this action.",
        ),
        caplog.at_level(logging.INFO),
    ):
        RequestService.exchange(source_service.audience_id, request)

    # Scopes from request action are not granted
    assert "Missing required source scope(s): target:update" in caplog.messages


@pytest.mark.parametrize("token_type", [TokenType.ACCESS_TOKEN, TokenType.JWT])
def test_request_service_generate_exchange_token_with_type(token_type, source_service):
    """Test the request service generate exchange token method with a given token type."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
        requested_token_type=token_type,
    )
    response, _ = RequestService.exchange(source_service.audience_id, request)
    assert isinstance(response.access_token, str)
    assert len(response.access_token) >= 32


def test_request_service_generate_exchange_token_jwt_no_sub_claim(
    source_service, settings, monkeypatch
):
    """Test the request service generate exchange token method with missing sub claim."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
        requested_token_type=AllowedRequestedTokenType.JWT,
    )

    # Monkeypatch OIDC backend token introspection
    def mock_user_info(self, _):
        self.token_origin_audience = "service:source"
        return {
            "active": True,
            "client_id": "service:source",
            "email": "jane.doe@example.org",
            "scope": "openid target:read target:write target:update",
            "jti": "beb588cf-6ba4-4158-942e-09d221e95968",
            "sub": "",
        }

    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection", mock_user_info
    )
    with pytest.raises(
        TokenExchangeIntrospectionError,
        match=r"Subject token introspection failed to provide an identity \(sub\)",
    ):
        RequestService.exchange(source_service.audience_id, request)


def test_request_service_generate_exchange_token_jwt_configuration(source_service, monkeypatch):
    """Test the request service generate exchange token method with missing kid."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
        requested_token_type=AllowedSubjectTokenType.JWT,
    )
    monkeypatch.setattr(RequestService, "kid", None)
    with pytest.raises(TokenExchangeConfigurationError, match="JWT signing key is not configured."):
        RequestService.exchange(source_service.audience_id, request)


def test_request_service_generate_exchange_token_unsupported_type(source_service):
    """Test the request service generate exchange token method with an unsupported token type."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
        requested_token_type=TokenType.REFRESH_TOKEN,  # ty: ignore
    )
    with pytest.raises(
        TokenExchangeConfigurationError, match="Configured request token type is not supported."
    ):
        RequestService.exchange(source_service.audience_id, request)


def test_request_service_generate_exchange_token_jwt_invalid_token(source_service, monkeypatch):
    """Test the request service generate exchange token method generates an invalid JWT."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
        requested_token_type=AllowedSubjectTokenType.JWT,
    )
    monkeypatch.setattr(TokenGenerator, "generate_jwt", Mock(side_effect=ValueError()))
    with pytest.raises(TokenExchangeIssuingError, match="An error occurred while issuing JWT."):
        RequestService.exchange(source_service.audience_id, request)


@pytest.mark.parametrize(
    "token_type", [AllowedRequestedTokenType.ACCESS_TOKEN, AllowedRequestedTokenType.JWT]
)
def test_request_service_generate_exchange_response(source_service, token_type):
    """Test the request service generate exchange response."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
        requested_token_type=token_type,
    )
    # No persisted token exists
    assert ExchangedToken.objects.count() == 0
    response, _ = RequestService.exchange(source_service.audience_id, request)
    # Exchanged token should not have been persisted
    assert ExchangedToken.objects.count() == 0
    assert isinstance(response.access_token, str)
    assert len(response.access_token) > 32
    assert response.issued_token_type == token_type
    assert response.token_type == TokenExchangeResponseTokenType.BEARER
    assert response.expires_in == 300  # rules' default is 5 minutes
    assert response.scope == "target:write"
    assert response.refresh_token is None
    assert len(response.grants) == 1
    assert response.grants[0].scope == "target:write"


@pytest.mark.parametrize(
    "token_type", [AllowedRequestedTokenType.ACCESS_TOKEN, AllowedRequestedTokenType.JWT]
)
def test_request_service_generate_exchange_response_with_persist(source_service, token_type):
    """Test the request service generate exchange response."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenType.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
        requested_token_type=token_type,
    )
    # No persisted token exists
    assert ExchangedToken.objects.count() == 0
    response, exchanged_token = RequestService.exchange(
        source_service.audience_id, request, persist=True
    )
    assert ExchangedToken.objects.count() == 1
    assert exchanged_token
    assert exchanged_token.token == response.access_token
