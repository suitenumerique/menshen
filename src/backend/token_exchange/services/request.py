"""Menshen: services:request for the token_exchange application."""

import logging
from functools import cached_property

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.db.models import F, QuerySet
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
    ScopeGrant,
    ServiceProvider,
    TokenExchangeRule,
)
from ..structs import (
    IntrospectionResponse,
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

    def __init__(self, service: ServiceProvider, request: TokenExchangeRequest) -> None:
        """
        Initialize the service.

        Note that token exchange request subject token introspection is performed during class
        instantiation. Thus instantiation may be slow.

        Args:
            service: the sources service performing the token exchange request
            request: the token exchange request

        """
        self.service: ServiceProvider = service
        self.request: TokenExchangeRequest = request
        self.requested_audiences: list = (
            request.audiences if request.audience else [service.audience_id]
        )
        self.granted_scopes: set = set()
        self.grants: list[MenshenJWTGrantClaim] = []
        self.kid: str = ""
        self.audiences: list[str] = (
            self.requested_audiences
            if settings.TOKEN_EXCHANGE_MULTI_AUDIENCES_ALLOWED
            else self.requested_audiences[:1]
        )
        self.user_info: IntrospectionResponse = self._introspect_subject_token()

    @cached_property
    def rules(self) -> QuerySet[TokenExchangeRule]:
        """Get rules associated with the source service for the target audience."""
        return TokenExchangeRule.objects.filter(
            source_service=self.service,
            target_service__audience_id__in=self.requested_audiences,
        ).select_related("target_service")

    @cached_property
    def introspection_backend(self) -> ResourceServerBackend:
        """Return the resource server backend class based on the settings."""
        backend_class = import_string(settings.OIDC_RS_BACKEND_CLASS)
        # Prevent backend from enforcing scopes: MUST improve code here
        backend_class._scopes = [  # noqa: SLF001
            "openid"
        ]
        return backend_class()

    def _validate_target(self) -> None:
        """
        Validate target service given source service associated rules and requested audiences.

        Target service may be invalid if:
            - requested_audiences does not correspond to any registered service
            - requested_audiences mentions extra services that are not registered
            - rules associated with this service are inactive

        Returns:
            None if rules are valid for the requested audiences
            Response [400] when the target is invalid

        """
        rules_audiences = {rule.target_service.audience_id for rule in self.rules}
        if not rules_audiences:
            message = "Only unknown audience(s) requested: {audiences}".format(
                audiences=", ".join(self.requested_audiences)
            )
            logger.error(message)
            raise TokenExchangeInvalidTargetError(message)

        if unknown_audiences := (set(self.requested_audiences) - rules_audiences):
            message = "Unknown audience(s) requested: {audiences}".format(
                audiences=", ".join(unknown_audiences)
            )
            logger.warning(message)
            raise TokenExchangeInvalidTargetError(message)

        if any(not rule.is_active for rule in self.rules):
            message = "Some rules are inactive: {rules}".format(
                rules=", ".join(str(rule.pk) for rule in self.rules if not rule.is_active)
            )
            logger.warning(message)
            raise TokenExchangeInvalidTargetError(message)

    def _introspect_subject_token(self) -> IntrospectionResponse:
        """Introspect the token exchange request subject token."""
        try:
            user_info = self.introspection_backend.get_user_info_with_introspection(
                self.request.subject_token
            )
        except RequestException as exc:
            raise TokenExchangeResourceServerIntrospectionError(
                "Failed to introspect subject token"
            ) from exc

        if self.introspection_backend.token_origin_audience != self.service.audience_id:
            logger.error(
                "Introspected token origin is different from requesting service: %s, %s",
                self.introspection_backend.token_origin_audience,
                self.service.audience_id,
            )
            raise SuspiciousOperation()

        introspection_response = IntrospectionResponse(**user_info)

        # Check the user audience is the same as the requesting service
        if (
            getattr(introspection_response, settings.OIDC_RS_AUDIENCE_CLAIM)
            != self.service.audience_id
        ):
            logger.error(
                "Introspected token audience is different from requesting service: %s, %s",
                getattr(introspection_response, settings.OIDC_RS_AUDIENCE_CLAIM),
                self.service.audience_id,
            )
            raise SuspiciousOperation()

        # We need at least one identity
        if not introspection_response.sub and not introspection_response.email:
            logger.warning("Introspection response missing both 'sub' and 'email'")
            raise TokenExchangeIntrospectionError(
                "Subject token introspection failed to provide identity (sub or email)"
            )

        return introspection_response

    def _validate_pure_scopes(self) -> None:
        """Validate requested scopes that are not actions."""
        # If no scope is specifically required, we switch to "best-effort" mode by returning
        # the same scopes as the subject token and ignoring the ones not allowed.
        requested_scopes = set(
            self.request.scopes if self.request.scopes else self.user_info.scopes
        )
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
            raise TokenExchangeInvalidTargetError("You cannot request more scope than rules allow")

        for requested_access in requested_accesses:
            scope_grant = rules_accesses[requested_access]
            # FIXME  # noqa: FIX001
            # this cannot happen (source_scope is filtered by user info scope)
            if scope_grant.source_scope not in self.user_info.scopes:
                raise TokenExchangeInvalidTargetError(
                    "User is not allowed to request rule-defined source scope"
                )
            self.granted_scopes.add(scope_grant.granted_scope)
            self.grants.append(
                MenshenJWTGrantClaim(
                    audience_id=scope_grant.audience_id,
                    scope=scope_grant.granted_scope,
                    throttle=MenshenJWTGrantClaimThrottling(rate=scope_grant.throttle_rate)
                    if scope_grant.throttle_rate
                    else None,
                )
            )

        # If scopes were requested, validate they're all granted
        # FIXME: this cannot happen?  # noqa: FIX001
        if requested_scopes and not requested_scopes.issubset(self.granted_scopes):
            missing_scopes = requested_scopes - self.granted_scopes
            message = "Requested scopes cannot be granted. Missing scopes: {}".format(
                ", ".join(missing_scopes),
            )
            logger.error(message)
            raise TokenExchangeInvalidScopesError(message)

    def _validate_scope_action(self) -> None:
        """Validate requested action scope."""
        action_grants = ActionScopeGrant.objects.filter(
            action__permissions__rule__in=self.rules,
        ).prefetch_related("action__permissions")

        for action_grant in action_grants:
            required_source_scopes = set(
                " ".join(
                    action_grant.action.permissions.values_list("required_source_scope", flat=True)
                ).split()
            )
            if (
                # Check if user has required source scope for this action
                required_source_scopes - set(self.user_info.scopes)
            ) or (
                # Check if action is requested (action scopes are prefixed with "action:")
                self.request.scopes and action_grant.action.name not in self.request.scopes
            ):
                continue  # User doesn't have required scope, skip this action

            self.granted_scopes.add(action_grant.granted_scope)
            self.grants.append(
                MenshenJWTGrantClaim(
                    audience_id=action_grant.target_service.audience_id,
                    scope=action_grant.granted_scope,
                    throttle=MenshenJWTGrantClaimThrottling(rate=action_grant.throttle_rate)
                    if action_grant.throttle_rate
                    else None,
                )
            )

        # If action was requested, validate it's granted
        action_name = self.request.scopes[0]
        if not len(self.grants):
            message = f"Requested action '{action_name}' cannot be granted."
            logger.error(message)
            raise TokenExchangeInvalidActionError(message)

    def _validate_scopes(self):
        """Validate scopes globally (pure scopes or actions)."""
        if self.request.action:
            self._validate_scope_action()
        else:
            self._validate_pure_scopes()

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
                self.kid = settings.TOKEN_EXCHANGE_JWT_CURRENT_KID
                if not self.kid:
                    raise TokenExchangeConfigurationError("JWT signing key is not configured.")
                if not self.user_info.sub:
                    raise TokenExchangeIssuingError(
                        "A subject claim is required to generate an exchange token."
                    )
                try:
                    return TokenGenerator.generate_jwt(
                        sub=self.user_info.sub,
                        email=self.user_info.email,
                        audiences=self.audiences,
                        scope=scope,
                        expires_in=expires_in,
                        may_act=None,  # TODO: Parse from actor_token if needed  # noqa: FIX002
                        kid=settings.TOKEN_EXCHANGE_JWT_CURRENT_KID,
                        grants=self.grants,
                    )
                except ValueError as exc:
                    raise TokenExchangeIssuingError("An error occured while issuing JWT.") from exc
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
