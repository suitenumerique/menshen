"""Menshen client: API clients."""

import logging
from dataclasses import asdict
from json import JSONDecodeError
from types import TracebackType
from typing import Self, cast

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


class _BaseTokenExchangeClient:
    """Token Exchange API client base class with transport-agnostic logic."""

    def __init__(self, config: Configuration) -> None:
        """Instantiate the API client."""
        self.config = config

    def _auth(self) -> httpx2.BasicAuth:
        """Get the API client authentication."""
        return httpx2.BasicAuth(self.config.client_id, self.config.client_secret)

    @staticmethod
    def _form_data(
        url: str, request: TokenExchangeRequest | IntrospectionRequest | RevocationRequest
    ) -> dict:
        """Get the POST request form data for an API endpoint."""
        logger.debug("Will request %s endpoint with: %s", url, request)
        # Unset optional fields should not be sent as empty form values
        return {key: value for key, value in asdict(request).items() if value is not None}

    @staticmethod
    def _parse_response(
        api_response: httpx2.Response,
        response_klass: type[TokenExchangeResponse | IntrospectionResponse] | None = None,
        error_message: str | None = None,
    ) -> TokenExchangeResponse | IntrospectionResponse | None:
        """Parse an API endpoint response."""
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


class TokenExchangeClient(_BaseTokenExchangeClient):
    """Token Exchange API client."""

    def __init__(self, config: Configuration) -> None:
        """Instantiate the API client."""
        super().__init__(config)
        self.session = httpx2.Client(auth=self._auth(), timeout=self.config.requests_timeout)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the API client HTTP connections."""
        self.session.close()

    def _post(
        self,
        url: str,
        request: TokenExchangeRequest | IntrospectionRequest | RevocationRequest,
        response_klass: type[TokenExchangeResponse | IntrospectionResponse] | None = None,
        error_message: str | None = None,
    ) -> TokenExchangeResponse | IntrospectionResponse | None:
        """Perform POST request for an API endpoint."""
        api_response = self.session.post(url, data=self._form_data(url, request))
        return self._parse_response(api_response, response_klass, error_message)

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


class TokenExchangeAsyncClient(_BaseTokenExchangeClient):
    """Token Exchange API asynchronous client."""

    def __init__(self, config: Configuration) -> None:
        """Instantiate the API client."""
        super().__init__(config)
        self.session = httpx2.AsyncClient(auth=self._auth(), timeout=self.config.requests_timeout)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the API client HTTP connections."""
        await self.session.aclose()

    async def _post(
        self,
        url: str,
        request: TokenExchangeRequest | IntrospectionRequest | RevocationRequest,
        response_klass: type[TokenExchangeResponse | IntrospectionResponse] | None = None,
        error_message: str | None = None,
    ) -> TokenExchangeResponse | IntrospectionResponse | None:
        """Perform POST request for an API endpoint."""
        api_response = await self.session.post(url, data=self._form_data(url, request))
        return self._parse_response(api_response, response_klass, error_message)

    async def exchange(self, request: TokenExchangeRequest) -> TokenExchangeResponse:
        """Request an exchange token."""
        return cast(
            TokenExchangeResponse,
            await self._post(
                self.config.token_url,
                request,
                TokenExchangeResponse,
                "Invalid token exchange response",
            ),
        )

    async def introspect(self, request: IntrospectionRequest) -> IntrospectionResponse:
        """Introspect exchanged token."""
        return cast(
            IntrospectionResponse,
            await self._post(
                self.config.introspection_url,
                request,
                IntrospectionResponse,
                "Invalid introspection response",
            ),
        )

    async def revoke(self, request: RevocationRequest) -> None:
        """Revoke exchanged token."""
        await self._post(self.config.revocation_url, request)
