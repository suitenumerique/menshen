"""Menshen: views tests for the token_exchange application."""

import base64
import logging
from datetime import UTC, datetime, timedelta
from unittest import mock
from uuid import uuid4

import pytest
from ninja.testing import TestClient
from requests import HTTPError

from token_exchange.api import api
from token_exchange.enums import TokenType
from token_exchange.factories import (
    ExchangedTokenFactory,
    ServiceProviderCredentialsFactory,
    ServiceProviderFactory,
    TokenExchangeRuleFactory,
)
from token_exchange.models import ExchangedToken, TokenTypeChoices
from token_exchange.services.token import TokenGenerator


@pytest.mark.parametrize(
    "endpoint",
    [
        "/exchange/",
        "/introspect/",
        "/revoke/",
    ],
)
@pytest.mark.django_db
def test_exchange_view_auth_without_credentials(endpoint):
    """Test the TokenExchangeView authentication without submitting credentials."""
    client = TestClient(api)
    response = client.post(endpoint, data={})
    assert response.status_code == 401  # UNAUTHORIZED


@pytest.mark.parametrize(
    "endpoint",
    [
        "/exchange/",
        "/introspect/",
        "/revoke/",
    ],
)
@pytest.mark.django_db
def test_exchange_view_auth_with_invalid_credentials(endpoint):
    """Test the TokenExchangeView authentication with invalid credentials."""
    client = TestClient(api)
    encoded_credentials = base64.b64encode(bytes("foo:bar", encoding="utf-8"))
    response = client.post(
        endpoint,
        headers={"Authorization": "Basic " + encoded_credentials.decode()},
        data={},
    )
    assert response.status_code == 401  # UNAUTHORIZED


@pytest.mark.parametrize(
    "endpoint",
    [
        "/exchange/",
        "/introspect/",
        "/revoke/",
    ],
)
@pytest.mark.django_db
def test_exchange_view_auth_with_inactive_service(endpoint):
    """Test the TokenExchangeView authentication for an inactive service provider."""
    client = TestClient(api)

    # Create the inactive service
    service_provider = ServiceProviderFactory.create(audience_id="test:inactive-service")
    credentials = ServiceProviderCredentialsFactory(
        service_provider=service_provider, is_active=False
    )

    encoded_credentials = base64.b64encode(
        bytes(f"{credentials.client_id}:{credentials.client_secret}", encoding="utf-8")
    )
    response = client.post(
        endpoint,
        headers={"Authorization": "Basic " + encoded_credentials.decode()},
        data={},
    )
    assert response.status_code == 401  # UNAUTHORIZED


def test_exchange_view_invalid_content_type(source_api_client):
    """Test the TokenExchangeView with an invalid request content-type."""
    response = source_api_client.post("/exchange/", json={"token": "invalid"})
    assert response.status_code == 422  # UNPROCESSABLE_ENTITY
    assert response.json() == {
        "detail": [
            {"type": "missing", "loc": ["form", "subject_token"], "msg": "Field required"},
            {"type": "missing", "loc": ["form", "subject_token_type"], "msg": "Field required"},
            {"type": "missing", "loc": ["form", "grant_type"], "msg": "Field required"},
        ]
    }


