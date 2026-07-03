"""Menshen: services:request for the token_exchange application."""

import logging
from functools import cached_property

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.db.models import F
from django.utils.module_loading import import_string
from lasuite.oidc_resource_server.backend import ResourceServerBackend
from requests import RequestException

from ..enums import (
    AllowedRequestedTokenTypeEnum,
    TokenExchangeResponseTokenType,
    TokenTypeEnum,
)
from ..exceptions import (
    TokenExchangeConfigurationError,
    TokenExchangeIntrospectionError,
    TokenExchangeInvalidActionError,
    TokenExchangeInvalidScopesError,
    TokenExchangeInvalidTargetError,
    TokenExchangeIssuingError,
    TokenExchangeResourceServerIntrospectionError,
)
from ..models import (
    ActionScopeGrant,
    IntrospectionResponse,
    ScopeGrant,
    TokenExchangeRule,
)
from ..structs import (
    MenshenJWTGrantClaim,
    MenshenJWTGrantClaimThrottling,
    MenshenTokenExchangeResponse,
    TokenExchangeRequest,
)
from .token import TokenGenerator

logger = logging.getLogger(__name__)


class TokenExchangeRequestService:
    """
    Token exchange request service.

    Use this service to generate an exchange token given a token exchange request.
    """

    def __init__(self, source_audience: str, request: TokenExchangeRequest) -> None:
        """
        Initialize the service.

        Args:
            source_audience: audience from the source service performing the token exchange request
            request: the token exchange request

        """
        self.source_audience: str = source_audience
        self.request: TokenExchangeRequest = request
        self.requested_audiences: list = (
            request.audiences if request.audience else [source_audience]
        )
        self.grants: list[MenshenJWTGrantClaim] = []
        self.kid: str = settings.TOKEN_EXCHANGE_JWT_CURRENT_KID
        self.audiences: list[str] = (
            self.requested_audiences
            if settings.TOKEN_EXCHANGE_MULTI_AUDIENCES_ALLOWED
            else self.requested_audiences[:1]
        )

    @cached_property
    def user_info(self) -> IntrospectionResponse:
        """Get subject token introspection response."""
        return self._introspect_subject_token()

    @property
    def granted_scopes(self) -> set[str]:
        """Get granted scopes from grants."""
        return {grant.scope for grant in self.grants}

    @cached_property
    def rules(self) -> list[TokenExchangeRule]:
        """Get active rules associated with the source and target audiences."""
        return list(
            TokenExchangeRule.objects.filter(
                source_service__audience_id=self.source_audience,
                target_service__audience_id__in=self.requested_audiences,
                is_active=True,
            ).select_related("target_service")
        )

    @cached_property
    def introspection_backend(self) -> ResourceServerBackend:
        """Return the resource server backend class based on the settings."""
        backend_class = import_string(settings.OIDC_RS_BACKEND_CLASS)
        backend = backend_class()
        # Prevent backend from enforcing scopes
        backend._scopes = [  # noqa: SLF001
            "openid"
        ]
        return backend

    def _validate_target(self) -> None:
        """
        Validate target service given source service associated rules and requested audiences.

        Target service may be invalid if:
            - requested_audiences does not correspond to any registered service
            - requested_audiences mentions extra services that are not registered

        Raises:
            TokenExchangeInvalidTargetError: if target service is invalid (see above).

        """
        rules_audiences = {rule.target_service.audience_id for rule in self.rules}
        if not rules_audiences:
            logger.error(
                "Only unknown audience(s) requested: %s", ", ".join(self.requested_audiences)
            )
            raise TokenExchangeInvalidTargetError("Only unknown audience(s) requested.")

        if unknown_audiences := (set(self.requested_audiences) - rules_audiences):
            logger.error("Unknown audience(s) requested: %s", ", ".join(unknown_audiences))
            raise TokenExchangeInvalidTargetError("Unknown audience(s) requested.")

    def _introspect_subject_token(self) -> IntrospectionResponse:
        """Introspect the token exchange request subject token."""
        try:
            user_info = self.introspection_backend.get_user_info_with_introspection(
                self.request.subject_token
            )
        except RequestException as exc:
            raise TokenExchangeResourceServerIntrospectionError(
                "Failed to introspect subject token."
            ) from exc

        # Ignore extra fields
        introspection_response = IntrospectionResponse(
            **{
                key: user_info[key]
                for key in IntrospectionResponse.__struct_fields__
                if key in user_info
            }
        )

        # Check the user audience is the same as the requesting service
        if getattr(introspection_response, settings.OIDC_RS_AUDIENCE_CLAIM) != self.source_audience:
            logger.error(
                "Introspected token audience is different from requesting service: %s, %s",
                getattr(introspection_response, settings.OIDC_RS_AUDIENCE_CLAIM),
                self.source_audience,
            )
            raise SuspiciousOperation()

        # We require the user sub
        if not introspection_response.sub:
            logger.warning("Introspection response has no 'sub'")
            raise TokenExchangeIntrospectionError(
                "Subject token introspection failed to provide an identity (sub)."
            )

        return introspection_response

    def _validate_pure_scopes(self) -> None:
        """Validate requested scopes that are not actions."""
        # If no scope is specifically required, we switch to "best-effort" mode by returning
        # the same scopes as the subject token and ignoring the ones not allowed.
        requested_scopes = set(self.request.scopes or self.user_info.scopes)
        requested_accesses = {
            f"{audience_id}:{requested_scope}"
            for audience_id in self.requested_audiences
            for requested_scope in requested_scopes
        }

        scope_grants = ScopeGrant.objects.filter(
            rule__in=self.rules, source_scope__in=self.user_info.scopes
        ).annotate(
            audience_id=F("rule__target_service__audience_id"),
        )
        rules_accesses: dict = {
            f"{scope_grant.audience_id}:{scope_grant.granted_scope}": scope_grant
            for scope_grant in scope_grants
        }

        # Service cannot ask for more scopes than rules allow
        if not requested_accesses.issubset(set(rules_accesses.keys())):
            raise TokenExchangeInvalidScopesError("You cannot request more scope than rules allow.")

        for requested_access in requested_accesses:
            scope_grant = rules_accesses[requested_access]
            self.grants.append(
                MenshenJWTGrantClaim(
                    audience_id=scope_grant.audience_id,
                    scope=scope_grant.granted_scope,
                    throttle=MenshenJWTGrantClaimThrottling(rate=scope_grant.throttle_rate)
                    if scope_grant.throttle_rate
                    else None,
                )
            )

    def _validate_scope_action(self) -> None:
        """Validate requested action scope."""
        requested_scopes = set(self.request.scopes or self.user_info.scopes)
        requested_accesses = {
            f"{audience_id}:{requested_scope}"
            for audience_id in self.requested_audiences
            for requested_scope in requested_scopes
        }

        action_grants = ActionScopeGrant.objects.filter(
            action__permissions__rule__in=self.rules,
            target_service__audience_id__in=self.requested_audiences,
        ).select_related("action", "target_service")
        rules_accesses: dict = {
            f"{action_grant.target_service.audience_id}:{action_grant.action.name}": action_grant
            for action_grant in action_grants
        }

        # Service cannot ask for more scopes than rules allow
        if not requested_accesses.issubset(set(rules_accesses.keys())):
            raise TokenExchangeInvalidScopesError("You cannot request more scope than rules allow.")
        required_source_scopes = {
            scope
            for action_grant in action_grants
            for scope in action_grant.action.permissions.values_list(
                "required_source_scope", flat=True
            )
            if len(scope)
        }

        # Check if user has required source scope for this action
        if required_source_scopes and not required_source_scopes.issubset(
            set(self.user_info.scopes)
        ):
            logger.error(
                "Missing required source scope(s): %s",
                ",".join(required_source_scopes - requested_scopes),
            )
            raise TokenExchangeInvalidActionError(
                "All required source scopes are not satisfied for this action."
            )

        for requested_access in requested_accesses:
            action_grant = rules_accesses[requested_access]
            self.grants.append(
                MenshenJWTGrantClaim(
                    audience_id=action_grant.target_service.audience_id,
                    scope=action_grant.granted_scope,
                    throttle=MenshenJWTGrantClaimThrottling(rate=action_grant.throttle_rate)
                    if action_grant.throttle_rate
                    else None,
                )
            )

    def _validate_scopes(self):
        """Validate scopes globally (pure scopes or actions)."""
        if self.request.action:
            self._validate_scope_action()
        else:
            self._validate_pure_scopes()

        # If action was requested, validate it's granted
        if not len(self.grants):
            missing_actions = ",".join(self.request.scopes)
            logger.error("Requested action '%s' cannot be granted", missing_actions)
            raise TokenExchangeInvalidActionError(
                f"Requested action '{missing_actions}' cannot be granted."
            )

    def _generate_exchange_token(
        self,
        token_type: AllowedRequestedTokenTypeEnum,
        scope: str,
        expires_in: int,
    ) -> str:
        """Generate an exchange token given a token exchange request."""
        match token_type:
            case TokenTypeEnum.ACCESS_TOKEN:
                return TokenGenerator.generate_opaque_token()
            case TokenTypeEnum.JWT:
                if not self.kid:
                    raise TokenExchangeConfigurationError("JWT signing key is not configured.")
                try:
                    return TokenGenerator.generate_jwt(
                        # user_info.sub cannot be None (enforced during instrospection)
                        sub=self.user_info.sub,  # ty: ignore
                        email=self.user_info.email,
                        audiences=self.audiences,
                        scope=scope,
                        expires_in=expires_in,
                        may_act=None,  # TODO: Parse from actor_token if needed  # noqa: FIX002
                        kid=self.kid,
                        grants=self.grants,
                    )
                except ValueError as exc:
                    raise TokenExchangeIssuingError("An error occurred while issuing JWT.") from exc
            case _:
                raise TokenExchangeConfigurationError(
                    "Configured request token type is not supported."
                )

    def generate_exchange_response(self) -> MenshenTokenExchangeResponse:
        """Generate an exchange response."""
        self._validate_target()
        self._validate_scopes()

        expires_in: int = (
            int(min(rule.exchanged_token_duration.total_seconds() for rule in self.rules))
            or settings.TOKEN_EXCHANGE_DEFAULT_EXPIRES_IN
        )
        scope = " ".join(sorted(self.granted_scopes))
        requested_token_type = (
            self.request.requested_token_type
            if self.request.requested_token_type
            else AllowedRequestedTokenTypeEnum(TokenTypeEnum.ACCESS_TOKEN)
        )
        access_token: str = self._generate_exchange_token(requested_token_type, scope, expires_in)

        return MenshenTokenExchangeResponse(
            access_token=access_token,
            issued_token_type=requested_token_type,
            token_type=TokenExchangeResponseTokenType.BEARER,
            expires_in=expires_in,
            scope=scope,
            refresh_token=None,
            grants=self.grants,
        )
