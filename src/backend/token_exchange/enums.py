"""Menshen: enums for the token_exchange application."""

from enum import StrEnum

from django.conf import settings


class TokenTypeEnum(StrEnum):
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


#
# Dynamic enums depending on project settings
#
AllowedRequestedTokenTypeEnum = StrEnum(
    "AllowedRequestedTokenTypeEnum",
    {
        TokenTypeEnum(type_).name: TokenTypeEnum(type_).value
        for type_ in settings.TOKEN_EXCHANGE_ALLOWED_REQUESTED_TOKEN_TYPES
    },
)
AllowedActorTokenTypeEnum = StrEnum(
    "AllowedActorTokenTypeEnum",
    {
        TokenTypeEnum(type_).name: TokenTypeEnum(type_).value
        for type_ in settings.TOKEN_EXCHANGE_ALLOWED_ACTOR_TOKEN_TYPES
    },
)
AllowedSubjectTokenTypeEnum = StrEnum(
    "AllowedSubjectTokenTypeEnum",
    {
        TokenTypeEnum(type_).name: TokenTypeEnum(type_).value
        for type_ in settings.TOKEN_EXCHANGE_ALLOWED_SUBJECT_TOKEN_TYPES
    },
)
