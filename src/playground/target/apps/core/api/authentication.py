"""Target: core API authentication."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from menshen_client import (
    Configuration,
    IntrospectionRequest,
    TokenExchangeClient,
    TokenType,
)
from mozilla_django_oidc.contrib.drf import OIDCAuthentication

logger = logging.getLogger(__name__)

User = get_user_model()


class TokenExchangeAuthentication(OIDCAuthentication):
    """Token Exchange based authentication."""

    def authenticate(self, request):
        access_token = self.get_access_token(request)
        logger.info(f"authenticate -> {access_token=}")

        # Create the client instance
        client = TokenExchangeClient(
            config=Configuration(
                client_id=settings.OIDC_TX_CLIENT_ID,
                client_secret=settings.OIDC_TX_CLIENT_SECRET,
                server_root_url=settings.OIDC_TX_ROOT_URL,
            )
        )

        # Introspect the token
        introspection_response = client.introspect(
            IntrospectionRequest(
                token=access_token,
                token_type_hint=TokenType.ACCESS_TOKEN,
            )
        )

        if not introspection_response.active:
            raise PermissionDenied("User is not active")

        # Get user
        user = User.objects.get_user_by_sub_or_email(
            introspection_response.sub, introspection_response.email
        )

        return user, access_token
