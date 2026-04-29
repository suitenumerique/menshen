"""Menshen: structures for the token_exchange application."""

from __future__ import annotations

from functools import cache
from typing import cast
from uuid import UUID, uuid4

import msgspec
from django.utils import timezone
from joserfc.jwt import ClaimsOption, JWTClaimsRegistry

from .enums import TokenTypeEnum


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
    """Introspection response object."""

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
