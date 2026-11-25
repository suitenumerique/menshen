"""Menshen: admin tests for the token_exchange application."""

import re
from uuid import uuid4

import pytest

from token_exchange.factories import (
    ExchangedTokenFactory,
    IdentityProviderCredentialsFactory,
    IdentityProviderFactory,
    ServiceProviderFactory,
)
from token_exchange.models import (
    IdentityProviderCredentials,
    ServiceProviderCredentials,
    TokenExchangeRule,
)


@pytest.mark.parametrize("use_special_chars", [True, False])
def test_service_provider_credentials_admin(admin_client, settings, use_special_chars):
    """Test new client credentials creation using Django admin."""
    settings.TOKEN_EXCHANGE_CLIENT_SECRET_USE_SPECIAL_CHARS = use_special_chars
    service_provider = ServiceProviderFactory.create()

    # No credentials should be associated
    assert ServiceProviderCredentials.objects.filter(service_provider=service_provider).count() == 0

    response = admin_client.post(
        "/admin/token_exchange/serviceprovidercredentials/add/",
        {
            "service_provider": service_provider.id,
            "client_id": "foo",
            "allowed_origins": "",
            "is_active": "on",
        },
        follow=True,
    )
    assert response.status_code == 200

    # A message with the client secret should be displayed
    assert any(
        re.match(r"Generated client_secret: .* \(will only be displayed once\)", m)
        for m in [str(message) for message in response.context["messages"]]
    )

    # And credentials with client secret should have been created
    credentials = ServiceProviderCredentials.objects.filter(service_provider=service_provider).get()
    assert credentials.client_id == "foo"
    assert isinstance(credentials.client_secret, str)
    assert len(credentials.client_secret)


@pytest.mark.django_db
def test_exchanged_token_admin_search_by_raw_token(admin_client):
    """Test searching exchanged tokens by their raw (unhashed) value in admin."""
    raw_token = str(uuid4())
    exchanged_token = ExchangedTokenFactory.create(raw_token=raw_token)

    response = admin_client.get(
        "/admin/token_exchange/exchangedtoken/",
        {"q": raw_token},
    )
    assert response.status_code == 200
    results = list(response.context["cl"].queryset)
    assert exchanged_token in results

    # Unknown token
    response = admin_client.get(
        "/admin/token_exchange/exchangedtoken/",
        {"q": "unknown-token"},
    )
    assert response.status_code == 200
    assert not list(response.context["cl"].queryset)


