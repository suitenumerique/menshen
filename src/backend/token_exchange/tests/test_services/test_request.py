"""Menshen: request service tests for the token_exchange application."""

import datetime
import logging
from unittest.mock import Mock
from uuid import UUID

import pytest
from django.core.exceptions import SuspiciousOperation
from pytest_django.asserts import assertNumQueries
from requests import ConnectionError as ConnectionError_
from requests import HTTPError

from token_exchange.enums import (
    AllowedRequestedTokenTypeEnum,
    AllowedSubjectTokenTypeEnum,
    TokenExchangeResponseTokenType,
    TokenTypeEnum,
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
    ServiceProviderFactory,
    TokenExchangeActionPermissionFactory,
    TokenExchangeRuleFactory,
)
from token_exchange.services.request import TokenExchangeRequestService
from token_exchange.services.token import TokenGenerator
from token_exchange.structs import IntrospectionResponse, MenshenJWTGrantClaim, TokenExchangeRequest


def test_request_service_instantiation_with_base_request(source_service, settings):
    """Test the request service instantiation with a base token exchange request."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    assert request_service.source_audience == source_service.audience_id
    assert request_service.request == request
    assert request_service.requested_audiences == [source_service.audience_id]
    assert request_service.granted_scopes == set()
    assert request_service.grants == []
    assert request_service.kid == settings.TOKEN_EXCHANGE_JWT_CURRENT_KID
    assert request_service.audiences == [source_service.audience_id]

    # Introspection should be ok
    assert isinstance(request_service.user_info, IntrospectionResponse)
    assert request_service.user_info.active
    assert request_service.user_info.client_id == "service:source"
    assert request_service.user_info.email == "jane.doe@example.org"
    assert request_service.user_info.scope == "openid target:read target:write"
    assert request_service.user_info.jti
    assert request_service.user_info.sub
    assert isinstance(request_service.user_info.jti, UUID)
    assert isinstance(request_service.user_info.sub, UUID)


@pytest.mark.parametrize(
    ("request_audience", "multi_audience_allowed", "expected_audiences"),
    [
        ("service:target foo bar", True, ["service:target", "foo", "bar"]),
        ("service:target foo bar", False, ["service:target"]),
    ],
)
def test_request_service_instantiation_audiences(
    request_audience, multi_audience_allowed, expected_audiences, settings, source_service
):
    """Test the request service instantiation with a base token exchange request."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience=request_audience,
    )
    settings.TOKEN_EXCHANGE_MULTI_AUDIENCES_ALLOWED = multi_audience_allowed
    request_service = TokenExchangeRequestService(source_service.audience_id, request)
    assert request_service.requested_audiences == ["service:target", "foo", "bar"]
    assert request_service.audiences == expected_audiences


def test_request_service_rules_cached_property(source_service, target_service):
    """Test the request service rules property."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    # Database query should be cached
    with assertNumQueries(1):
        for _ in range(5):
            [rule.target_service.audience_id for rule in request_service.rules]

    # Check service-related rule
    assert len(request_service.rules) == 1
    rule = request_service.rules[0]
    assert rule.source_service == source_service
    assert rule.target_service == target_service
    assert rule.exchanged_token_duration == datetime.timedelta(minutes=5)
    assert rule.is_active


def test_request_service_rules_cached_property_with_inactive_rule(source_service, target_service):
    """Test the request service rules property with an inactive rule."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    # Inactivate source/target services associated rule
    rule = source_service.exchange_out.get()
    rule.is_active = False
    rule.save()

    assert len(request_service.rules) == 0


def test_request_service_validate_target_only_unknown_audiences(
    source_service, monkeypatch, caplog
):
    """Test the request service validate target method with only unknown audiences."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    # Remove all rules associated with the services
    monkeypatch.setattr(request_service, "rules", [])
    with (
        pytest.raises(
            TokenExchangeInvalidTargetError,
            match=r"Only unknown audience\(s\) requested",
        ),
        caplog.at_level(logging.INFO),
    ):
        request_service._validate_target()
    assert "Only unknown audience(s) requested: service:target" in caplog.messages


def test_request_service_validate_target_with_unknown_audience(source_service, caplog):
    """Test the request service validate target method with unknown audience."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target service:foo",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    with (
        pytest.raises(
            TokenExchangeInvalidTargetError,
            match=r"Unknown audience\(s\) requested.",
        ),
        caplog.at_level(logging.INFO),
    ):
        request_service._validate_target()
    assert "Unknown audience(s) requested: service:foo" in caplog.messages

    # Reset the cache
    del request_service.rules

    # Create the rule associating service:source to service:foo
    foo_service = ServiceProviderFactory(name="foo", audience_id="service:foo")
    TokenExchangeRuleFactory(source_service=source_service, target_service=foo_service)

    # Should be ok now
    request_service._validate_target()


