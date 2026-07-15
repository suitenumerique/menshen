"""Menshen: structures for the token_exchange application."""

from __future__ import annotations

from functools import cache
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from django.conf import settings
from django.utils import timezone
from joserfc.jwt import ClaimsOption, JWTClaimsRegistry
from ninja import Field, Schema
from pydantic import ConfigDict, PlainSerializer, field_validator, model_validator
from pydantic_core import PydanticUndefined

from .enums import (
    AllowedActorTokenType,
    AllowedRequestedTokenType,
    AllowedSubjectTokenType,
    TokenExchangeResponseTokenType,
    TokenExchangeTokenTypeHint,
    TokenType,
)


def str_to_list(value: str) -> list[str]:
    """Split input string with space separated items to a deduplicated list of items."""
    out = []
    for item in value.split():
        if not item.strip() or item in out:
            continue
        out.append(item)
    return out


class TokenExchangeJWTMayActClaim(Schema):
    """
    JWT may_act claim.

    The may_act claim makes a statement that one party is authorized to become the actor
    and act on behalf of another party.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-may_act-authorized-actor-cl
    """

    sub: str


class TokenExchangeJWTActClaim(Schema):
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


class TokenExchangeJWTClaims(Schema):
    """
    Token Exchange JWT claims.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-json-web-token-claims-and-i
    """

    act: TokenExchangeJWTActClaim | None = None
    scope: str | list[str] | None = None
    client_id: str | None = None
    may_act: TokenExchangeJWTMayActClaim | None = None


class MenshenJWTGrantClaimThrottling(Schema):
    """Menshen JWT grant claim throttling."""

    rate: str | None = None


class MenshenJWTGrantClaim(Schema):
    """Menshen JWT grant claim."""

    audience_id: str
    scope: str
    throttle: MenshenJWTGrantClaimThrottling | None = None

    model_config = ConfigDict(frozen=True)


# Define a UUID serializer to maximize compatibility with various libraries that JSON encode
# dictionnaries and are not able to deal with UUIDs.
UUIDStr = Annotated[UUID, PlainSerializer(str, return_type=str)]


class MenshenJWTClaims(TokenExchangeJWTClaims):
    """
    Menshen JWT claims.

    Inherits from standard JWT claims and Token Exchange claims.
    """

    sub: UUIDStr | str
    aud: list[str]
    exp: int
    iat: int = Field(default_factory=lambda: int(timezone.now().timestamp()))
    jti: UUIDStr = Field(default_factory=uuid4)

    email: str | None = None
    grants: list[MenshenJWTGrantClaim] | None = None

    @classmethod
    @cache
    def to_jwt_claims_registry(cls) -> JWTClaimsRegistry:
        """Convert claims to the joserfc's JWTClaimsRegistry spec."""
        options = {}
        for name, field in cls.model_fields.items():
            claims = {
                "essential": field.is_required()
                or (
                    # Having a default factory with no default means
                    # that this field is essentiel
                    field.default_factory != PydanticUndefined
                    and field.default == PydanticUndefined
                ),
            }
            if field.default != PydanticUndefined:
                claims["value"] = field.default
            options[name] = ClaimsOption(**claims)
        return JWTClaimsRegistry(now=None, leeway=0, **options)


class IntrospectionResponse(Schema):
    """
    Introspection response.

    Reference:
    https://www.rfc-editor.org/info/rfc7662/#section-2.2
    """

    # Required
    active: bool

    # Recommended
    sub: UUID | str | None = None
    client_id: str | None = None
    scope: str | None = None
    exp: int | None = None
    iat: int | None = None
    iss: str | None = None
    aud: str | None = None
    token_type: TokenType | None = None

    # Optionnal
    email: str | None = None
    username: str | None = None
    jti: UUID | str | None = None

    @property
    def scopes(self) -> list[str]:
        """Access to scopes as a list of strings."""
        return str_to_list(self.scope) if self.scope else []

    @property
    def audiences(self) -> list[str]:
        """Access to audiences as a list of strings."""
        return str_to_list(self.aud) if self.aud else []

    @field_validator("aud", mode="before")
    @classmethod
    def list_str_to_str(cls, value):
        """Convert list of strings to strings."""
        if not isinstance(value, list):
            return value
        if not all(isinstance(aud, str) for aud in value):
            return value
        return " ".join(value)

    model_config = ConfigDict(frozen=True)


class TokenExchangeRequest(Schema):
    """
    Token exchange request.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-request
    """

    subject_token: str = Field(min_length=1)
    subject_token_type: AllowedSubjectTokenType
    grant_type: Literal["urn:ietf:params:oauth:grant-type:token-exchange"]
    resource: str | None = None
    audience: str | None = None
    scope: str | None = None
    requested_token_type: AllowedRequestedTokenType | None = None
    actor_token: str | None = None
    actor_token_type: AllowedActorTokenType | None = None

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

    @model_validator(mode="after")
    def validate_actions(self) -> Self:
        """Validate actions defined in the scope field."""
        if not self.scopes:
            return self

        actions_count = len(self._actions)
        if actions_count > 1:
            raise ValueError("Only one action scope is allowed per token exchange request")

        has_action = actions_count > 0
        if has_action and len(self.scopes) > 1:
            raise ValueError("Actions cannot be combined with other scopes")
        return self

    @model_validator(mode="after")
    def validate_actor_token_requirements(self) -> Self:
        """When an actor token is provided, an actor token type should be defined."""
        if self.actor_token and not self.actor_token_type:
            raise ValueError("An actor_token_type is required when actor_token is provided")
        if self.actor_token_type and not self.actor_token:
            raise ValueError("An actor_token is required when actor_token_type is provided")
        return self


class TokenExchangeResponse(Schema):
    """
    Token exchange response.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-response
    """

    access_token: str
    issued_token_type: AllowedRequestedTokenType
    token_type: TokenExchangeResponseTokenType
    expires_in: int = Field(
        default=settings.TOKEN_EXCHANGE_DEFAULT_EXPIRES_IN,
        le=settings.TOKEN_EXCHANGE_MAX_EXPIRES_IN,
    )
    scope: str | None = None
    refresh_token: str | None = None


class MenshenTokenExchangeResponse(TokenExchangeResponse):
    """Menshen token exchange custom response."""

    grants: list[MenshenJWTGrantClaim]


class BaseTokenRequest(Schema):
    """Base token request."""

    # When striped the token should be at least 32 characters long (opaque token)
    token: str = Field(pattern=r"^\s*\S{32,}\s*$")
    token_type_hint: TokenExchangeTokenTypeHint | None = None

    @field_validator("token_type_hint", mode="before")
    @classmethod
    def reset_to_none(cls, value):
        """Ignore unsupported token type hint (reset to None)."""
        if value in TokenExchangeTokenTypeHint:
            return value
        return None


class IntrospectionRequest(BaseTokenRequest):
    """
    Exchanged token introspection request.

    Reference:
    https://www.rfc-editor.org/info/rfc7662/#section-2.1
    """


class RevocationRequest(BaseTokenRequest):
    """
    Exchanged token revocation request.

    Reference:
    https://www.rfc-editor.org/info/rfc7009/#section-2.1
    """
