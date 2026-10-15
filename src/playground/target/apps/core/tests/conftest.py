"""Target: test fixtures for the core application."""

import pytest
from rest_framework.test import APIClient

from apps.core.models import PlaygroundUser

from .constants import USER_EMAIL, USER_SUB


@pytest.fixture(autouse=True)
def user(db) -> PlaygroundUser:
    """Create a playground user matching the introspected token subject."""
    return PlaygroundUser.objects.create_user(sub=USER_SUB, email=USER_EMAIL)


@pytest.fixture
def api_client() -> APIClient:
    """Get a DRF API client."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer exchanged-token")
    return client
