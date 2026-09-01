"""Menshen: enums for the token_exchange application."""

from enum import StrEnum

from django.conf import settings


class TokenType(StrEnum):
    """Token type identifier for RFC 8693."""

    ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"  # noqa: S105
    REFRESH_TOKEN = "urn:ietf:params:oauth:token-type:refresh_token"  # noqa: S105
    JWT = "urn:ietf:params:oauth:token-type:jwt"
    ID_TOKEN = "urn:ietf:params:oauth:token-type:id_token"  # noqa: S105
    SAML1 = "urn:ietf:params:oauth:token-type:saml1"
    SAML2 = "urn:ietf:params:oauth:token-type:saml2"


class TokenExchangeResponseTokenType(StrEnum):
    """Token exchange response token_types allowed values."""

    BEARER = "bearer"
    MAC = "mac"
    NA = "N_A"


class TokenExchangeTokenTypeHint(StrEnum):
    """Token type hint used for token introspection (RFC 7662) and revocation (RFC 7009)."""

    ACCESS_TOKEN = "access_token"  # noqa: S105
    REFRESH_TOKEN = "refresh_token"  # noqa: S105

    # Extension
    JWT = "jwt"


class IntrospectionResponseTokenType(StrEnum):
    """
    Introspected token type.

    When introspecting a token it may be a subject or exchanged token. In the first case,
    it may be a bearer or mac token, while in the second case, it may be one of the supported
    exchanged token types.
    """

    # Subject token
    BEARER = "bearer"
    MAC = "mac"

    # Exchanged token
    ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"  # noqa: S105
    REFRESH_TOKEN = "urn:ietf:params:oauth:token-type:refresh_token"  # noqa: S105
    JWT = "urn:ietf:params:oauth:token-type:jwt"
    ID_TOKEN = "urn:ietf:params:oauth:token-type:id_token"  # noqa: S105
    SAML1 = "urn:ietf:params:oauth:token-type:saml1"
    SAML2 = "urn:ietf:params:oauth:token-type:saml2"


#
# Dynamic enums depending on project settings
#
AllowedRequestedTokenType = StrEnum(
    "AllowedRequestedTokenType",
    {
        TokenType(type_).name: TokenType(type_).value
        for type_ in settings.TOKEN_EXCHANGE_ALLOWED_REQUESTED_TOKEN_TYPES
    },
)
AllowedActorTokenType = StrEnum(
    "AllowedActorTokenType",
    {
        TokenType(type_).name: TokenType(type_).value
        for type_ in settings.TOKEN_EXCHANGE_ALLOWED_ACTOR_TOKEN_TYPES
    },
)
AllowedSubjectTokenType = StrEnum(
    "AllowedSubjectTokenType",
    {
        TokenType(type_).name: TokenType(type_).value
        for type_ in settings.TOKEN_EXCHANGE_ALLOWED_SUBJECT_TOKEN_TYPES
    },
)
