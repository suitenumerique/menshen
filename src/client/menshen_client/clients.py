"""Menshen client: API clients."""

import logging
import re
from dataclasses import asdict
from http import HTTPStatus
from json import JSONDecodeError
from types import TracebackType
from typing import Self, cast

import httpx2

from .exceptions import InvalidTokenError, ResponseParsingError
from .schemas import (
    TOKEN_PATTERN,
    BaseTokenRequest,
    Configuration,
    IntrospectionRequest,
    IntrospectionResponse,
    RevocationRequest,
    TokenExchangeRequest,
    TokenExchangeResponse,
)

logger = logging.getLogger(__name__)


class BaseTokenExchangeClient:
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

    def _validate_token(self, request: BaseTokenRequest) -> None:
        """
        Validate the opaque token format before sending it to Menshen.

        JWTs (identified by their token type hint or by their shape) are not validated
        locally: the server is the only judge.

        Raises:
            InvalidTokenError: if the opaque token is malformed or too short.

        """
        if request.is_jwt:
            return
        if (
            not re.fullmatch(TOKEN_PATTERN, request.token)
            or len(request.token) < self.config.opaque_token_min_length
        ):
            raise InvalidTokenError("Invalid token format")

    @staticmethod
    def _parse_response(
        api_response: httpx2.Response,
        request: TokenExchangeRequest | IntrospectionRequest | RevocationRequest,
        response_klass: type[TokenExchangeResponse | IntrospectionResponse] | None = None,
        error_message: str | None = None,
    ) -> TokenExchangeResponse | IntrospectionResponse | None:
        """Parse an API endpoint response."""
        try:
            api_response.raise_for_status()
        except httpx2.HTTPStatusError as err:
            # The server rejects malformed tokens with a validation error
            if (
                isinstance(request, BaseTokenRequest)
                and api_response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
            ):
                logger.debug("Token rejected by the server: %s", api_response.text)
                raise InvalidTokenError("Token rejected by the server") from err
            raise

        if response_klass is None:
            return None

        try:
            response = response_klass(**api_response.json())
        except (TypeError, JSONDecodeError) as err:
            logger.error("%s: %s", error_message, err)
            raise ResponseParsingError(error_message) from err

        logger.debug("Successful response: %s", response)
        return response


class TokenExchangeClient(BaseTokenExchangeClient):
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
        return self._parse_response(api_response, request, response_klass, error_message)

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
        self._validate_token(request)
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
        self._validate_token(request)
        self._post(self.config.revocation_url, request)


class TokenExchangeAsyncClient(BaseTokenExchangeClient):
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
        return self._parse_response(api_response, request, response_klass, error_message)

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
        self._validate_token(request)
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
        self._validate_token(request)
        await self._post(self.config.revocation_url, request)
