"""Menshen client: schemas."""

import logging
import os
import re
from dataclasses import dataclass
from typing import Literal

from .enums import MenshenSupportedTokenType, TokenExchangeResponseTokenType

logger = logging.getLogger(__name__)


@dataclass
class MenshenConfiguration:
    """
    Menshen server configuration.

    Expected configuration:

        - client_id: the client identifier for the menshen-registered service
        - client_secret: the client secret for the menshen-registered service
        - server_root_url: target menshen server root URL, e.g. https://menshen.example.org
        - token_endpoint: the token exchange API endpoint path
        - introspection: the exchanged token introspection API endpoint path
        - revocation_endpoint: the exchanged token revocation API endpoint path
    """

    client_id: str
    client_secret: str
    server_root_url: str
    token_endpoint: str = "/auth/token/exchange/"  # noqa: S105
    introspection_endpoint: str = "/auth/token/introspect/"
    revocation_endpoint: str = "/auth/token/revoke/"

    def _fully_qualified_endpoint_url(self, endpoint: str) -> str:
        """
        Get fully qualified endpoint URL.

        Note that we expect return URL to have a trailing slash (to avoid redirections).
        """
        # Rebuild URL
        url = f"{self.server_root_url}/{endpoint}"
        # Remove eventually duplicated slashes (excluding scheme)
        url = re.sub(r"(?<!:)\/{2,}", r"/", url)
        # Add trailing slash if missing
        return url + os.sep if url[-1] != os.sep else url

    @property
    def token_url(self) -> str:
        """Get Menshen API token exchange url."""
        return self._fully_qualified_endpoint_url(self.token_endpoint)

    @property
    def introspection_url(self) -> str:
        """Get Menshen API token introspection url."""
        return self._fully_qualified_endpoint_url(self.introspection_endpoint)

    @property
    def revocation_url(self) -> str:
        """Get Menshen API token revocation url."""
        return self._fully_qualified_endpoint_url(self.revocation_endpoint)


@dataclass
class TokenExchangeRequest:
    """
    Token exchange request.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-request
    """

    subject_token: str
    subject_token_type: MenshenSupportedTokenType
    grant_type: Literal["urn:ietf:params:oauth:grant-type:token-exchange"] = (
        "urn:ietf:params:oauth:grant-type:token-exchange"
    )
    resource: str | None = None
    audience: str | None = None
    scope: str | None = None
    requested_token_type: MenshenSupportedTokenType | None = None
    actor_token: str | None = None
    actor_token_type: MenshenSupportedTokenType | None = None


@dataclass
class MenshenJWTGrantClaimThrottling:
    """Menshen JWT grant claim throttling."""

    rate: str | None = None


@dataclass
class MenshenJWTGrantClaim:
    """Menshen JWT grant claim."""

    audience_id: str
    scope: str
    throttle: MenshenJWTGrantClaimThrottling | None = None

    def __post_init__(self):
        """Parse nested dataclasses."""
        if self.throttle and isinstance(self.throttle, dict):
            self.throttle = MenshenJWTGrantClaimThrottling(**self.throttle)  # ty: ignore


@dataclass
class TokenExchangeResponse:
    """
    Token exchange response.

    Reference:
    https://www.rfc-editor.org/info/rfc8693/#name-response
    """

    access_token: str
    issued_token_type: MenshenSupportedTokenType
    token_type: TokenExchangeResponseTokenType
    expires_in: int
    grants: list[MenshenJWTGrantClaim]
    scope: str | None = None
    refresh_token: str | None = None

    def __post_init__(self):
        """Parse nested dataclasses."""
        if self.grants and len(self.grants) and isinstance(self.grants[0], dict):
            self.grants = [MenshenJWTGrantClaim(**grant) for grant in self.grants]  # ty: ignore


@dataclass
class IntrospectionRequest:
    """
    Introspection request.

    Reference:
    https://www.rfc-editor.org/info/rfc7662/#section-2.1
    """

    token: str
    token_type_hint: MenshenSupportedTokenType | None = None


@dataclass
class IntrospectionResponse:
    """
    Introspection response.

    Reference:
    https://www.rfc-editor.org/info/rfc7662/#section-2.2
    """

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
    token_type: MenshenSupportedTokenType | None = None

    # Optionnal
    email: str | None = None
    username: str | None = None
    jti: str | None = None


@dataclass
class RevocationRequest:
    """
    Exchanged token revocation request.

    Reference:
    https://www.rfc-editor.org/info/rfc7009/#section-2.1
    """

    token: str
    token_type_hint: MenshenSupportedTokenType | None = None
