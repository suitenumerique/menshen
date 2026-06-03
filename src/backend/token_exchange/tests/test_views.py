"""Menshen: views tests for the token_exchange application."""

import logging
from datetime import UTC, datetime, timedelta
from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from token_exchange.enums import TokenTypeEnum
from token_exchange.factories import (
    ExchangedTokenFactory,
    ServiceProviderFactory,
    TokenExchangeRuleFactory,
)
from token_exchange.models import ExchangedToken, ServiceProvider, TokenTypeChoices
from token_exchange.token_generator import TokenGenerator


@pytest.mark.django_db
def test_exchange_view_auth():
    """Test the TokenExchangeView authentication."""
    client = APIClient()
    response = client.post("/auth/token/exchange/", {}, content_type="application/json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": None,
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "audience": "service:target",
        },
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": "",
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "audience": "service:target",
        },
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": "",
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
            "audience": "service:target",
        },
    ],
)
def test_exchange_view_invalid_token(source_api_client, payload):
    """Test the TokenExchangeView with an invalid access/JWT token."""
    response = source_api_client.post(
        "/auth/token/exchange/", payload, content_type="application/json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "invalid_request"


@pytest.mark.django_db
def test_exchange_view_with_only_unknown_audience(source_api_client, caplog):
    """Test the TokenExchangeView when the token points to an unknown audience."""
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        # Could be fake since it won't be introspected
        "subject_token": "{}",
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": "foo",
    }
    with caplog.at_level(logging.INFO):
        response = source_api_client.post(
            "/auth/token/exchange/", payload, content_type="application/json"
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "errors": [
            {
                "attr": None,
                "code": "invalid_target",
                "detail": "Only unknown audience(s) requested: foo",
            }
        ],
        "type": "client_error",
    }
    assert "Only unknown audience(s) requested: foo" in caplog.messages


@pytest.mark.django_db
def test_exchange_view_with_unknown_audience(source_api_client, caplog):
    """Test the TokenExchangeView when the token points to an unknown audience."""
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        # Could be fake since it won't be introspected
        "subject_token": "{}",
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": "foo service:target",
    }
    with caplog.at_level(logging.INFO):
        response = source_api_client.post(
            "/auth/token/exchange/", payload, content_type="application/json"
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "errors": [
            {
                "attr": None,
                "code": "invalid_target",
                "detail": "Unknown audience(s) requested: foo",
            }
        ],
        "type": "client_error",
    }
    assert "Unknown audience(s) requested: foo" in caplog.messages


@pytest.mark.django_db
def test_exchange_view_with_inactive_rule(source_api_client, caplog):
    """Test the TokenExchangeView when the token points to an inactive service rule."""
    source_service = ServiceProvider.objects.get(audience_id="service:source")
    other_service = ServiceProviderFactory(audience_id="service:other")
    inactive_rule = TokenExchangeRuleFactory.create(
        source_service=source_service, target_service=other_service, is_active=False
    )
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        # Could be fake since it won't be introspected
        "subject_token": "{}",
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": "service:target service:other",
    }
    with caplog.at_level(logging.INFO):
        response = source_api_client.post(
            "/auth/token/exchange/", payload, content_type="application/json"
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "errors": [
            {
                "attr": None,
                "code": "invalid_target",
                "detail": f"Some rules are inactive: {inactive_rule.pk}",
            }
        ],
        "type": "client_error",
    }
    assert f"Some rules are inactive: {inactive_rule.pk}" in caplog.messages


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("subject_token", "subject_token_type"),
    [
        # Could be fake since it won't be introspected
        ("fake-access-token", TokenTypeEnum.ACCESS_TOKEN),
        ("{}", TokenTypeEnum.JWT),
    ],
)
def test_exchange_view_with_subject_token_type(
    subject_token, subject_token_type, source_api_client
):
    """Test the TokenExchangeView with different subject tokens."""
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": subject_token,
        "subject_token_type": subject_token_type,
        "audience": "service:target",
    }
    # Create an exchange token
    response = source_api_client.post(
        "/auth/token/exchange/", payload, content_type="application/json"
    )
    assert response.status_code == status.HTTP_200_OK
    exchanged_token = response.json()
    assert "access_token" in exchanged_token
    assert len(exchanged_token["access_token"]) > 1
    assert exchanged_token["issued_token_type"] == "urn:ietf:params:oauth:token-type:access_token"
    assert "target:read" in exchanged_token["scope"]

    # Check saved token grants
    saved_exchanged_token = ExchangedToken.objects.get()
    assert {
        "audience_id": "service:target",
        "scope": "target:read",
    } in saved_exchanged_token.grants
    assert {
        "audience_id": "service:target",
        "scope": "target:write",
    } in saved_exchanged_token.grants