def test_request_service_introspect_subject_token_request_failure(source_service, monkeypatch):
    """Test the request service introspect subject token method when the request fails."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    # HTTPError
    monkeypatch.setattr(
        request_service.introspection_backend,
        "get_user_info_with_introspection",
        Mock(side_effect=HTTPError("Connection fails")),
    )
    with pytest.raises(
        TokenExchangeResourceServerIntrospectionError, match="Failed to introspect subject token"
    ):
        request_service._introspect_subject_token()

    # ConnectionError
    monkeypatch.setattr(
        request_service.introspection_backend,
        "get_user_info_with_introspection",
        Mock(side_effect=ConnectionError_("Connection fails")),
    )
    with pytest.raises(
        TokenExchangeResourceServerIntrospectionError, match="Failed to introspect subject token"
    ):
        request_service._introspect_subject_token()


def test_request_service_introspect_subject_token_suspicious_introspection_response_audience(
    source_service, monkeypatch, settings, caplog
):
    """
    Test the request service introspect subject token method when suspicious audience raises.

    Invalid introspection response audience_id case.

    """
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    # Monkeypatch OIDC backend token introspection
    def mock_user_info(self, _):
        self.token_origin_audience = "service:source"
        return {"active": True, "client_id": "service:suspicious"}

    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection", mock_user_info
    )
    with pytest.raises(SuspiciousOperation), caplog.at_level(logging.INFO):
        request_service._introspect_subject_token()

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
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

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
        request_service._introspect_subject_token()

    assert "Introspection response has no 'sub'" in caplog.messages


def test_request_service_validate_pure_scopes_from_request(source_service):
    """
    Test the request service validate pure scopes method with scopes from the request.

    Add expected scopes in the request; expected scopes are those granted by linked services rules.

    """
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
        scope="target:read target:write",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)
    request_service._validate_pure_scopes()

    # Scopes from request scope are granted
    assert request_service.granted_scopes == {"target:read", "target:write"}
    assert set(request_service.grants) == {
        MenshenJWTGrantClaim(audience_id="service:target", scope=scope, throttle=None)
        for scope in request_service.granted_scopes
    }


@pytest.mark.parametrize(
    ("audience", "scope"),
    [
        # Extra scope
        ("service:target", "target:read target:write extra"),
        # Extra audience
        ("service:target service:other", "target:read target:write"),
    ],
)
def test_request_service_validate_pure_scopes_from_request_with_extra_scopes(
    source_service, audience, scope
):
    """Test the request service validate pure scopes method with extra scopes from the request."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience=audience,
        scope=scope,
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    with pytest.raises(
        TokenExchangeInvalidScopesError, match="You cannot request more scope than rules allow"
    ):
        request_service._validate_pure_scopes()


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
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
        scope="action:update-target",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)
    with assertNumQueries(4):
        request_service._validate_scope_action()

    # Scopes from request action are granted
    assert request_service.granted_scopes == {"target:update"}
    assert request_service.grants == [
        MenshenJWTGrantClaim(audience_id="service:target", scope="target:update", throttle=None)
    ]


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
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
        scope="action:update-target",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)
    with (
        pytest.raises(
            TokenExchangeInvalidActionError,
            match="All required source scopes are not satisfied for this action.",
        ),
        caplog.at_level(logging.INFO),
    ):
        request_service._validate_scope_action()

    # Scopes from request action are not granted
    assert not request_service.granted_scopes
    assert "Missing required source scope(s): target:update" in caplog.messages


