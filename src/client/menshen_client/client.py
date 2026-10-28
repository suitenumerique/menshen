"""Menshen client: synchronous client."""

import logging
from dataclasses import asdict
from json import JSONDecodeError
from typing import cast

import httpx2

from .exceptions import ResponseParsingError
from .schemas import (
    Configuration,
    IntrospectionRequest,
    IntrospectionResponse,
    RevocationRequest,
    TokenExchangeRequest,
    TokenExchangeResponse,
)

logger = logging.getLogger(__name__)


class TokenExchangeClient:
    """Token Exchange API client."""

    def __init__(self, config: Configuration) -> None:
        """Instantiate the API client."""
        self.config = config
        self.session = httpx2.Client(
            auth=httpx2.BasicAuth(self.config.client_id, self.config.client_secret),
            timeout=self.config.requests_timeout,
        )

    def _post(
        self,
        url: str,
        request: TokenExchangeRequest | IntrospectionRequest | RevocationRequest,
        response_klass: type[TokenExchangeResponse | IntrospectionResponse] | None = None,
        error_message: str | None = None,
    ) -> TokenExchangeResponse | IntrospectionResponse | None:
        """Perform POST request for an API endpoint."""
        logger.debug("Will request %s endpoint with: %s", url, request)
        # Unset optional fields should not be sent as empty form values
        data = {key: value for key, value in asdict(request).items() if value is not None}
        api_response = self.session.post(url, data=data)
        api_response.raise_for_status()

        if response_klass is None:
            return None

        try:
            response = response_klass(**api_response.json())
        except (TypeError, JSONDecodeError) as err:
            logger.error("%s: %s", error_message, err)
            raise ResponseParsingError(error_message) from err

        logger.debug("Successful response: %s", response)
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
