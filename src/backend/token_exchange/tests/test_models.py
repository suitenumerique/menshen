"""Menshen: model tests for the token_exchange application."""

import logging
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from token_exchange.enums import AllowedRequestedTokenType
from token_exchange.factories import (
    ActionScopeFactory,
    ActionScopeGrantFactory,
    ExchangedTokenFactory,
    ScopeGrantFactory,
    ServiceProviderCredentialsFactory,
    TokenExchangeActionPermissionFactory,
    TokenExchangeRuleFactory,
)
from token_exchange.models import (
    ExchangedToken,
    ServiceProvider,
    TokenTypeChoices,
    validate_action_scope_name,
)
from token_exchange.structs import IntrospectionResponse


@pytest.mark.parametrize("value", ["action:foo", "action:bar"])
def test_validate_action_scope_name(value):
    """Test the validate_action_scope_name utility."""
    assert validate_action_scope_name(value) is None


@pytest.mark.parametrize(
    "value", ["action:", "foo", " action: ", " action:bar", " action:bar  ", " bar  "]
)
def test_validate_action_scope_name_with_invalid_names(value):
    """Test the validate_action_scope_name utility."""
    with pytest.raises(ValidationError, match="Action name must start with 'action:'"):
        validate_action_scope_name(value)


def test_serviceprovider_str():
    """Test the ServiceProvider str method."""
    service = ServiceProvider(name="foo", audience_id="service:foo")
    assert str(service) == "foo"


@pytest.mark.django_db
def test_serviceprovider_save():
    """Test the ServiceProvider save method."""
    service = ServiceProvider(audience_id="service:foo")
    assert service.name == ""
    assert service.audience_id == "service:foo"
    service.save()
    assert service.name == "service:foo"


def test_serviceprovidercredentials_str():
    """Test the ServiceProviderCredentials str method."""
    credentials = ServiceProviderCredentialsFactory.build()
    assert str(credentials) == f"{credentials.service_provider} [is_active:{credentials.is_active}]"


@pytest.mark.parametrize(
    "allowed_origins", [" https://foo.com http://www.bar.com  ", "https://foo.com/action"]
)
def test_serviceprovidercredentials_clean(allowed_origins):
    """Test the ServiceProviderCredentials clean method."""
    credentials = ServiceProviderCredentialsFactory.build(allowed_origins=allowed_origins)
    credentials.clean()


@pytest.mark.parametrize(
    "allowed_origins", [" foo.com http://www.bar.com  ", "ftp://foo.com/action"]
)
def test_serviceprovidercredentials_clean_bad_origins(allowed_origins):
    """Test the ServiceProviderCredentials clean method."""
    credentials = ServiceProviderCredentialsFactory.build(allowed_origins=allowed_origins)
    with pytest.raises(ValidationError):
        credentials.clean()


def test_tokenexchangerule_str():
    """Test the TokenEchangeRule str method."""
    rule = TokenExchangeRuleFactory.build()
    assert str(rule) == f"{rule.source_service} → {rule.target_service}"


def test_scopegrant_str():
    """Test the ScopeGrant str method."""
    scope_grant = ScopeGrantFactory.build()
    assert (
        str(scope_grant)
        == f"{scope_grant.source_scope} → {scope_grant.granted_scope} (rule: {scope_grant.rule.id})"
    )


def test_actionscope_str():
    """Test the ActionScope str method."""
    action_scope = ActionScopeFactory.build()
    assert str(action_scope) == action_scope.name


def test_actionscope_save():
    """Test the ActionScope save method."""
    action_scope = ActionScopeFactory.build(name="action:Foo")
    action_scope.save()
    assert action_scope.name == "action:foo"


def test_actionscopegrant_str():
    """Test the ActionScopeGrant str method."""
    grant = ActionScopeGrantFactory.build()
    assert str(grant) == f"{grant.action.name} → {grant.granted_scope} on {grant.target_service}"


def test_tokenexchangeactionpermission_str():
    """Test the TokenExchangeActionPermission str method."""
    permission = TokenExchangeActionPermissionFactory.build()
    assert str(permission) == f"{permission.action.name} in rule {permission.rule.id}"


@pytest.mark.parametrize(
    ("subject_email", "subject_sub", "identity"),
    [
        (None, None, "unknown"),
        ("jane.doe@example.org", None, "jane.doe@example.org"),
        ("jane.doe@example.org", "fbfcce3c-10e9-4225-8a5e-f8b1192bc709", "jane.doe@example.org"),
        (None, "fbfcce3c-10e9-4225-8a5e-f8b1192bc709", "fbfcce3c-10e9-4225-8a5e-f8b1192bc709"),
    ],
)
def test_exchangedtoken_str(subject_email, subject_sub, identity):
    """Test the ExchangedToken str method."""
    token = ExchangedTokenFactory.build(subject_email=subject_email, subject_sub=subject_sub)
    assert str(token) == f"{token.token_type} for {identity} (expires {token.expires_at})"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("subject_email", "subject_sub"),
    [
        ("jane.doe@example.org", ""),
        ("jane.doe@example.org", "fbfcce3c-10e9-4225-8a5e-f8b1192bc709"),
        ("", "fbfcce3c-10e9-4225-8a5e-f8b1192bc709"),
    ],
)
def test_exchangedtoken_save(settings, caplog, subject_sub, subject_email):
    """Test the ExchangedToken save method."""
    settings.TOKEN_EXCHANGE_MAX_ACTIVE_TOKENS_PER_USER = None
    ExchangedTokenFactory.create_batch(4, subject_sub=subject_sub, subject_email=subject_email)
    token = ExchangedTokenFactory.build(subject_sub=subject_sub, subject_email=subject_email)
    token.save()  # No restriction applies until then

    # we have 5 stored tokens for sub
    assert (
        ExchangedToken.objects.filter(subject_sub=subject_sub, subject_email=subject_email).count()
        == 5
    )

    # Restrict to at least 4 tokens per user
    settings.TOKEN_EXCHANGE_MAX_ACTIVE_TOKENS_PER_USER = 4
    future_oldest = ExchangedToken.objects.filter(
        subject_sub=subject_sub, subject_email=subject_email
    ).order_by("created_at")[2]

    token = ExchangedTokenFactory.build(subject_sub=subject_sub, subject_email=subject_email)
    with caplog.at_level(logging.INFO):
        token.save()  # Clean oldest tokens

    # We have 4 token for the user
    qs = ExchangedToken.objects.filter(
        subject_sub=subject_sub, subject_email=subject_email
    ).order_by("created_at")
    assert qs.count() == 4
    assert qs.first() == future_oldest
    assert qs.last() == token
    assert (
        f"Enforced token limit for sub={subject_sub}/email={subject_email}: deleted 2 oldest tokens"
        in caplog.messages
    )


