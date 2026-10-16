"""Target: API tests for the core application."""

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.core.models import Item

from .constants import USER_EMAIL, USER_SUB

ITEMS_URL = "/external_api/items/"
ITEM_PAYLOAD = {"name": "Recording", "type": "video/mpeg", "size": 1024}
INTROSPECTION_URL = f"{settings.OIDC_TX_ROOT_URL}/auth/token/introspect/"


@pytest.mark.django_db
def test_create_item_with_write_scope_succeeds(api_client, responses):
    """An item can be created when the exchanged token grants the target:item:write scope."""
    responses.post(
        INTROSPECTION_URL,
        status=200,
        json={
            "active": True,
            "sub": USER_SUB,
            "email": USER_EMAIL,
            "scope": "target:item:write",
        },
    )

    response = api_client.post(ITEMS_URL, ITEM_PAYLOAD)

    assert response.status_code == 201
    assert Item.objects.count() == 1


@pytest.mark.parametrize("scope", ["openid target:item:read", None])
@pytest.mark.django_db
def test_create_item_without_write_scope_is_forbidden(api_client, responses, scope):
    """An item cannot be created when the exchanged token lacks the target:item:write scope."""
    responses.post(
        INTROSPECTION_URL,
        status=200,
        json={
            "active": True,
            "sub": USER_SUB,
            "email": USER_EMAIL,
            "scope": scope,
        },
    )

    response = api_client.post(ITEMS_URL, ITEM_PAYLOAD)

    assert response.status_code == 403
    assert Item.objects.count() == 0


@pytest.mark.django_db
def test_list_items_with_read_scope_succeeds(api_client, responses):
    """Items can be listed when the exchanged token grants the target:item:read scope."""
    responses.post(
        INTROSPECTION_URL,
        status=200,
        json={
            "active": True,
            "sub": USER_SUB,
            "email": USER_EMAIL,
            "scope": "openid target:item:read",
        },
    )

    response = api_client.get(ITEMS_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_list_items_without_read_scope_is_forbidden(api_client, responses):
    """Items cannot be listed when the exchanged token lacks the target:item:read scope."""
    responses.post(
        INTROSPECTION_URL,
        status=200,
        json={
            "active": True,
            "sub": USER_SUB,
            "email": USER_EMAIL,
            "scope": "target:item:write",
        },
    )

    response = api_client.get(ITEMS_URL)

    assert response.status_code == 403


@pytest.mark.django_db
def test_inactive_token_is_unauthorized(api_client, responses):
    """An inactive introspected token is rejected as unauthenticated."""
    responses.post(
        INTROSPECTION_URL,
        status=200,
        json={
            "active": False,
            "sub": USER_SUB,
            "email": USER_EMAIL,
            "scope": None,
        },
    )

    response = api_client.post(ITEMS_URL, ITEM_PAYLOAD)

    assert response.status_code == 401
    assert Item.objects.count() == 0


@pytest.mark.django_db
def test_unknown_user_is_unauthorized(api_client, responses):
    """A token issued for an unknown user is rejected as unauthenticated."""
    responses.post(
        INTROSPECTION_URL,
        status=200,
        json={
            "active": True,
            "sub": "unknown-sub",
            "email": "unknown@menshen.world",
            "scope": "openid target:item:write",
        },
    )

    response = api_client.post(ITEMS_URL, ITEM_PAYLOAD)

    assert response.status_code == 401
    assert Item.objects.count() == 0


@pytest.mark.django_db
def test_missing_token_is_unauthorized(responses):
    """A request without credentials is rejected without calling the introspection endpoint."""
    client = APIClient()
    response = client.post(ITEMS_URL, ITEM_PAYLOAD)

    assert response.status_code == 401
    assert Item.objects.count() == 0
    assert not responses.calls