def test_exchange_view_invalid_payload(source_api_client):
    """Test the TokenExchangeView with a valid content-type but an invalid payload."""
    response = source_api_client.post(
        "/exchange/",
        data=b"token=invalid",
        content_type="application/json",
    )
    assert response.status_code == 422  # UNPROCESSABLE_ENTITY
    assert response.json() == {
        "detail": [
            {"type": "missing", "loc": ["form", "subject_token"], "msg": "Field required"},
            {"type": "missing", "loc": ["form", "subject_token_type"], "msg": "Field required"},
            {"type": "missing", "loc": ["form", "grant_type"], "msg": "Field required"},
        ]
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (
            {},
            {
                "type": "missing",
                "loc": ["form", "subject_token"],
                "msg": "Field required",
            },
        ),
        (
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": None,
                "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "audience": "service:target",
            },
            {
                "type": "missing",
                "loc": ["form", "subject_token"],
                "msg": "Field required",
            },
        ),
        (
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": "",
                "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "audience": "service:target",
            },
            {
                "type": "string_too_short",
                "loc": ["form", "subject_token"],
                "msg": "String should have at least 1 character",
                "ctx": {"min_length": 1},
            },
        ),
        (
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": "",
                "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
                "audience": "service:target",
            },
            {
                "type": "string_too_short",
                "loc": ["form", "subject_token"],
                "msg": "String should have at least 1 character",
                "ctx": {"min_length": 1},
            },
        ),
    ],
)
def test_exchange_view_invalid_token(source_api_client, payload, error):
    """Test the TokenExchangeView with an invalid access/JWT token."""
    response = source_api_client.post("/exchange/", data=payload)
    assert response.status_code == 422  # UNPROCESSABLE_ENTITY
    assert error in response.json()["detail"]


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
        response = source_api_client.post("/exchange/", data=payload)
    assert response.status_code == 400  # BAD_REQUEST
    assert response.json() == {
        "detail": "Only unknown audience(s) requested.",
        "code": "invalid_target",
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
        response = source_api_client.post("/exchange/", data=payload)
    assert response.status_code == 400  # BAD_REQUEST
    assert response.json() == {"detail": "Unknown audience(s) requested.", "code": "invalid_target"}
    assert "Unknown audience(s) requested: foo" in caplog.messages


@pytest.mark.django_db
def test_exchange_view_with_introspection_error(source_api_client, monkeypatch, settings):
    """Test the TokenExchangeView when the subject token introspection fails."""
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": "fake-access-token",
        "subject_token_type": TokenType.ACCESS_TOKEN,
        "audience": "service:target",
    }

    # HTTPError
    monkeypatch.setattr(
        f"{settings.OIDC_RS_BACKEND_CLASS}.get_user_info_with_introspection",
        mock.Mock(side_effect=HTTPError("Connection fails")),
    )
    response = source_api_client.post("/exchange/", data=payload)
    assert response.status_code == 422  # UNPROCESSABLE_ENTITY
    assert response.json() == {
        "detail": "Failed to introspect subject token.",
        "code": "invalid_introspection",
    }