@pytest.mark.django_db
@pytest.mark.parametrize(
    "requested_token_type",
    [TokenTypeEnum.ACCESS_TOKEN, TokenTypeEnum.JWT],
)
def test_exchange_view_with_requested_token_type(requested_token_type, source_api_client):
    """Test the TokenExchangeView with different requested token types."""
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": "foo",
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": "service:target",
        "requested_token_type": requested_token_type,
    }
    # Create an exchange token
    response = source_api_client.post(
        "/auth/token/exchange/", payload, content_type="application/json"
    )
    assert response.status_code == status.HTTP_200_OK
    exchanged_token = response.json()
    assert "access_token" in exchanged_token
    assert len(exchanged_token["access_token"]) > 1
    assert exchanged_token["issued_token_type"] == requested_token_type
    assert "target:read" in exchanged_token["scope"]

    # Check saved token grants
    saved_exchanged_token = ExchangedToken.objects.get()
    assert {
        "audience_id": "service:target",
        "scope": "target:read",
    } in saved_exchanged_token.grants
    assert {
        "audience_id": "service:target",
        "scope": "target:write",
    } in saved_exchanged_token.grants


@pytest.mark.django_db
def test_exchange_view_with_requested_refresh_token_type(source_api_client):
    """Test the TokenExchangeView with requested refresh token type (not implemented)."""
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": "foo",
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": "service:target",
        "requested_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
    }
    # Create an exchange token
    response = source_api_client.post(
        "/auth/token/exchange/", payload, content_type="application/json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload["error"] == "invalid_request"
    assert (
        "Invalid enum value 'urn:ietf:params:oauth:token-type:refresh_token'"
        " - at `$.requested_token_type`"
    ) in payload["error_description"]


@pytest.mark.django_db
def test_instrospect_view_auth():
    """Test the TokenIntrospectView authentication."""
    client = APIClient()
    response = client.post("/auth/token/introspect/", {}, content_type="application/json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [{}, {"token": None}, {"token": ""}])
def test_introspect_view_without_token(target_api_client, payload):
    """Test the TokenIntrospectView with no or empty exchange token."""
    response = target_api_client.post(
        "/auth/token/introspect/", payload, content_type="application/json"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"active": False}


@pytest.mark.django_db
def test_introspect_view_with_unknown_token(target_api_client, caplog):
    """Test the TokenIntrospectView with no or empty exchange token."""
    with caplog.at_level(logging.INFO):
        response = target_api_client.post(
            "/auth/token/introspect/", {"token": uuid4().hex}, content_type="application/json"
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"active": False}
    assert "Token introspected: token not found, active=False" in caplog.messages


@pytest.mark.django_db
@pytest.mark.parametrize("token_type", TokenTypeChoices.values)
@pytest.mark.parametrize(
    (
        "expires_at",
        "revoked_at",
    ),
    [
        (datetime.now(tz=UTC) - timedelta(hours=1), None),
        (datetime.now(tz=UTC) - timedelta(hours=1), datetime.now(tz=UTC) - timedelta(minutes=1)),
        (datetime.now(tz=UTC) + timedelta(hours=1), datetime.now(tz=UTC) - timedelta(minutes=1)),
    ],
)
def test_introspect_view_invalid_token(
    target_api_client, caplog, token_type, expires_at, revoked_at
):
    """Test the TokenIntrospectView with an invalid exchange token (expired or revoked)."""
    exchanged_token = ExchangedTokenFactory(
        expires_at=expires_at,
        revoked_at=revoked_at,
        token_type=token_type,
    )
    with caplog.at_level(logging.INFO):
        response = target_api_client.post(
            "/auth/token/introspect/",
            {"token": exchanged_token.token},
            content_type="application/json",
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"active": False}
    assert (
        f"Token introspected: token_jti={exchanged_token.subject_token_jti}, "
        f"active=False, format={token_type} [invalid]"
    ) in caplog.messages


@pytest.mark.django_db
def test_introspect_view_invalid_jwt_signature(target_api_client, caplog):
    """Test the TokenIntrospectView with a badly signed JWT exchange token."""
    exchanged_token = ExchangedTokenFactory(token_type=TokenTypeChoices.JWT)
    with (
        caplog.at_level(logging.INFO),
        mock.patch.object(TokenGenerator, "verify_jwt", side_effect=ValueError("wrong signature")),
    ):
        response = target_api_client.post(
            "/auth/token/introspect/",
            {"token": exchanged_token.token},
            content_type="application/json",
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"active": False}
    assert (
        "Token introspected: JWT signature verification failed: wrong signature" in caplog.messages
    )


@pytest.mark.django_db
def test_introspect_view_introspection(target_api_client, caplog):
    """Test the TokenIntrospectView instrospection."""
    exchanged_token = ExchangedTokenFactory(token_type=TokenTypeChoices.ACCESS_TOKEN)
    with caplog.at_level(logging.INFO):
        response = target_api_client.post(
            "/auth/token/introspect/",
            {"token": exchanged_token.token},
            content_type="application/json",
        )
    assert response.status_code == status.HTTP_200_OK
    assert (
        f"Token introspected: token_jti={exchanged_token.subject_token_jti}, active=True, "
        f"format={exchanged_token.token_type}, kid={exchanged_token.jwt_kid or 'N/A'}"
        in caplog.messages
    )
    introspected_token = response.json()
    assert introspected_token["active"]


@pytest.mark.django_db
def test_revocation_view_auth():
    """Test the TokenRevocationView authentication."""
    client = APIClient()
    response = client.post("/auth/token/revoke/", {}, content_type="application/json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [{}, {"token": None}, {"token": ""}])
def test_revocation_view_without_token(source_api_client, payload):
    """Test the TokenRevocationView instrospection with no or empty token."""
    response = source_api_client.post(
        "/auth/token/revoke/", payload, content_type="application/json"
    )
    assert response.status_code == status.HTTP_200_OK
    assert not len(response.content)


@pytest.mark.django_db
def test_revocation_view_with_unknown_token(source_api_client, caplog):
    """Test the TokenRevocationView instrospection with no or empty token."""
    with caplog.at_level(logging.INFO):
        response = source_api_client.post(
            "/auth/token/revoke/", {"token": uuid4().hex}, content_type="application/json"
        )
    assert response.status_code == status.HTTP_200_OK
    assert not len(response.content)
    assert "Token revocation attempted: token not found" in caplog.messages


@pytest.mark.django_db
def test_revocation_view(source_api_client, caplog):
    """Test the TokenRevocationView revocation."""
    exchanged_token = ExchangedTokenFactory(token_type=TokenTypeChoices.ACCESS_TOKEN)

    # Get token from database
    database_exchanged_token = ExchangedToken.objects.get(token=exchanged_token.token)
    assert database_exchanged_token.revoked_at is None

    before = datetime.now(tz=UTC)
    with caplog.at_level(logging.INFO):
        response = source_api_client.post(
            "/auth/token/revoke/", {"token": exchanged_token.token}, content_type="application/json"
        )
    assert response.status_code == status.HTTP_200_OK
    assert not len(response.content)
    assert (
        "Token revoked: "
        f"token_jti={exchanged_token.subject_token_jti}, "
        f"sub={exchanged_token.subject_sub}, "
        f"email={exchanged_token.subject_email}, "
        f"type={exchanged_token.token_type}, "
        f"audiences={exchanged_token.audiences}" in caplog.messages
    )

    # revoked_at field should have been updated
    database_exchanged_token.refresh_from_db()
    assert database_exchanged_token.revoked_at is not None
    assert database_exchanged_token.revoked_at > before
