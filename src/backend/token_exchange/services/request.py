"""Menshen: services:request for the token_exchange application."""

import logging
from collections.abc import Callable
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.db.models import F
from django.utils import timezone
from django.utils.module_loading import import_string
from lasuite.oidc_resource_server.backend import ResourceServerBackend
from requests import RequestException

from ..enums import (
    AllowedRequestedTokenType,
    TokenExchangeResponseTokenType,
    TokenType,
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
    ExchangedToken,
    ScopeGrant,
    TokenExchangeRule,
)
from ..schemas import (
    IntrospectionResponse,
    MenshenJWTGrantClaim,
    MenshenJWTGrantClaimThrottling,
    MenshenTokenExchangeResponse,
    TokenExchangeRequest,
)
from .token import TokenGenerator

logger = logging.getLogger(__name__)


class RequestService:
    """
    Token exchange request service.

    Use this service to generate an exchange token given a token exchange request.
    """

    kid: str = settings.TOKEN_EXCHANGE_JWT_CURRENT_KID

    @staticmethod
    def _validate_target(requested_audiences: list[str], rules: list) -> None:
        """
        Validate target service given source service associated rules and requested audiences.

        Target service may be invalid if:
            - requested_audiences does not correspond to any registered service
            - requested_audiences mentions extra services that are not registered

        Raises:
            TokenExchangeInvalidTargetError: if target service is invalid (see above).

        """
        rules_audiences = {rule.target_service.audience_id for rule in rules}
        if not rules_audiences:
            logger.error("Only unknown audience(s) requested: %s", ", ".join(requested_audiences))
            raise TokenExchangeInvalidTargetError("Only unknown audience(s) requested.")

        if unknown_audiences := (set(requested_audiences) - rules_audiences):
            logger.error("Unknown audience(s) requested: %s", ", ".join(unknown_audiences))
            raise TokenExchangeInvalidTargetError("Unknown audience(s) requested.")

    @classmethod
    def _introspection_backend(cls) -> ResourceServerBackend:
        """Cache the introspection backend loading (given configuration)."""
        # Get configured introspection backend
        introspection_backend = import_string(settings.OIDC_RS_BACKEND_CLASS)()
        # Prevent backend from enforcing scopes
        introspection_backend._scopes = [  # noqa: SLF001
            "openid"
        ]
        return introspection_backend

    @classmethod
    def _introspect_subject_token(cls, token: str, source_audience: str) -> IntrospectionResponse:
        """Introspect the token exchange request subject token."""
        try:
            user_info = cls._introspection_backend().get_user_info_with_introspection(token)
        except RequestException as exc:
            raise TokenExchangeResourceServerIntrospectionError(
                "Failed to introspect subject token."
            ) from exc

        introspection_response = IntrospectionResponse(**user_info)

        # Check the user audience is the same as the requesting service
        if getattr(introspection_response, settings.OIDC_RS_AUDIENCE_CLAIM) != source_audience:
            logger.error(
                "Introspected token audience is different from requesting service: %s, %s",
                getattr(introspection_response, settings.OIDC_RS_AUDIENCE_CLAIM),
                source_audience,
            )
            raise SuspiciousOperation()

        # We require the user sub
        if not introspection_response.sub:
            logger.warning("Introspection response has no 'sub'")
            raise TokenExchangeIntrospectionError(
                "Subject token introspection failed to provide an identity (sub)."
            )

        return introspection_response

    @staticmethod
    def _validate_pure_scopes(
        requested_scopes: set[str],
        requested_audiences: list[str],
        rules: list[TokenExchangeRule],
        user_scopes: list[str],
    ) -> list[MenshenJWTGrantClaim]:
        """Validate requested scopes that are not actions."""
        requested_accesses = {
            f"{audience_id}:{requested_scope}"
            for audience_id in requested_audiences
            for requested_scope in requested_scopes
        }

        scope_grants = ScopeGrant.objects.filter(
            rule__in=rules, source_scope__in=user_scopes
        ).annotate(
            audience_id=F("rule__target_service__audience_id"),
        )
        rules_accesses: dict = {
            f"{scope_grant.audience_id}:{scope_grant.granted_scope}": scope_grant  # ty: ignore
            for scope_grant in scope_grants
        }

        # Service cannot ask for more scopes than rules allow
        if not requested_accesses.issubset(set(rules_accesses.keys())):
            logger.warning(
                "Unsatisfied requested accesses (%s) given rules (%s)",
                requested_accesses,
                set(rules_accesses.keys()),
            )
            raise TokenExchangeInvalidScopesError("You cannot request more scope than rules allow.")

        grants: list[MenshenJWTGrantClaim] = []
        for requested_access in requested_accesses:
            scope_grant = rules_accesses[requested_access]
            grants.append(
                MenshenJWTGrantClaim(
                    audience_id=scope_grant.audience_id,
                    scope=scope_grant.granted_scope,
                    throttle=MenshenJWTGrantClaimThrottling(rate=scope_grant.throttle_rate)
                    if scope_grant.throttle_rate
                    else None,
                )
            )
        return grants

    @staticmethod
    def _validate_scope_action(
        requested_scopes: set[str],
        requested_audiences: list[str],
        rules: list[TokenExchangeRule],
        user_scopes: list[str],
    ) -> list[MenshenJWTGrantClaim]:
        """Validate requested action scope."""
        requested_accesses = {
            f"{audience_id}:{requested_scope}"
            for audience_id in requested_audiences
            for requested_scope in requested_scopes
        }

        action_grants = ActionScopeGrant.objects.filter(
            action__permissions__rule__in=rules,
            target_service__audience_id__in=requested_audiences,
        ).select_related("action", "target_service")
        rules_accesses: dict = {
            f"{action_grant.target_service.audience_id}:{action_grant.action.name}": action_grant
            for action_grant in action_grants
        }

        # Service cannot ask for more scopes than rules allow
        if not requested_accesses.issubset(set(rules_accesses.keys())):
            logger.warning(
                "Unsatisfied requested accesses (%s) given rules (%s)",
                requested_accesses,
                set(rules_accesses.keys()),
            )
            raise TokenExchangeInvalidScopesError("You cannot request more scope than rules allow.")
        required_source_scopes = {
            scope
            for action_grant in action_grants
            for scope in action_grant.action.permissions.values_list(  # ty: ignore
                "required_source_scope", flat=True
            )
            if len(scope)
        }

        # Check if user has required source scope for this action
        if required_source_scopes and not required_source_scopes.issubset(set(user_scopes)):
            logger.error(
                "Missing required source scope(s): %s",
                ",".join(required_source_scopes - requested_scopes),
            )
            raise TokenExchangeInvalidActionError(
                "All required source scopes are not satisfied for this action."
            )

        grants: list[MenshenJWTGrantClaim] = []
        for requested_access in requested_accesses:
            action_grant = rules_accesses[requested_access]
            grants.append(
                MenshenJWTGrantClaim(
                    audience_id=action_grant.target_service.audience_id,
                    scope=action_grant.granted_scope,
                    throttle=MenshenJWTGrantClaimThrottling(rate=action_grant.throttle_rate)
                    if action_grant.throttle_rate
                    else None,
                )
            )
        return grants

    @classmethod
    def _validate_scopes(
        cls,
        requested_scopes: set[str],
        requested_audiences: list[str],
        rules: list[TokenExchangeRule],
        user_scopes: list[str],
        is_action: bool = False,
    ) -> list[MenshenJWTGrantClaim]:
        """Validate scopes globally (pure scopes or actions)."""
        validation_fn: Callable = cls._validate_pure_scopes
        if is_action:
            validation_fn = cls._validate_scope_action

        return validation_fn(
            requested_scopes,
            requested_audiences,
            rules,
            user_scopes,
        )

    @classmethod
    def _generate_exchange_token(  # noqa: PLR0913
        cls,
        token_type: AllowedRequestedTokenType,
        user_info: IntrospectionResponse,
        scope: str,
        audiences: list[str],
        grants: list[MenshenJWTGrantClaim],
        expires_in: int,
    ) -> str:
        """Generate an exchange token given a token exchange request."""
        match token_type:
            case TokenType.ACCESS_TOKEN:
                return TokenGenerator.generate_opaque_token()
            case TokenType.JWT:
                if not cls.kid:
                    raise TokenExchangeConfigurationError("JWT signing key is not configured.")
                try:
                    return TokenGenerator.generate_jwt(
                        # user_info.sub cannot be None (enforced during instrospection)
                        sub=user_info.sub,  # ty: ignore
                        email=user_info.email,
                        audiences=audiences,
                        scope=scope,
                        expires_in=expires_in,
                        may_act=None,  # TODO: Parse from actor_token if needed  # noqa: FIX002
                        kid=cls.kid,
                        grants=grants,
                    )
                except ValueError as exc:
                    raise TokenExchangeIssuingError("An error occurred while issuing JWT.") from exc
            case _:
                raise TokenExchangeConfigurationError(
                    "Configured request token type is not supported."
                )

    @classmethod
    def _save(
        cls,
        request: TokenExchangeRequest,
        response: MenshenTokenExchangeResponse,
        user_info: IntrospectionResponse,
        audiences: list[str],
    ) -> ExchangedToken:
        """Save exchanged token."""
        expires_at = timezone.now() + timedelta(seconds=response.expires_in)
        return ExchangedToken.objects.create(
            token=response.access_token,
            token_type=response.issued_token_type,
            jwt_kid=cls.kid,
            subject_sub=user_info.sub,
            subject_email=user_info.email,
            audiences=audiences,
            scope=response.scope,
            grants=[grant.model_dump() for grant in response.grants],
            expires_at=expires_at,
            actor_token=request.actor_token if request.actor_token is not None else "",
            may_act=None,  # TODO: Parse from actor_token if needed  # noqa: FIX002
            subject_token_jti=user_info.jti,
            subject_token_scope=user_info.scope,
        )

    @classmethod
    def exchange(
        cls, source_audience: str, request: TokenExchangeRequest, persist: bool = False
    ) -> tuple[MenshenTokenExchangeResponse, ExchangedToken | None]:
        """Generate a token exchange response."""
        requested_audiences: list[str] = (
            request.audiences if request.audience else [source_audience]
        )
        rules = list(
            TokenExchangeRule.objects.filter(
                source_service__audience_id=source_audience,
                target_service__audience_id__in=requested_audiences,
                is_active=True,
            ).select_related("target_service")
        )

        # Validate target service given requested audiences and defined rules
        cls._validate_target(requested_audiences, rules)

        # Introspect request subject token
        user_info: IntrospectionResponse = cls._introspect_subject_token(
            request.subject_token, source_audience
        )

        # If no scope is specifically required, we switch to "best-effort" mode by returning
        # the same scopes as the subject token and ignoring the ones not allowed.
        requested_scopes = set(request.scopes or user_info.scopes)
        grants = cls._validate_scopes(
            requested_scopes,
            requested_audiences,
            rules,
            user_info.scopes,
            is_action=request.action is not None,
        )

        # Prepare exchange token parameters
        requested_token_type = (
            request.requested_token_type
            if request.requested_token_type
            else AllowedRequestedTokenType(TokenType.ACCESS_TOKEN)
        )
        scope = " ".join(sorted({grant.scope for grant in grants}))
        audiences: list[str] = (
            requested_audiences
            if settings.TOKEN_EXCHANGE_MULTI_AUDIENCES_ALLOWED
            else requested_audiences[:1]
        )
        expires_in: int = (
            int(min(rule.exchanged_token_duration.total_seconds() for rule in rules))
            or settings.TOKEN_EXCHANGE_DEFAULT_EXPIRES_IN
        )
        access_token: str = cls._generate_exchange_token(
            requested_token_type, user_info, scope, audiences, grants, expires_in
        )
        response = MenshenTokenExchangeResponse(
            access_token=access_token,
            issued_token_type=requested_token_type,
            token_type=TokenExchangeResponseTokenType.BEARER,
            expires_in=expires_in,
            scope=scope,
            refresh_token=None,
            grants=grants,
        )

        if not persist:
            return (response, None)

        # Save exchanged token to database
        exchanged_token = cls._save(request, response, user_info, audiences)

        # Log the exchange
        logger.info(
            "Token exchanged: sub=%s, email=%s, audiences=%s, token_type=%s, "
            "expires_at=%s, subject_jti=%s, kid=%s, scopes_granted=%s, grants=%s",
            exchanged_token.subject_sub,
            exchanged_token.subject_email,
            exchanged_token.audiences,
            exchanged_token.token_type,
            exchanged_token.expires_at,
            exchanged_token.subject_token_jti,
            exchanged_token.jwt_kid,
            exchanged_token.scope,
            exchanged_token.grants,
        )

        return (response, exchanged_token)