@pytest.mark.django_db
def test_exchange_view_with_inactive_rule(source_api_client, source_service, caplog):
    """Test the TokenExchangeView when the token points to an inactive service rule."""
    other_service = ServiceProviderFactory(audience_id="service:other")

    # The inactive rule
    TokenExchangeRuleFactory.create(
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
        response = source_api_client.post("/exchange/", data=payload)
    assert response.status_code == 400  # BAD_REQUEST
    assert response.json() == {"detail": "Unknown audience(s) requested.", "code": "invalid_target"}
    assert "Unknown audience(s) requested: service:other" in caplog.messages


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("subject_token", "subject_token_type"),
    [
        # Could be fake since it won't be introspected
        ("fake-access-token", TokenType.ACCESS_TOKEN),
        ("{}", TokenType.JWT),
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
    # response = source_api_client.post("/exchange/", payload)
    response = source_api_client.post("/exchange/", data=payload)
    assert response.status_code == 200  # OK
    exchanged_token = response.json()
    assert "access_token" in exchanged_token
    assert len(exchanged_token["access_token"]) > 1
    assert exchanged_token["issued_token_type"] == "urn:ietf:params:oauth:token-type:access_token"
    assert "target:read" in exchanged_token["scope"]
    assert {
        "audience_id": "service:target",
        "scope": "target:read",
        "throttle": None,
    } in exchanged_token["grants"]
    assert {
        "audience_id": "service:target",
        "scope": "target:write",
        "throttle": None,
    } in exchanged_token["grants"]

    # Check saved token grants
    saved_exchanged_token = ExchangedToken.objects.get()
    assert saved_exchanged_token.token == exchanged_token["access_token"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "requested_token_type",
    [TokenType.ACCESS_TOKEN, TokenType.JWT],
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
    response = source_api_client.post("/exchange/", data=payload)
    assert response.status_code == 200  # OK
    exchanged_token = response.json()
    assert "access_token" in exchanged_token
    assert len(exchanged_token["access_token"]) > 1
    assert exchanged_token["issued_token_type"] == requested_token_type
    assert "target:read" in exchanged_token["scope"]
    assert {
        "audience_id": "service:target",
        "scope": "target:read",
        "throttle": None,
    } in exchanged_token["grants"]
    assert {
        "audience_id": "service:target",
        "scope": "target:write",
        "throttle": None,
    } in exchanged_token["grants"]

    # Check saved token grants
    saved_exchanged_token = ExchangedToken.objects.get()
    assert saved_exchanged_token.token == exchanged_token["access_token"]


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
    response = source_api_client.post("/exchange/", data=payload)
    assert response.status_code == 422  # UNPROCESSABLE_ENTITY
    payload = response.json()
    assert {
        "type": "enum",
        "loc": ["form", "requested_token_type"],
        "msg": (
            "Input should be 'urn:ietf:params:oauth:token-type:access_token' or "
            "'urn:ietf:params:oauth:token-type:jwt'"
        ),
        "ctx": {
            "expected": (
                "'urn:ietf:params:oauth:token-type:access_token' or "
                "'urn:ietf:params:oauth:token-type:jwt'"
            )
        },
    } in payload["detail"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (
            {},
            {
                "type": "missing",
                "loc": [
                    "form",
                    "token",
                ],
                "msg": "Field required",
            },
        ),
        (
            {"token": None},
            {
                "type": "missing",
                "loc": [
                    "form",
                    "token",
                ],
                "msg": "Field required",
            },
        ),
        (
            {"token": ""},
            {
                "type": "string_pattern_mismatch",
                "loc": [
                    "form",
                    "token",
                ],
                "msg": "String should match pattern '^\\s*\\S{32,}\\s*$'",
                "ctx": {"pattern": "^\\s*\\S{32,}\\s*$"},
            },
        ),
        (
            {"token": "0123456789"},
            {
                "type": "string_pattern_mismatch",
                "loc": [
                    "form",
                    "token",
                ],
                "msg": "String should match pattern '^\\s*\\S{32,}\\s*$'",
                "ctx": {"pattern": "^\\s*\\S{32,}\\s*$"},
            },
        ),
    ],
)
def test_introspect_view_without_token(target_api_client, payload, error):
    """Test the TokenIntrospectView with no, empty or too short exchange token."""
    response = target_api_client.post("/introspect/", data=payload)
    assert response.status_code == 422  # UNPROCESSABLE_ENTITY
    assert error in response.json()["detail"]


@pytest.mark.django_db
def test_introspect_view_with_unknown_token(target_api_client, caplog):
    """Test the TokenIntrospectView with no or empty exchange token."""
    with caplog.at_level(logging.INFO):
        response = target_api_client.post("/introspect/", data={"token": uuid4().hex})
    assert response.status_code == 200  # OK
    assert response.json() == {"active": False}
    assert "Token not found." in caplog.messages


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
def test_introspect_view_invalid_token(  # noqa: PLR0913
    target_api_client,
    target_service,
    caplog,
    token_type,
    expires_at,
    revoked_at,
):
    """Test the TokenIntrospectView with an invalid exchange token (expired or revoked)."""
    exchanged_token = ExchangedTokenFactory(
        expires_at=expires_at,
        revoked_at=revoked_at,
        token_type=token_type,
        audiences=[target_service.audience_id],
    )
    with caplog.at_level(logging.INFO):
        response = target_api_client.post(
            "/introspect/",
            data={"token": exchanged_token.token},
        )
    assert response.status_code == 200  # OK
    assert response.json() == {"active": False}
    assert (
        f"Token is invalid: token_jti={exchanged_token.subject_token_jti}, "
        f"type={token_type}, kid=N/A"
    ) in caplog.messages


@pytest.mark.django_db
def test_introspect_view_invalid_jwt_signature(target_api_client, target_service, caplog):
    """Test the TokenIntrospectView with a badly signed JWT exchange token."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.JWT, audiences=[target_service.audience_id]
    )
    with (
        caplog.at_level(logging.INFO),
        mock.patch.object(TokenGenerator, "verify_jwt", side_effect=ValueError("wrong signature")),
    ):
        response = target_api_client.post(
            "/introspect/",
            data={"token": exchanged_token.token},
        )
    assert response.status_code == 200  # OK
    assert response.json() == {"active": False}
    assert "JWT signature verification failed (wrong signature)" in caplog.messages


@pytest.mark.django_db
def test_introspect_view_invalid_audience(target_api_client, caplog):
    """Test the TokenIntrospectView with an invalid audience from requesting service."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.JWT, audiences=["service:foo"]
    )
    with caplog.at_level(logging.INFO):
        response = target_api_client.post("/introspect/", data={"token": exchanged_token.token})
    assert response.status_code == 200  # OK
    assert response.json() == {"active": False}
    assert (
        "'service:target' service tried to act on an exchanged token that is beyond its audience"
    ) in caplog.messages


@pytest.mark.django_db
@pytest.mark.parametrize("token_type_hint", ["bogus", "refresh"])
def test_introspect_view_introspection_with_wrong_token_type_hint(
    target_api_client, target_service, token_type_hint, caplog
):
    """Test the TokenIntrospectView instrospection with a falsy token type hint."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN, audiences=[target_service.audience_id]
    )
    with caplog.at_level(logging.INFO):
        response = target_api_client.post(
            "/introspect/",
            data={"token": exchanged_token.token, "token_type_hint": token_type_hint},
        )
    assert response.status_code == 200  # OK
    introspected_token = response.json()
    # the token exists  and is active (token type hint should be ignored)
    assert introspected_token["active"]


@pytest.mark.django_db
def test_introspect_view_introspection_with_token_type_hint(
    target_api_client, target_service, caplog
):
    """Test the TokenIntrospectView instrospection."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN, audiences=[target_service.audience_id]
    )
    with caplog.at_level(logging.INFO):
        response = target_api_client.post(
            "/introspect/",
            data={"token": exchanged_token.token, "token_type_hint": "access_token"},
        )
    assert response.status_code == 200  # OK
    introspected_token = response.json()
    assert introspected_token["active"]
    assert (
        f"Token introspected (active): token_jti={exchanged_token.subject_token_jti}, "
        f"type={exchanged_token.token_type}, kid={exchanged_token.jwt_kid or 'N/A'}"
        in caplog.messages
    )


