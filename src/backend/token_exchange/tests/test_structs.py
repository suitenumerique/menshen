"""Menshen: struct tests for the token_exchange application."""

import json
import secrets
from uuid import UUID

import msgspec
import pytest
from joserfc.jwt import ClaimsOption, JWTClaimsRegistry

from token_exchange.enums import (
    AllowedActorTokenTypeEnum,
    TokenExchangeResponseTokenType,
    TokenTypeEnum,
)
from token_exchange.structs import (
    BaseStruct,
    MenshenJWTClaims,
    TokenExchangeJWTActClaim,
    TokenExchangeJWTClaims,
    TokenExchangeRequest,
    TokenExchangeResponse,
    TokenRevocationRequest,
)


def test_basestruct_to_dict():
    """Test the BaseStruct `to_dict` method."""

    class Foo(BaseStruct):
        """Foo test class."""

        bar: str
        lol: str | None = None

    assert Foo(bar="bar").to_dict() == {"bar": "bar", "lol": None}

    class FooNoDefaults(BaseStruct, omit_defaults=True):
        """Foo test class."""

        bar: str
        lol: str | None = None

    assert FooNoDefaults(bar="bar").to_dict() == {"bar": "bar"}


def test_tokenexchangejwtclaims_struct():
    """Test the TokenExchangeJWTClaims struct."""
    # Test with only two fields
    claims = TokenExchangeJWTClaims(
        act=TokenExchangeJWTActClaim(sub="foo"),
        scope=["foo", "bar"],
    )
    assert claims.act is not None
    assert hasattr(claims.act, "sub")
    assert claims.act.sub == "foo"
    assert claims.scope == ["foo", "bar"]


def test_tokenexchangejwtclaims_nested_actor_claim_struct():
    """Test the TokenExchangeJWTClaims struct with a nested actor claim."""
    # Test with only two fields
    claims = TokenExchangeJWTClaims(
        act=TokenExchangeJWTActClaim(sub="foo", act=TokenExchangeJWTActClaim(sub="bar")),
        scope=["foo", "bar"],
    )
    assert claims.act is not None
    assert claims.act.sub == "foo"
    assert claims.act.act is not None
    assert claims.act.act.sub == "bar"
    assert claims.scope == ["foo", "bar"]


@pytest.mark.parametrize(
    ("claims", "match"),
    [
        ({}, "Missing required argument 'sub'"),
        ({"sub": "foo@bar.com"}, "Missing required argument 'aud'"),
        ({"sub": "foo@bar.com", "aud": ["foo.com", "bar.com"]}, "Missing required argument 'exp'"),
    ],
)
def test_menshenjwtclaims_struct_required_arguments(claims, match):
    """Test the MenshenJWTClaims struct required arguments."""
    with pytest.raises(TypeError, match=match):
        MenshenJWTClaims(**claims)


def test_menshenjwtclaims_struct_default_factories():
    """Test the MenshenJWTClaims struct default factories."""
    claims = MenshenJWTClaims(sub="foo@bar.com", aud=["foo.com"], exp=12)
    assert claims.iat > 0
    assert isinstance(claims.jti, UUID)

    # Ensure convertion cast jti UUID field to str
    claims_dict = claims.to_dict()
    assert isinstance(claims_dict["jti"], str)


def test_menshenjwtclaims_struct_to_jwt_claims_registry():
    """Test the MenshenJWTClaims struct to_jwt_claims_registy method."""
    # joserfc does not allow None in ClaimsOption.value, we think it's perfectly legit and thus
    # ignore typing issues deliberately.
    assert (
        MenshenJWTClaims.to_jwt_claims_registry().options
        == JWTClaimsRegistry(
            act=ClaimsOption(essential=False, value=None),  # ty: ignore
            scope=ClaimsOption(essential=False, value=None),  # ty: ignore
            client_id=ClaimsOption(essential=False, value=None),  # ty: ignore
            may_act=ClaimsOption(essential=False, value=None),  # ty: ignore
            sub=ClaimsOption(essential=True),
            aud=ClaimsOption(essential=True),
            exp=ClaimsOption(essential=True),
            iat=ClaimsOption(essential=True),
            jti=ClaimsOption(essential=True),
            email=ClaimsOption(essential=False, value=None),  # ty: ignore
            grants=ClaimsOption(essential=False, value=None),  # ty: ignore
        ).options
    )


