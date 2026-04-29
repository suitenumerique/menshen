"""Menshen: enums for the token_exchange application."""

from enum import StrEnum


class TokenTypeEnum(StrEnum):
    """Token type choices for RFC 8693."""

    ACCESS_TOKEN = "access_token"  # noqa: S105
    JWT = "jwt"
