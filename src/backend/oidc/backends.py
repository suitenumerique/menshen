"""Menshen: resource server backends for the oidc module."""

import json
import logging
from json import JSONDecodeError

import httpx2
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from joserfc import jwe, jwk, jwt
from joserfc.errors import InvalidClaimError, InvalidTokenError, JoseError, MissingClaimError
from joserfc.jwk import KeySet
from joserfc.registry import HeaderParameter

from .clients import AuthorizationServerClient, JWTAuthorizationServerClient
from .exceptions import IntrospectionInactiveTokenError

logger = logging.getLogger(__name__)

CLAIMS_ERRORS = (InvalidClaimError, InvalidTokenError, MissingClaimError)


class ResourceServerBackend:
    """
    OAuth 2.0 resource server backend using JSON introspection responses.

    Submit access tokens to the authorization server for introspection, to ensure
    their validity and obtain the associated metadata.

    Reference: https://www.rfc-editor.org/info/rfc7662
    """

    authorization_server_client_class: type[AuthorizationServerClient] = AuthorizationServerClient

    def __init__(self, transport: httpx2.BaseTransport | None = None):
        """Read configuration from settings, an HTTP transport can be injected (tests)."""
        self._client_id = settings.OIDC_RS_CLIENT_ID
        self._client_secret = settings.OIDC_RS_CLIENT_SECRET
        self._scopes = settings.OIDC_RS_SCOPES
        self._audience_claim = settings.OIDC_RS_AUDIENCE_CLAIM

        if not self._client_id or not self._client_secret:
            raise ImproperlyConfigured(
                f"Could not instantiate {self.__class__.__name__}: "
                "missing required settings: OIDC_RS_CLIENT_ID, OIDC_RS_CLIENT_SECRET"
            )

        self._authorization_server_client = self.authorization_server_client_class(
            transport=transport
        )
        self._introspection_claims_registry = jwt.JWTClaimsRegistry(
            iss={"essential": False, "value": self._authorization_server_client.url},
            **self._introspection_claims_options(),
        )

    def _introspection_claims_options(self) -> dict:
        """Claims options shared by all introspection responses."""
        return {
            "active": {"essential": True},
            # scope and audience may be missing when the token is inactive,
            # their content is validated in _verify_user_info
            "scope": {"essential": False},
            self._audience_claim: {"essential": False},
        }

    def get_user_info_with_introspection(self, access_token: str) -> dict:
        """
        Get user info from an access token emitted by the authorization server.

        Raises:
            IntrospectionInactiveTokenError: the token is not active.
            SuspiciousOperation: the introspection response is invalid.
            httpx2.HTTPError: the authorization server cannot be reached.

        """
        claims = self._introspect(access_token)
        self._verify_claims(claims)
        return self._verify_user_info(claims)

    def _get_introspection(self, access_token: str) -> str:
        """Request introspection of an access token to the authorization server."""
        try:
            return self._authorization_server_client.get_introspection(
                self._client_id, self._client_secret, access_token
            )
        except httpx2.HTTPStatusError as err:
            logger.debug("Could not fetch introspection", exc_info=True)
            raise SuspiciousOperation("Could not fetch introspection") from err

    def _introspect(self, access_token: str) -> dict:
        """Introspect an access token, the response is expected to be a JSON object."""
        introspection_str = self._get_introspection(access_token)
        try:
            introspection_data = json.loads(introspection_str)
        except JSONDecodeError as err:
            raise SuspiciousOperation("Invalid JSON for introspection") from err

        if not isinstance(introspection_data, dict):
            raise SuspiciousOperation("Invalid JSON for introspection")

        return introspection_data

    def _verify_claims(self, claims: dict) -> None:
        """Verify introspection response claims."""
        try:
            self._introspection_claims_registry.validate(claims)
        except CLAIMS_ERRORS as err:
            logger.debug("Failed to validate token's claims", exc_info=True)
            raise SuspiciousOperation("Failed to validate token's claims") from err

    def _verify_user_info(self, introspection_response: dict) -> dict:
        """
        Verify the introspection response to get valid and relevant user info.

        The token should be active, have at least one of the required scopes and
        provide its source audience.
        """
        if not introspection_response["active"]:
            logger.info("Token introspection refused because user is not active")
            raise IntrospectionInactiveTokenError("Introspected user is not active")

        scope = introspection_response.get("scope")
        if scope is None:
            message = "Token introspection failed due to missing 'scope' claim."
            logger.warning(message)
            raise SuspiciousOperation(message)

        scopes = scope.split(" ")
        if set(self._scopes).isdisjoint(scopes):
            logger.warning("Token introspection failed, missing required scopes: %s", scopes)
            raise SuspiciousOperation("Introspection response is missing required scopes.")

        if not introspection_response.get(self._audience_claim):
            logger.warning("Token introspection failed, missing %s claim", self._audience_claim)
            raise SuspiciousOperation("Introspection response does not provide source audience.")

        return introspection_response


