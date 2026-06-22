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


def str_to_list(value: str) -> list[str]:
    """Split input string with space separated items to a deduplicated list of items."""
    out = []
    for item in value.split():
        if not item.strip() or item in out:
            continue
        out.append(item)
    return out


class MenshenStructMixin:
    """Menshen's mixin that extends msgspect Struct class."""

    def to_dict(self) -> dict:
        """Convert Struct to a standard dict."""
        return msgspec.to_builtins(self)


class TokenExchangeJWTMayActClaim(msgspec.Struct, MenshenStructMixin):
    """
    JWT may_act claim.

    The may_act claim makes a statement that one party is authorized to become the actor
    and act on behalf of another party.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-may_act-authorized-actor-cl
    """

    sub: str


class TokenExchangeJWTActClaim(msgspec.Struct, MenshenStructMixin):
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
    msgspec.Struct,
    MenshenStructMixin,
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


class MenshenJWTGrantClaimThrottling(
    msgspec.Struct, MenshenStructMixin, forbid_unknown_fields=True
):
    """Menshen JWT grant claim throttling."""

    rate: str | None = None


class MenshenJWTGrantClaim(
    msgspec.Struct, MenshenStructMixin, forbid_unknown_fields=True, frozen=True
):
    """Menshen JWT grant claim."""

    audience_id: str
    scope: str
    throttle: MenshenJWTGrantClaimThrottling | None = None


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
    grants: list[MenshenJWTGrantClaim] | None = None

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


class IntrospectionResponse(
    msgspec.Struct,
    MenshenStructMixin,
    omit_defaults=True,
    dict=True,
):
    """Introspection response."""

    # Required
    active: bool

    # Recommended
    sub: str | None = None
    client_id: str | None = None
    scope: str | None = None
    exp: int | None = None
    iat: int | None = None
    iss: str | None = None
    aud: str | None = None
    token_type: TokenTypeEnum | None = None

    # Optionnal
    email: str | None = None
    username: str | None = None
    jti: str | None = None

    @property
    def scopes(self) -> list[str]:
        """Access to scopes as a list of strings."""
        return str_to_list(self.scope) if self.scope else []

    @property
    def audiences(self) -> list[str]:
        """Access to audiences as a list of strings."""
        return str_to_list(self.aud) if self.aud else []


class TokenExchangeRequest(
    msgspec.Struct,
    MenshenStructMixin,
    forbid_unknown_fields=True,
    dict=True,
):
    """
    Token exchange request.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-request
    """

    subject_token: Annotated[str, msgspec.Meta(min_length=1)]
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
        """Access to audiences as a deduplicated list of strings."""
        return str_to_list(self.audience) if self.audience else []

    @property
    def scopes(self) -> list[str]:
        """Access to scopes as deduplicated a list of strings."""
        return str_to_list(self.scope) if self.scope else []

    @property
    def _actions(self) -> list[str]:
        """Extract action(s) from request scope."""
        return [scope for scope in self.scopes if scope.startswith("action:")]

    @property
    def action(self) -> str | None:
        """
        Extract action from scope.

        Note that there must be at least a single action per request.

        Returns:
            str: the action
            None: no action has been defined in the scope request

        """
        if not len(self._actions):
            return None
        return self._actions[0]

    def _validate_actions(self) -> None:
        """Validate actions defined in the scope field."""
        if not self.scopes:
            return

        actions_count = len(self._actions)
        if actions_count > 1:
            raise msgspec.ValidationError(
                "Only one action scope is allowed per token exchange request"
            )

        has_action = actions_count > 0
        if has_action and len(self.scopes) > 1:
            raise msgspec.ValidationError("Actions cannot be combined with other scopes")

    def _validate_actor_token_requirements(self):
        """When an actor token is provided, an actor token type should be defined."""
        if self.actor_token and not self.actor_token_type:
            raise msgspec.ValidationError(
                "An actor_token_type is required when actor_token is provided"
            )
        if self.actor_token_type and not self.actor_token:
            raise msgspec.ValidationError(
                "An actor_token is required when actor_token_type is provided"
            )

    def __post_init__(self):
        """Perform post initialization validation."""
        self._validate_actions()
        self._validate_actor_token_requirements()


class TokenExchangeResponse(
    msgspec.Struct,
    MenshenStructMixin,
    omit_defaults=True,
    forbid_unknown_fields=True,
    kw_only=True,
):
    """
    Token exchange response.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-response
    """

    access_token: str
    issued_token_type: AllowedRequestedTokenTypeEnum
    token_type: TokenExchangeResponseTokenType
    expires_in: Annotated[int, msgspec.Meta(le=settings.TOKEN_EXCHANGE_MAX_EXPIRES_IN)] = (
        settings.TOKEN_EXCHANGE_DEFAULT_EXPIRES_IN
    )
    scope: str | None = None
    refresh_token: str | None = None


class MenshenTokenExchangeResponse(TokenExchangeResponse):
    """Menshen token exchange custom response."""

    grants: list[MenshenJWTGrantClaim]


class TokenRevocationRequest(msgspec.Struct, MenshenStructMixin, forbid_unknown_fields=True):
    """
    Exchanged token revocation request.

    Reference:
    https://www.rfc-editor.org/info/rfc7009/#section-2.1
    """

    # When striped the token should be at least 32 characters long (opaque token)
    token: Annotated[str, msgspec.Meta(pattern=r"^\s*\S{32,}\s*$")]
    token_type_hint: AllowedRequestedTokenTypeEnum | None = None
