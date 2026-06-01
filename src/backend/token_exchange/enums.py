"""Menshen: enums for the token_exchange application."""

from enum import StrEnum
from typing import Annotated

from annotated_types import Predicate
from django.conf import settings


class TokenTypeEnum(StrEnum):
    """Token type identifier for RFC 8693."""

    ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"  # noqa: S105
    REFRESH_TOKEN = "urn:ietf:params:oauth:token-type:refresh_token"  # noqa: S105
    JWT = "urn:ietf:params:oauth:token-type:jwt"
    ID_TOKEN = "urn:ietf:params:oauth:token-type:id_token"  # noqa: S105
    SAML1 = "urn:ietf:params:oauth:token-type:saml1"
    SAML2 = "urn:ietf:params:oauth:token-type:saml2"


class SupportedTokenTypeEnum(StrEnum):
    """Token type identifier that the current implementation supports."""

    ACCESS_TOKEN = TokenTypeEnum.ACCESS_TOKEN
    JWT = TokenTypeEnum.JWT


class TokenExchangeResponseTokenType(StrEnum):
    """Token exchange response token_types allowed values."""

    BEARER = "bearer"
    MAC = "mac"
    NA = "N_A"


#
# Dynamic enums depending on project settings
#
AllowedRequestedTokenTypeEnum = Annotated[
    SupportedTokenTypeEnum,
    Predicate(lambda type_: type_ in settings.TOKEN_EXCHANGE_ALLOWED_REQUESTED_TOKEN_TYPES),
]
AllowedActorTokenTypeEnum = Annotated[
    SupportedTokenTypeEnum,
    Predicate(lambda type_: type_ in settings.TOKEN_EXCHANGE_ALLOWED_ACTOR_TOKEN_TYPES),
]
AllowedSubjectTokenTypeEnum = Annotated[
    SupportedTokenTypeEnum,
    Predicate(lambda type_: type_ in settings.TOKEN_EXCHANGE_ALLOWED_SUBJECT_TOKEN_TYPES),
]