@pytest.mark.django_db
def test_introspect_view_introspection(target_api_client, target_service, caplog):
    """Test the TokenIntrospectView instrospection."""
    exchanged_token = ExchangedTokenFactory(
        token_type=TokenTypeChoices.ACCESS_TOKEN, audiences=[target_service.audience_id]
    )
    with caplog.at_level(logging.INFO):
        response = target_api_client.post(
            "/introspect/",
            data={"token": exchanged_token.token},
        )
    assert response.status_code == 200  # OK
    assert (
        f"Token introspected (active): token_jti={exchanged_token.subject_token_jti}, "
        f"type={exchanged_token.token_type}, kid={exchanged_token.jwt_kid or 'N/A'}"
        in caplog.messages
    )
    introspected_token = response.json()
    assert introspected_token["active"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (
            {},
            {
                "type": "missing",
                "loc": [
                    "form",
                    "token",
                ],
                "msg": "Field required",
            },
        ),
        (
            {"token": None},
            {
                "type": "missing",
                "loc": [
                    "form",
                    "token",
                ],
                "msg": "Field required",
            },
        ),
        (
            {"token": ""},
            {
                "type": "string_pattern_mismatch",
                "loc": [
                    "form",
                    "token",
                ],
                "msg": "String should match pattern '^\\s*\\S{32,}\\s*$'",
                "ctx": {"pattern": "^\\s*\\S{32,}\\s*$"},
            },
        ),
        (
            {"token": "0123456789"},
            {
                "type": "string_pattern_mismatch",
                "loc": [
                    "form",
                    "token",
                ],
                "msg": "String should match pattern '^\\s*\\S{32,}\\s*$'",
                "ctx": {"pattern": "^\\s*\\S{32,}\\s*$"},
            },
        ),
    ],
)
def test_revocation_view_without_token(source_api_client, payload, error):
    """Test the TokenRevocationView instrospection with no or empty token."""
    response = source_api_client.post("/revoke/", data=payload)
    assert response.status_code == 422  # UNPROCESSABLE_ENTITY
    assert error in response.json()["detail"]


@pytest.mark.django_db
def test_revocation_view_with_unknown_token(source_api_client, caplog):
    """Test the TokenRevocationView instrospection with no or empty token."""
    with caplog.at_level(logging.INFO):
        response = source_api_client.post("/revoke/", data={"token": uuid4().hex})
    assert response.status_code == 200  # OK
    assert not len(response.content)
    assert "Token revocation failed (not found)." in caplog.messages


@pytest.mark.django_db
def test_revocation_view(target_api_client, target_service, caplog):
    """Test the TokenRevocationView revocation."""
    exchanged_token = ExchangedTokenFactory.create(
        token_type=TokenTypeChoices.ACCESS_TOKEN,
        audiences=[target_service.audience_id],
    )

    # Get token from database
    assert not exchanged_token.is_revoked()

    before = datetime.now(tz=UTC)
    with caplog.at_level(logging.INFO):
        response = target_api_client.post("/revoke/", data={"token": exchanged_token.token})
    assert response.status_code == 200  # OK
    assert not len(response.content)
    assert (
        "Token revoked: "
        f"token_jti={exchanged_token.subject_token_jti}, "
        f"sub={exchanged_token.subject_sub}, "
        f"email={exchanged_token.subject_email}, "
        f"type={exchanged_token.token_type}, "
        f"audiences={exchanged_token.audiences}"
    ) in caplog.messages

    # revoked_at field should have been updated
    exchanged_token.refresh_from_db()
    assert exchanged_token.is_revoked()
    assert exchanged_token.revoked_at > before