def test_tokenexchangerequest_struct_decoding():
    """Test the TokenExchangeRequest struct decoding from JSON string."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenTypeEnum.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "resource": "https://target-service.com",
        "audience": " target1  target2 ",
        "scope": " scope1 scope2 ",
    }

    token_exchanged_request = msgspec.json.decode(json.dumps(payload), type=TokenExchangeRequest)

    # Check the values are the same
    for key, value in payload.items():
        assert getattr(token_exchanged_request, key) == value

    assert token_exchanged_request.audiences == ["target1", "target2"]
    assert token_exchanged_request.scopes == ["scope1", "scope2"]


def test_tokenexchangerequest_struct_decoding_with_only_required_fields():
    """Test the TokenExchangeRequest struct with only required fields."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenTypeEnum.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
    }

    token_exchanged_request = msgspec.json.decode(json.dumps(payload), type=TokenExchangeRequest)

    assert token_exchanged_request.resource is None
    assert token_exchanged_request.audience is None
    assert token_exchanged_request.scope is None
    assert token_exchanged_request.requested_token_type is None
    assert token_exchanged_request.actor_token is None
    assert token_exchanged_request.actor_token_type is None
    assert token_exchanged_request.scope is None
    assert token_exchanged_request.audiences == []
    assert token_exchanged_request.scopes == []


@pytest.mark.parametrize(
    ("scope", "match"),
    [
        ("action:foo action:bar", "Only one action scope is allowed per token exchange request"),
        ("action:foo scope1", "Actions cannot be combined with other scopes"),
    ],
)
def test_tokenexchangerequest_struct_scope_invalid_actions(scope, match):
    """Test the TokenExchangeRequest struct action validation rules (invalid cases)."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenTypeEnum.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "scope": scope,
    }

    with pytest.raises(msgspec.ValidationError, match=match):
        msgspec.json.decode(json.dumps(payload), type=TokenExchangeRequest)


def test_tokenexchangerequest_struct_scope_valid_actions():
    """Test the TokenExchangeRequest struct action validation rules (valid case)."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenTypeEnum.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "scope": "action:foo",
    }

    token_exchange_request = msgspec.json.decode(json.dumps(payload), type=TokenExchangeRequest)
    assert token_exchange_request.scopes == ["action:foo"]


def test_tokenexchangerequest_struct_ensure_actor_token_requirements():
    """Test the TokenExchangeRequest struct ensures actor_token requirements."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenTypeEnum.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "resource": "https://target-service.com",
        "scope": "action:foo",
        "audience": " target1  target2 ",
        "actor_token": "foo",
    }

    with pytest.raises(
        msgspec.ValidationError,
        match="An actor_token_type is required when actor_token is provided",
    ):
        msgspec.json.decode(json.dumps(payload), type=TokenExchangeRequest)

    # Now add a token type
    payload.update({"actor_token_type": AllowedActorTokenTypeEnum.ACCESS_TOKEN})
    token_exchanged_request = msgspec.json.decode(json.dumps(payload), type=TokenExchangeRequest)
    assert token_exchanged_request.actor_token == "foo"
    assert token_exchanged_request.actor_token_type == AllowedActorTokenTypeEnum.ACCESS_TOKEN


def test_tokenexchangerequest_struct_ensure_actor_token_type_requirements():
    """Test the TokenExchangeRequest struct ensures actor_token_type requirements."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenTypeEnum.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "resource": "https://target-service.com",
        "scope": "action:foo",
        "audience": " target1  target2 ",
        "actor_token_type": TokenTypeEnum.ACCESS_TOKEN,
    }

    with pytest.raises(
        msgspec.ValidationError,
        match="An actor_token is required when actor_token_type is provided",
    ):
        msgspec.json.decode(json.dumps(payload), type=TokenExchangeRequest)

    # Now add a token
    payload.update({"actor_token": "foo"})
    token_exchanged_request = msgspec.json.decode(json.dumps(payload), type=TokenExchangeRequest)
    assert token_exchanged_request.actor_token == "foo"
    assert token_exchanged_request.actor_token_type == AllowedActorTokenTypeEnum.ACCESS_TOKEN


