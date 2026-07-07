"""Menshen client: enums."""

from enum import StrEnum


class MenshenSupportedTokenType(StrEnum):
    """
    Token type identifier for RFC 8693.

    Note that the current list is restricted to the ones that Menshen supports.
    """

    ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"  # noqa: S105
    JWT = "urn:ietf:params:oauth:token-type:jwt"


class TokenExchangeResponseTokenType(StrEnum):
    """Token exchange response token_types allowed values."""

    BEARER = "bearer"
    MAC = "mac"
    NA = "N_A"