@pytest.mark.django_db
def test_exchangedtoken_save_no_tokens_restriction_without_email_or_sub(settings):
    """Test the ExchangedToken save method when no restriction applies without sub or email."""
    settings.TOKEN_EXCHANGE_MAX_ACTIVE_TOKENS_PER_USER = None
    ExchangedTokenFactory.create_batch(4, subject_sub="", subject_email="")
    token = ExchangedTokenFactory.build(subject_sub="", subject_email="")
    token.save()  # No restriction applies until then

    # we have 5 stored tokens for sub
    assert ExchangedToken.objects.filter().count() == 5

    # Restrict to at least 5 tokens per user
    settings.TOKEN_EXCHANGE_MAX_ACTIVE_TOKENS_PER_USER = 4
    token = ExchangedTokenFactory.build(subject_sub="", subject_email="")
    token.save()

    # we have 6 token
    qs = ExchangedToken.objects.filter(subject_sub="", subject_email="").order_by("created_at")
    assert qs.count() == 6
    assert qs.last() == token


def test_exchangedtoken_is_expired():
    """Test the ExchangedToken is_expired method."""
    token = ExchangedTokenFactory.create()
    assert not token.is_expired()
    token.expires_at = timezone.now() - timedelta(hours=1)
    assert token.is_expired()


def test_exchangedtoken_is_revoked():
    """Test the ExchangedToken is_revoked method."""
    token = ExchangedTokenFactory.create(revoked_at=None)
    assert not token.is_revoked()
    token.revoked_at = timezone.now() - timedelta(hours=1)
    assert token.is_revoked()


def test_exchangedtoken_is_valid():
    """Test the ExchangedToken is_valid method."""
    token = ExchangedTokenFactory.create(
        revoked_at=None, expires_at=timezone.now() + timedelta(days=1)
    )
    assert token.is_valid()
    token.revoked_at = timezone.now()
    assert not token.is_valid()
    token.revoked_at = None
    assert token.is_valid()
    token.expires_at = timezone.now() - timedelta(days=1)
    assert not token.is_valid()


def test_exchangedtoken_revoke():
    """Test the ExchangedToken revoke method."""
    token = ExchangedTokenFactory.create(revoked_at=None)
    updated_at = token.updated_at

    assert token.revoked_at is None
    assert not token.is_revoked()

    token.revoke()
    assert token.revoked_at
    assert token.is_revoked()
    assert token.updated_at > updated_at

    # If already revoked, the save method should not be called
    revoked_at = token.revoked_at
    updated_at = token.updated_at
    token.save = MagicMock()
    token.revoke()
    token.save.assert_not_called()
    assert token.is_revoked()
    assert token.revoked_at == revoked_at
    assert token.updated_at == updated_at


@pytest.mark.parametrize(
    ("expires_at", "revoked_at"),
    [
        (timezone.now() - timedelta(days=1), None),
        (timezone.now() + timedelta(days=1), timezone.now()),
        (timezone.now() - timedelta(days=1), timezone.now()),
    ],
)
def test_exchangedtoken_to_introspection_response_invalid_token(expires_at, revoked_at):
    """Test the ExchangedToken to_introspection_response method with an invalid token."""
    token = ExchangedTokenFactory.create(expires_at=expires_at, revoked_at=revoked_at)
    assert token.to_introspection_response() == IntrospectionResponse(active=False)


def test_exchangedtoken_to_introspection_response(settings):
    """Test the ExchangedToken to_introspection_response method."""
    token = ExchangedTokenFactory.create(token_type=AllowedRequestedTokenType.ACCESS_TOKEN)
    assert token.to_introspection_response() == IntrospectionResponse(
        active=True,
        scope=token.scope,
        username=token.subject_email or token.subject_sub,
        token_type=AllowedRequestedTokenType.ACCESS_TOKEN,
        exp=int(token.expires_at.timestamp()),
        iat=int(token.created_at.timestamp()),
        sub=token.subject_sub,
        email=token.subject_email,
        aud=token.audiences,
        jti=token.token[:50],
        client_id=settings.OIDC_RS_CLIENT_ID,
    )


@pytest.mark.parametrize("token_type", [TokenTypeChoices.ACCESS_TOKEN, TokenTypeChoices.JWT])
def test_exchangedtoken_get_jti(token_type):
    """Test the ExchangedToken get_jti private method."""
    token = ExchangedTokenFactory.create(token_type=token_type)
    expected = token.token[:50]
    if token_type == TokenTypeChoices.JWT:
        expected = token.subject_token_jti
    assert token._get_jti() == expected