class JWTResourceServerBackend(ResourceServerBackend):
    """
    OAuth 2.0 resource server backend using JWT introspection responses.

    The introspection response is expected to be signed (JWS) then encrypted (JWE).

    Reference: https://www.rfc-editor.org/info/rfc9701
    """

    authorization_server_client_class: type[AuthorizationServerClient] = (
        JWTAuthorizationServerClient
    )
    _authorization_server_client: JWTAuthorizationServerClient

    def __init__(self, transport: httpx2.BaseTransport | None = None):
        """Read encryption and signing configuration from settings."""
        super().__init__(transport=transport)
        self._encryption_encoding = settings.OIDC_RS_ENCRYPTION_ENCODING
        self._encryption_algorithm = settings.OIDC_RS_ENCRYPTION_ALGO
        self._signing_algorithm = settings.OIDC_RS_SIGNING_ALGO

        # The issuer is validated in the enclosing JWT
        self._introspection_claims_registry = jwt.JWTClaimsRegistry(
            **self._introspection_claims_options()
        )

    def _introspect(self, access_token: str) -> dict:
        """Introspect an access token, the response is expected to be a JWE(JWS)."""
        introspection_str = self._get_introspection(access_token)

        jws = self._decrypt(introspection_str, self._import_private_key())

        try:
            public_key_set = self._authorization_server_client.import_public_keys()
        except (TypeError, ValueError, AttributeError, httpx2.HTTPStatusError) as err:
            logger.debug("Could not get authorization server JWKS", exc_info=True)
            raise SuspiciousOperation("Could not get authorization server JWKS") from err

        token = self._decode(jws, public_key_set)

        registry = jwt.JWTClaimsRegistry(
            iss={"essential": True, "value": self._authorization_server_client.url},
            aud={"essential": True, "value": self._client_id},
            token_introspection={"essential": True},
        )
        try:
            registry.validate(token.claims)
        except CLAIMS_ERRORS as err:
            logger.exception("Failed to validate introspection JWT claims")
            raise SuspiciousOperation("Failed to validate token's claims") from err

        introspection_data = token.claims["token_introspection"]
        if not isinstance(introspection_data, dict):
            raise SuspiciousOperation("Invalid token_introspection claim")

        return introspection_data

    def _import_private_key(self) -> jwk.Key:
        """Import the resource server private key used to decrypt introspection responses."""
        private_key_str = settings.OIDC_RS_PRIVATE_KEY_STR
        if not private_key_str:
            raise ImproperlyConfigured("OIDC_RS_PRIVATE_KEY_STR setting is missing or empty.")

        try:
            return jwk.import_key(
                private_key_str,
                key_type=settings.OIDC_RS_ENCRYPTION_KEY_TYPE,
                parameters={"alg": self._encryption_algorithm, "use": "enc"},
            )
        except ValueError as err:
            raise ImproperlyConfigured("OIDC_RS_PRIVATE_KEY_STR setting is wrong.") from err

    def _decrypt(self, encrypted_token: str, private_key: jwk.Key) -> bytes:
        """Decrypt the introspection response encrypted by the authorization server."""
        try:
            decrypted = jwe.decrypt_compact(
                encrypted_token,
                private_key,
                registry=jwe.JWERegistry(
                    # Extra header parameters set by some providers (e.g. node-oidc-provider)
                    header_registry={
                        "iss": HeaderParameter("Issuer", "str"),
                        "aud": HeaderParameter("Audience", "str"),
                    },
                    algorithms=[self._encryption_algorithm, self._encryption_encoding],
                ),
            )
        except Exception as err:
            logger.debug("Token decryption failed", exc_info=True)
            raise SuspiciousOperation("Token decryption failed") from err

        if decrypted.plaintext is None:
            raise SuspiciousOperation("Token decryption failed")

        return decrypted.plaintext

    def _decode(self, encoded_token: bytes, public_key_set: KeySet) -> jwt.Token:
        """Decode and verify the introspection response signed by the authorization server."""
        try:
            return jwt.decode(encoded_token, public_key_set, algorithms=[self._signing_algorithm])
        except (ValueError, JoseError) as err:
            logger.debug("Token decoding failed", exc_info=True)
            raise SuspiciousOperation("Token decoding failed") from err