def test_request_service_validate_scopes_from_pure_scopes(source_service, monkeypatch):
    """Test the request service validate scopes method when requested from pure scopes."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
    )

    mock_validate_scope_action = Mock()
    monkeypatch.setattr(
        TokenExchangeRequestService, "_validate_scope_action", mock_validate_scope_action
    )

    request_service = TokenExchangeRequestService(source_service.audience_id, request)
    request_service._validate_scopes()

    # We should not have used the validate scope action method
    mock_validate_scope_action.assert_not_called()

    # Scopes from user info are granted
    assert request_service.granted_scopes == {"openid", "target:read", "target:write"}
    assert set(request_service.grants) == {
        MenshenJWTGrantClaim(audience_id="service:target", scope=scope, throttle=None)
        for scope in request_service.granted_scopes
    }


def test_request_service_validate_scopes_from_scope_action(source_service, monkeypatch):
    """Test the request service validate scopes method when requested from an action."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN),
        audience="service:target",
        scope="action:write-to-target",
    )

    mock_validate_pure_scopes = Mock()
    monkeypatch.setattr(
        TokenExchangeRequestService, "_validate_pure_scopes", mock_validate_pure_scopes
    )

    request_service = TokenExchangeRequestService(source_service.audience_id, request)
    request_service._validate_scopes()

    # We should not have used the validate scope action method
    mock_validate_pure_scopes.assert_not_called()

    # Scopes from request action are granted
    assert request_service.granted_scopes == {"target:write"}
    assert request_service.grants == [
        MenshenJWTGrantClaim(audience_id="service:target", scope="target:write", throttle=None)
    ]


@pytest.mark.parametrize("token_type", [TokenTypeEnum.ACCESS_TOKEN, TokenTypeEnum.JWT])
def test_request_service_generate_exchange_token_with_type(token_type, source_service):
    """Test the request service generate exchange token method with a given token type."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    token = request_service._generate_exchange_token(
        token_type, scope="target:write", expires_in=3600
    )
    assert isinstance(token, str)
    assert len(token) >= 32


def test_request_service_generate_exchange_token_jwt_no_sub_claim(
    source_service, settings, monkeypatch
):
    """Test the request service generate exchange token method with missing sub claim."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
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
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    with pytest.raises(
        TokenExchangeIntrospectionError,
        match=r"Subject token introspection failed to provide an identity \(sub\)",
    ):
        request_service._generate_exchange_token(
            AllowedSubjectTokenTypeEnum.JWT,
            scope="target:write",
            expires_in=3600,
        )


def test_request_service_generate_exchange_token_jwt_configuration(source_service, settings):
    """Test the request service generate exchange token method with missing kid."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
    )
    settings.TOKEN_EXCHANGE_JWT_CURRENT_KID = None
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    with pytest.raises(TokenExchangeConfigurationError, match="JWT signing key is not configured."):
        request_service._generate_exchange_token(
            AllowedSubjectTokenTypeEnum.JWT,
            scope="target:write",
            expires_in=3600,
        )


def test_request_service_generate_exchange_token_unsupported_type(source_service):
    """Test the request service generate exchange token method with an unsupported token type."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    with pytest.raises(
        TokenExchangeConfigurationError, match="Configured request token type is not supported."
    ):
        request_service._generate_exchange_token(
            TokenTypeEnum.REFRESH_TOKEN,  # ty: ignore
            scope="target:write",
            expires_in=3600,
        )


def test_request_service_generate_exchange_token_jwt_invalid_token(source_service, monkeypatch):
    """Test the request service generate exchange token method generates an invalid JWT."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)

    monkeypatch.setattr(TokenGenerator, "generate_jwt", Mock(side_effect=ValueError()))

    with pytest.raises(TokenExchangeIssuingError, match="An error occurred while issuing JWT."):
        request_service._generate_exchange_token(
            AllowedSubjectTokenTypeEnum.JWT,
            scope="target:write",
            expires_in=3600,
        )


@pytest.mark.parametrize(
    "token_type", [AllowedRequestedTokenTypeEnum.ACCESS_TOKEN, AllowedRequestedTokenTypeEnum.JWT]
)
def test_request_service_generate_exchange_response(source_service, token_type):
    """Test the request service generate exchange response."""
    request = TokenExchangeRequest(
        subject_token="foo",
        subject_token_type=AllowedSubjectTokenTypeEnum.ACCESS_TOKEN,
        audience="service:target",
        scope="target:write",
        requested_token_type=token_type,
    )
    request_service = TokenExchangeRequestService(source_service.audience_id, request)
    response = request_service.generate_exchange_response()
    assert isinstance(response.access_token, str)
    assert len(response.access_token) > 32
    assert response.issued_token_type == token_type
    assert response.token_type == TokenExchangeResponseTokenType.BEARER
    assert response.expires_in == 300  # rules' default is 5 minutes
    assert response.scope == "target:write"
    assert response.refresh_token is None
    assert len(response.grants) == 1
    assert response.grants[0].scope == "target:write"
