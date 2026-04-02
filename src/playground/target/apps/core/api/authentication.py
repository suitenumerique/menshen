"""Target: core API authentication."""

import logging

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

User = get_user_model()


class TokenExchangeAuthentication(OIDCAuthentication):
    """Token Exchange based authentication."""

    def authenticate(self, request):
        access_token = self.get_access_token(request)
        logger.info(f"authenticate -> {access_token=}")

        # Introspect the token
        token_exchange_auth = HTTPBasicAuth(
            settings.OIDC_TX_CLIENT_ID, settings.OIDC_TX_CLIENT_SECRET
        )
        token_introspection_payload = {"token": access_token}
        response = requests.post(
            settings.OIDC_TX_INTROSPECTION_ENDPOINT,
            json=token_introspection_payload,
            auth=token_exchange_auth,
        )
        user_info = response.json()
        logger.info(f"Introspection: {user_info=}")
        response.raise_for_status()

        # Get user
        user = User.objects.get(email=user_info["sub"])

        return user, access_token
