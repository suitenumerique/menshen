"""Menshen: factories for the token_exchange application."""

from datetime import UTC

import factory.fuzzy
from django.conf import settings
from faker import Faker

from token_exchange.enums import AllowedRequestedTokenTypeEnum
from token_exchange.services.token import TokenGenerator
from token_exchange.structs import MenshenJWTGrantClaim

from . import models

fake = Faker()


class ExchangedTokenFactory(factory.django.DjangoModelFactory):
    """A factory to create ExchangedToken instances for testing."""

    class Meta:  # noqa: D106
        model = models.ExchangedToken

    token = factory.LazyFunction(fake.uuid4)
    token_type = factory.fuzzy.FuzzyChoice(models.TokenTypeChoices.values)
    jwt_kid = ""
    subject_sub = factory.LazyFunction(fake.uuid4)
    subject_email = factory.LazyFunction(fake.email)
    audiences = factory.LazyFunction(lambda: [fake.domain_word() for _ in range(3)])
    scope = "openid email profile"
    grants = None
    expires_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="+1d", end_date="+30d", tzinfo=UTC)
    )
    subject_token_jti = factory.LazyFunction(fake.uuid4)
    subject_token_scope = "openid email profile"  # noqa: S105


class ExpiredExchangedTokenFactory(ExchangedTokenFactory):
    """A factory to create expired ExchangedToken instances for testing."""

    expires_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="-1d", tzinfo=UTC)
    )


class JWTExchangedTokenFactory(ExchangedTokenFactory):
    """A factory to create JWT ExchangedToken instances for testing."""

    token = factory.LazyFunction(
        lambda: TokenGenerator.generate_jwt(
            sub="ef7d37b4-080c-4df7-b0f8-3560dc7138aa",
            email="jane.doe@example.org",
            audiences=["service:target"],
            scope="openid target:read target:write",
            expires_in=3600,
            kid=settings.TOKEN_EXCHANGE_JWT_CURRENT_KID,
            grants=[
                MenshenJWTGrantClaim(
                    audience_id="service:target",
                    scope="target:read",
                    throttle=None,
                ),
                MenshenJWTGrantClaim(
                    audience_id="service:target",
                    scope="target:write",
                    throttle=None,
                ),
            ],
        )
    )
    token_type = AllowedRequestedTokenTypeEnum.JWT
    subject_sub = "ef7d37b4-080c-4df7-b0f8-3560dc7138aa"
    subject_email = "jane.doe@example.org"
    audiences = ["service:target"]


class ServiceProviderFactory(factory.django.DjangoModelFactory):
    """Create a ServiceProvider that will query token exchange endpoint."""

    class Meta:  # noqa: D106
        model = models.ServiceProvider

    name = factory.LazyFunction(fake.uuid4)
    audience_id = factory.LazyFunction(fake.domain_word)


class ServiceProviderCredentialsFactory(factory.django.DjangoModelFactory):
    """Allow a ServiceProvider to authenticate against the token exchange endpoint."""

    class Meta:  # noqa: D106
        model = models.ServiceProviderCredentials

    service_provider = factory.SubFactory("token_exchange.factories.ServiceProviderFactory")
    client_id = factory.LazyFunction(fake.uuid4)
    client_secret = factory.LazyFunction(fake.uuid4)


class TokenExchangeRuleFactory(factory.django.DjangoModelFactory):
    """Factory for creating TokenExchangeRule instances."""

    class Meta:  # noqa: D106
        model = models.TokenExchangeRule

    source_service = factory.SubFactory("token_exchange.factories.ServiceProviderFactory")
    target_service = factory.SubFactory("token_exchange.factories.ServiceProviderFactory")
    is_active = True


class ScopeGrantFactory(factory.django.DjangoModelFactory):
    """Factory for creating ScopeGrant instances."""

    class Meta:  # noqa: D106
        model = models.ScopeGrant

    rule = factory.SubFactory(TokenExchangeRuleFactory)
    source_scope = factory.LazyFunction(fake.word)
    granted_scope = factory.LazyFunction(fake.word)
    throttle_rate = ""


class ActionScopeFactory(factory.django.DjangoModelFactory):
    """Factory for creating ActionScope instances."""

    class Meta:  # noqa: D106
        model = models.ActionScope

    name = factory.Sequence(lambda n: f"action_{n}")
    description = factory.LazyFunction(fake.sentence)


class ActionScopeGrantFactory(factory.django.DjangoModelFactory):
    """Factory for creating ActionScopeGrant instances."""

    class Meta:  # noqa: D106
        model = models.ActionScopeGrant

    action = factory.SubFactory(ActionScopeFactory)
    target_service = factory.SubFactory("token_exchange.factories.ServiceProviderFactory")
    granted_scope = factory.LazyFunction(fake.word)
    throttle_rate = ""


class TokenExchangeActionPermissionFactory(factory.django.DjangoModelFactory):
    """Factory for creating TokenExchangeActionPermission instances."""

    class Meta:  # noqa: D106
        model = models.TokenExchangeActionPermission

    rule = factory.SubFactory(TokenExchangeRuleFactory)
    action = factory.SubFactory(ActionScopeFactory)
    required_source_scope = ""
