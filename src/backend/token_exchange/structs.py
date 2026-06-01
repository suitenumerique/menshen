"""Menshen: structures for the token_exchange application."""

from __future__ import annotations

from functools import cache
from typing import Annotated, Literal, cast
from uuid import UUID, uuid4

import msgspec
from django.conf import settings
from django.utils import timezone
from joserfc.jwt import ClaimsOption, JWTClaimsRegistry

from .enums import (
    AllowedActorTokenTypeEnum,
    AllowedRequestedTokenTypeEnum,
    AllowedSubjectTokenTypeEnum,
    TokenExchangeResponseTokenType,
    TokenTypeEnum,
)


class BaseStruct(msgspec.Struct):
    """Base Struct class for Menshen."""

    def to_dict(self) -> dict:
        """Convert Struct to a standard dict."""
        return msgspec.to_builtins(self)


class TokenExchangeJWTMayActClaim(BaseStruct):
    """
    JWT may_act claim.

    The may_act claim makes a statement that one party is authorized to become the actor
    and act on behalf of another party.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-may_act-authorized-actor-cl
    """

    sub: str


class TokenExchangeJWTActClaim(BaseStruct):
    """
    JWT act claim.

    The act (actor) claim provides a means within a JWT to express that delegation has
    occurred and identify the acting party to whom authority has been delegated.

    A chain of delegation can be expressed by nesting one act claim within another.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-act-actor-claim
    """

    sub: str
    act: TokenExchangeJWTActClaim | None = None


class TokenExchangeJWTClaims(
    BaseStruct,
    omit_defaults=True,
    forbid_unknown_fields=True,
):
    """
    Token Exchange JWT claims.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-json-web-token-claims-and-i
    """

    act: TokenExchangeJWTActClaim | None = None
    scope: str | list[str] | None = None
    client_id: str | None = None
    may_act: TokenExchangeJWTMayActClaim | None = None


class MenshenJWTClaims(
    TokenExchangeJWTClaims,
    omit_defaults=True,
    forbid_unknown_fields=True,
    kw_only=True,
):
    """
    Menshen JWT claims.

    Inherits from standard JWT claims and Token Exchange claims.
    """

    sub: str
    aud: list[str]
    exp: int
    iat: int = msgspec.field(default_factory=lambda: int(timezone.now().timestamp()))
    jti: UUID = msgspec.field(default_factory=uuid4)

    email: str | None = None
    grants: list[dict] | None = None

    @classmethod
    @cache
    def to_jwt_claims_registry(cls) -> JWTClaimsRegistry:
        """Convert claims to the joserfc's JWTClaimsRegistry spec."""
        options = {}
        for field in cast(msgspec.inspect.StructType, msgspec.inspect.type_info(cls)).fields:
            claims = {
                "essential": field.required
                or (
                    # Having a default factory with no default means
                    # that this field is essentiel
                    field.default == msgspec.NODEFAULT and field.default_factory != msgspec.UNSET
                ),
            }
            if field.default != msgspec.NODEFAULT:
                claims["value"] = field.default
            options[field.name] = ClaimsOption(**claims)
        return JWTClaimsRegistry(now=None, leeway=0, **options)


class IntrospectionResponse(BaseStruct, omit_defaults=True):
    """Introspection response."""

    active: bool
    scope: str | None = None
    username: str | None = None
    token_type: TokenTypeEnum | None = None
    exp: int | None = None
    iat: int | None = None
    sub: str | None = None
    email: str | None = None
    aud: list[str] | None = None
    jti: str | None = None
    client_id: str | None = None


def str_to_list(value: str) -> list[str]:
    """Split input string with space separated items to a list of items."""
    return [item.strip() for item in value.split() if item.strip()]


class TokenExchangeRequest(
    BaseStruct,
    forbid_unknown_fields=True,
    dict=True,
):
    """
    Token exchange request.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-request
    """

    subject_token: str
    subject_token_type: AllowedSubjectTokenTypeEnum
    grant_type: Literal["urn:ietf:params:oauth:grant-type:token-exchange"] = (
        "urn:ietf:params:oauth:grant-type:token-exchange"
    )
    resource: str | None = None
    audience: str | None = None
    scope: str | None = None
    requested_token_type: AllowedRequestedTokenTypeEnum | None = None
    actor_token: str | None = None
    actor_token_type: AllowedActorTokenTypeEnum | None = None

    @property
    def audiences(self) -> list[str]:
        """Access to audiences as a list of strings."""
        return str_to_list(self.audience) if self.audience else []

    @property
    def scopes(self) -> list[str]:
        """Access to scopes as a list of strings."""
        return str_to_list(self.scope) if self.scope else []

    def _validate_scopes(self) -> None:
        """Validate scopes."""
        if not self.scopes:
            return

        actions_count = len(list(filter(lambda scope: scope.startswith("action:"), self.scopes)))
        if actions_count > 1:
            raise msgspec.ValidationError(
                "Only one action scope is allowed per token exchange request"
            )

        has_action = actions_count > 0
        if has_action and len(self.scopes) > 1:
            raise msgspec.ValidationError("Actions cannot be combined with other scopes")

    def _validate_actor_token_requirements(self):
        """When an actor token is provided, an actor token type should be defined."""
        if self.actor_token and self.actor_token_type is None:
            raise msgspec.ValidationError(
                "An actor_token_type is required when actor_token is provided"
            )
        if self.actor_token_type and self.actor_token is None:
            raise msgspec.ValidationError(
                "An actor_token is required when actor_token_type is provided"
            )

    def __post_init__(self):
        """Perform post initialization validation."""
        self._validate_scopes()
        self._validate_actor_token_requirements()


class TokenExchangeResponse(BaseStruct, forbid_unknown_fields=True):
    """
    Token exchange response.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-response
    """

    access_token: str
    issued_token_type: AllowedRequestedTokenTypeEnum
    token_type: TokenExchangeResponseTokenType
    expires_in: Annotated[int, msgspec.Meta(le=settings.TOKEN_EXCHANGE_MAX_EXPIRES_IN)] | None = (
        None
    )
    scope: str | None = None
    refresh_token: str | None = None


class TokenRevocationRequest(BaseStruct, forbid_unknown_fields=True):
    """
    Exchanged token revocation request.

    Reference:
    https://www.rfc-editor.org/info/rfc7009/#section-2.1
    """

    # When striped the token should be at least 32 characters long (opaque token)
    token: Annotated[str, msgspec.Meta(pattern=r"^\s*\S{32,}\s*$")]
    token_type_hint: AllowedRequestedTokenTypeEnum | None = None