def _token_exchange_rule_admin_form_data(source_service, target_service, duration):
    """Build the TokenExchangeRule admin add form data."""
    data = {
        "source_service": source_service.id,
        "target_service": target_service.id,
        "exchanged_token_duration": duration,
        "is_active": "on",
    }
    for prefix in ("scope_grants", "action_permissions"):
        data |= {
            f"{prefix}-TOTAL_FORMS": "0",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
    return data


@pytest.mark.parametrize(("duration", "seconds"), [("00:01:40", 100), ("00:00:01", 1)])
def test_token_exchange_rule_admin_valid_duration(admin_client, settings, duration, seconds):
    """Test the TokenExchangeRule admin accepts a duration within the allowed range."""
    settings.TOKEN_EXCHANGE_MAX_EXPIRES_IN = 100
    source_service, target_service = ServiceProviderFactory.create_batch(2)

    response = admin_client.post(
        "/admin/token_exchange/tokenexchangerule/add/",
        _token_exchange_rule_admin_form_data(source_service, target_service, duration),
    )

    assert response.status_code == 302
    rule = TokenExchangeRule.objects.get(
        source_service=source_service, target_service=target_service
    )
    assert rule.exchanged_token_duration.total_seconds() == seconds


@pytest.mark.parametrize("duration", ["00:01:41", "00:00:00", "-00:00:01"])
def test_token_exchange_rule_admin_invalid_duration(admin_client, settings, duration):
    """Test the TokenExchangeRule admin refuses a duration out of the allowed range."""
    settings.TOKEN_EXCHANGE_MAX_EXPIRES_IN = 100
    source_service, target_service = ServiceProviderFactory.create_batch(2)

    response = admin_client.post(
        "/admin/token_exchange/tokenexchangerule/add/",
        _token_exchange_rule_admin_form_data(source_service, target_service, duration),
    )

    assert response.status_code == 200
    assert "exchanged_token_duration" in response.context["adminform"].form.errors
    assert not TokenExchangeRule.objects.filter(
        source_service=source_service, target_service=target_service
    ).exists()


def _identity_provider_credentials_admin_form_data(identity_provider, **kwargs):
    """Build the IdentityProviderCredentials admin form data."""
    return {
        "identity_provider": identity_provider.id,
        "client_id": "menshen",
        "client_secret": "",
        "private_key": "",
        "is_active": "on",
    } | kwargs


@pytest.mark.django_db
def test_identity_provider_admin_with_credentials_inline(admin_client):
    """Test creating an identity provider with its credentials using Django admin."""
    response = admin_client.post(
        "/admin/token_exchange/identityprovider/add/",
        {
            "name": "ProConnect",
            "issuer": "https://idp.example.com",
            "credentials-TOTAL_FORMS": "1",
            "credentials-INITIAL_FORMS": "0",
            "credentials-MIN_NUM_FORMS": "0",
            "credentials-MAX_NUM_FORMS": "1000",
            "credentials-0-client_id": "menshen",
            "credentials-0-client_secret": "s3cr3t",
            "credentials-0-private_key": "",
            "credentials-0-is_active": "on",
        },
    )
    assert response.status_code == 302

    credentials = IdentityProviderCredentials.objects.get(identity_provider__name="ProConnect")
    assert credentials.identity_provider.issuer == "https://idp.example.com"
    assert credentials.client_id == "menshen"
    assert credentials.client_secret == "s3cr3t"


@pytest.mark.django_db
def test_identity_provider_credentials_admin_add(admin_client):
    """Test identity provider credentials creation requires a client secret."""
    identity_provider = IdentityProviderFactory.create()
    url = "/admin/token_exchange/identityprovidercredentials/add/"

    response = admin_client.post(
        url, _identity_provider_credentials_admin_form_data(identity_provider)
    )
    assert response.status_code == 200
    assert "client_secret" in response.context["adminform"].form.errors
    assert not IdentityProviderCredentials.objects.exists()

    response = admin_client.post(
        url,
        _identity_provider_credentials_admin_form_data(
            identity_provider, client_secret="s3cr3t", private_key="pem"
        ),
    )
    assert response.status_code == 302
    credentials = IdentityProviderCredentials.objects.get(identity_provider=identity_provider)
    assert credentials.client_secret == "s3cr3t"
    assert credentials.private_key == "pem"


@pytest.mark.django_db
def test_identity_provider_credentials_admin_secrets_not_rendered(admin_client):
    """Test identity provider credentials secrets are never displayed in the admin."""
    credentials = IdentityProviderCredentialsFactory.create(
        client_secret="client-s3cr3t", private_key="private-s3cr3t"
    )

    for url in (
        f"/admin/token_exchange/identityprovidercredentials/{credentials.pk}/change/",
        f"/admin/token_exchange/identityprovider/{credentials.identity_provider.pk}/change/",
    ):
        response = admin_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "client-s3cr3t" not in content
        assert "private-s3cr3t" not in content


@pytest.mark.django_db
def test_identity_provider_credentials_admin_change(admin_client):
    """Test empty secrets are left unchanged when editing credentials."""
    credentials = IdentityProviderCredentialsFactory.create(
        client_secret="client-s3cr3t", private_key="private-s3cr3t"
    )
    url = f"/admin/token_exchange/identityprovidercredentials/{credentials.pk}/change/"

    response = admin_client.post(
        url,
        _identity_provider_credentials_admin_form_data(
            credentials.identity_provider, client_id="new-client-id"
        ),
    )
    assert response.status_code == 302
    credentials.refresh_from_db()
    assert credentials.client_id == "new-client-id"
    assert credentials.client_secret == "client-s3cr3t"
    assert credentials.private_key == "private-s3cr3t"

    response = admin_client.post(
        url,
        _identity_provider_credentials_admin_form_data(
            credentials.identity_provider, client_secret="new-s3cr3t"
        ),
    )
    assert response.status_code == 302
    credentials.refresh_from_db()
    assert credentials.client_secret == "new-s3cr3t"
    assert credentials.private_key == "private-s3cr3t"


@pytest.mark.django_db
def test_identity_provider_credentials_admin_make_inactive(admin_client):
    """Test the identity provider credentials inactivation admin action."""
    credentials = IdentityProviderCredentialsFactory.create()

    response = admin_client.post(
        "/admin/token_exchange/identityprovidercredentials/",
        {"action": "make_inactive", "_selected_action": [credentials.pk]},
    )
    assert response.status_code == 302
    credentials.refresh_from_db()
    assert not credentials.is_active


@pytest.mark.django_db
def test_exchanged_token_admin_identity_fields(admin_client):
    """Test exchanged token identity fields are displayed and searchable in the admin."""
    exchanged_token = ExchangedTokenFactory.create(
        subject_iss="https://idp.example.com", target_sub="target-sub-42"
    )

    response = admin_client.get(
        f"/admin/token_exchange/exchangedtoken/{exchanged_token.pk}/change/"
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "https://idp.example.com" in content
    assert "target-sub-42" in content

    response = admin_client.get("/admin/token_exchange/exchangedtoken/", {"q": "target-sub-42"})
    assert response.status_code == 200
    assert list(response.context["cl"].queryset) == [exchanged_token]