@pytest.mark.parametrize(
    ("subject_token_type", "requested_token_type", "actor_token_type"),
    [
        (TokenTypeEnum.REFRESH_TOKEN, None, None),
        (TokenTypeEnum.ID_TOKEN, None, None),
        (TokenTypeEnum.SAML1, None, None),
        (TokenTypeEnum.SAML2, None, None),
        (TokenTypeEnum.ACCESS_TOKEN, TokenTypeEnum.REFRESH_TOKEN, None),
        (TokenTypeEnum.ACCESS_TOKEN, TokenTypeEnum.ID_TOKEN, None),
        (TokenTypeEnum.ACCESS_TOKEN, TokenTypeEnum.SAML1, None),
        (TokenTypeEnum.ACCESS_TOKEN, TokenTypeEnum.SAML2, None),
        (TokenTypeEnum.ACCESS_TOKEN, None, TokenTypeEnum.REFRESH_TOKEN),
        (TokenTypeEnum.ACCESS_TOKEN, None, TokenTypeEnum.ID_TOKEN),
        (TokenTypeEnum.ACCESS_TOKEN, None, TokenTypeEnum.SAML1),
        (TokenTypeEnum.ACCESS_TOKEN, None, TokenTypeEnum.SAML2),
    ],
)
def test_tokenexchangerequest_struct_not_allowed_token_types(
    subject_token_type, requested_token_type, actor_token_type
):
    """Test the TokenExchangeRequest struct not allowed token types."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": subject_token_type,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "resource": "https://target-service.com",
        "scope": "action:foo",
        "audience": " target1  target2 ",
        "requested_token_type": requested_token_type,
        "actor_token": "foo",
        "actor_token_type": actor_token_type,
    }

    with pytest.raises(
        msgspec.ValidationError,
        match="Invalid enum value 'urn:ietf:params:oauth:token-type:",
    ):
        msgspec.json.decode(json.dumps(payload), type=TokenExchangeRequest)


def test_tokenexchangeresponse_struct_decoding_with_only_required_fields():
    """Test the TokenExchangeResponse struct decoding withn only required fields."""
    payload = {
        "access_token": "fake_access",
        "issued_token_type": TokenTypeEnum.ACCESS_TOKEN,
        "token_type": TokenExchangeResponseTokenType.BEARER,
    }

    token_exchanged_response = msgspec.json.decode(json.dumps(payload), type=TokenExchangeResponse)
    assert token_exchanged_response.access_token == "fake_access"
    assert token_exchanged_response.issued_token_type == TokenTypeEnum.ACCESS_TOKEN
    assert token_exchanged_response.token_type == TokenExchangeResponseTokenType.BEARER
    assert token_exchanged_response.expires_in == 3600
    assert token_exchanged_response.scope is None
    assert token_exchanged_response.refresh_token is None


def test_tokenexchangeresponse_struct_decoding_with_optional_fields():
    """Test the TokenExchangeResponse struct decoding with optional fields."""
    payload = {
        "access_token": "fake_access",
        "issued_token_type": TokenTypeEnum.ACCESS_TOKEN,
        "token_type": TokenExchangeResponseTokenType.BEARER,
        "expires_in": 1800,
        "scope": "foo",
        "refresh_token": "fake_refresh",
    }

    token_exchanged_response = msgspec.json.decode(json.dumps(payload), type=TokenExchangeResponse)
    assert token_exchanged_response.access_token == "fake_access"
    assert token_exchanged_response.issued_token_type == TokenTypeEnum.ACCESS_TOKEN
    assert token_exchanged_response.token_type == TokenExchangeResponseTokenType.BEARER
    assert token_exchanged_response.expires_in == 1800
    assert token_exchanged_response.scope == "foo"
    assert token_exchanged_response.refresh_token == "fake_refresh"


def test_tokenexchangeresponse_struct_expires_in(settings):
    """Test the TokenExchangeResponse struct expiracy."""
    payload = {
        "access_token": "fake_access",
        "issued_token_type": TokenTypeEnum.ACCESS_TOKEN,
        "token_type": TokenExchangeResponseTokenType.BEARER,
        "expires_in": settings.TOKEN_EXCHANGE_MAX_EXPIRES_IN + 1,
    }

    with pytest.raises(
        msgspec.ValidationError,
        match=r"Expected `int` <= 86400 - at `\$\.expires_in`",
    ):
        msgspec.json.decode(json.dumps(payload), type=TokenExchangeResponse)


def test_tokenrevocationrequest_struct_decoding():
    """Test the TokenRevocationRequest struct decoding."""
    token = secrets.token_urlsafe(32)
    payload = {
        "token": token,
    }

    token_revocation_request = msgspec.json.decode(json.dumps(payload), type=TokenRevocationRequest)
    assert token_revocation_request.token == token
    assert token_revocation_request.token_type_hint is None

    # With a token_type_hint
    payload.update({"token_type_hint": TokenTypeEnum.ACCESS_TOKEN})
    token_revocation_request = msgspec.json.decode(json.dumps(payload), type=TokenRevocationRequest)
    assert token_revocation_request.token == token
    assert token_revocation_request.token_type_hint == TokenTypeEnum.ACCESS_TOKEN


@pytest.mark.parametrize(
    "token_type_hint",
    [
        TokenTypeEnum.REFRESH_TOKEN,
        TokenTypeEnum.ID_TOKEN,
        TokenTypeEnum.SAML1,
        TokenTypeEnum.SAML2,
    ],
)
def test_tokenrevocationrequest_struct_allowed_token_type_hint(token_type_hint):
    """Test the TokenRevocationRequest struct allowed token type hint."""
    payload = {
        "token": secrets.token_urlsafe(32),
        "token_type_hint": token_type_hint,
    }

    with pytest.raises(
        msgspec.ValidationError,
        match="Invalid enum value 'urn:ietf:params:oauth:token-type:",
    ):
        msgspec.json.decode(json.dumps(payload), type=TokenRevocationRequest)


@pytest.mark.parametrize(
    "token",
    [
        "",
        " " * 32,  # Only spaces
        " " * 14 + "fake" + " " * 14,  # 32 characters but padded with spaces
    ],
)
def test_tokenrevocationrequest_struct_invalid_token(token):
    """Test the TokenRevocationRequest struct with an invalid token."""
    payload = {
        "token": token,
    }

    with pytest.raises(
        msgspec.ValidationError, match=r"Expected `str` matching regex .* at `\$.token`"
    ):
        msgspec.json.decode(json.dumps(payload), type=TokenRevocationRequest)


def test_tokenrevocationrequest_struct_valid_access_token():
    """Test the TokenRevocationRequest struct with a valid access token."""
    payload = {
        "token": "f4k3" * 8,  # 32 characters
    }

    token_revokation_request = msgspec.json.decode(json.dumps(payload), type=TokenRevocationRequest)
    assert token_revokation_request.token == "f4k3" * 8
    assert token_revokation_request.token_type_hint is None
