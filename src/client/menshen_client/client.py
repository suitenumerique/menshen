"""Menshen client: synchronous client."""

import logging
from dataclasses import asdict
from typing import cast

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import JSONDecodeError

from .exceptions import ResponseParsingError
from .schemas import (
    IntrospectionRequest,
    IntrospectionResponse,
    MenshenConfiguration,
    RevocationRequest,
    TokenExchangeRequest,
    TokenExchangeResponse,
)

logger = logging.getLogger(__name__)


class MenshenClient:
    """Menshen API client."""

    def __init__(self, config: MenshenConfiguration) -> None:
        """Instantiate the API client."""
        self.config = config
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.config.client_id, self.config.client_secret)

    def _post(
        self,
        url: str,
        request: TokenExchangeRequest | IntrospectionRequest | RevocationRequest,
        response_klass: type[TokenExchangeResponse | IntrospectionResponse] | None = None,
        error_message: str | None = None,
    ) -> TokenExchangeResponse | IntrospectionResponse | None:
        """Perform POST request for an API endpoint."""
        logger.debug("Will request %s endpoint with: %s", url, request)
        api_response = self.session.post(url, data=asdict(request))
        api_response.raise_for_status()

        if response_klass is None:
            return None

        try:
            response = response_klass(**api_response.json())
        except (TypeError, JSONDecodeError) as err:
            logger.error("%s: %s", error_message, err)
            raise ResponseParsingError(error_message) from err

        logger.debug("Successfull response: %s", response)
        return response

    def exchange(self, request: TokenExchangeRequest) -> TokenExchangeResponse:
        """Request an exchange token."""
        return cast(
            TokenExchangeResponse,
            self._post(
                self.config.token_url,
                request,
                TokenExchangeResponse,
                "Invalid token exchange response",
            ),
        )

    def introspect(self, request: IntrospectionRequest) -> IntrospectionResponse:
        """Introspect exchanged token."""
        return cast(
            IntrospectionResponse,
            self._post(
                self.config.introspection_url,
                request,
                IntrospectionResponse,
                "Invalid introspection response",
            ),
        )

    def revoke(self, request: RevocationRequest) -> None:
        """Revoke exchanged token."""
        self._post(self.config.revocation_url, request)
