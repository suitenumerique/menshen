"""Menshen: schema tests for the token_exchange application."""

import json
import secrets
from uuid import UUID

import pytest
from joserfc.jwt import ClaimsOption, JWTClaimsRegistry
from pydantic import ValidationError

from token_exchange.enums import (
    AllowedActorTokenType,
    AllowedSubjectTokenType,
    TokenExchangeResponseTokenType,
    TokenExchangeTokenTypeHint,
    TokenType,
)
from token_exchange.schemas import (
    IntrospectionRequest,
    IntrospectionResponse,
    MenshenJWTClaims,
    RevocationRequest,
    TokenExchangeJWTActClaim,
    TokenExchangeJWTClaims,
    TokenExchangeRequest,
    TokenExchangeResponse,
    str_to_list,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", []),
        ("foo", ["foo"]),
        ("  foo ", ["foo"]),
        ("foo bar", ["foo", "bar"]),
        ("foo bar bar", ["foo", "bar"]),
        ("  foo   bar  ", ["foo", "bar"]),
        ("  foo   bar  bar", ["foo", "bar"]),
    ],
)
def test_str_to_list(value, expected):
    """Test the str_to_list utility."""
    assert str_to_list(value) == expected


def test_tokenexchangejwtclaims_schema():
    """Test the TokenExchangeJWTClaims schema."""
    # Test with only two fields
    claims = TokenExchangeJWTClaims(
        act=TokenExchangeJWTActClaim(sub="foo"),
        scope=["foo", "bar"],
    )
    assert claims.act is not None
    assert hasattr(claims.act, "sub")
    assert claims.act.sub == "foo"
    assert claims.scope == ["foo", "bar"]


def test_tokenexchangejwtclaims_nested_actor_claim_schema():
    """Test the TokenExchangeJWTClaims schema with a nested actor claim."""
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


def test_menshenjwtclaims_schema_default_factories():
    """Test the MenshenJWTClaims schema default factories."""
    claims = MenshenJWTClaims(sub="foo@bar.com", aud=["foo.com"], exp=12)
    assert claims.iat > 0
    assert isinstance(claims.jti, UUID)


def test_menshenjwtclaims_schema_to_jwt_claims_registry():
    """Test the MenshenJWTClaims schema to_jwt_claims_registy method."""
    # joserfc does not allow None in ClaimsOption.value, we think it's perfectly legit & thus
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


def test_introspection_response_schema_properties():
    """Test the IntrospectionResponse properties."""
    introspection_response = IntrospectionResponse(active=False, scope="foo  bar ", aud=" one two")
    assert introspection_response.scopes == ["foo", "bar"]
    assert introspection_response.audiences == ["one", "two"]

    # A property should not be dumped
    dump = introspection_response.model_dump()
    assert "scope" in dump
    assert "scopes" not in dump
    assert "aud" in dump
    assert "audiences" not in dump


def test_introspection_response_schema_aud_field_validation():
    """Test the IntrospectionResponse schema aud field pre-validation."""
    # Multiple audiences as a single string should be left untouched
    assert IntrospectionResponse(active=False, aud="foo bar").aud == "foo bar"
    assert IntrospectionResponse(active=False, aud="foo bar ").aud == "foo bar "

    # Multiple audiences string list should be joined as a string
    assert IntrospectionResponse(active=False, aud=["foo", "bar"]).aud == "foo bar"  # ty: ignore
    assert IntrospectionResponse(active=False, aud=["foo", "bar "]).aud == "foo bar "  # ty: ignore

    # Multiple audiences list containing an non-string type should raise an error
    with pytest.raises(ValidationError, match="Input should be a valid string"):
        IntrospectionResponse(active=False, aud=["foo", 1])  # ty: ignore


@pytest.mark.parametrize(
    ("scope", "action"),
    [
        ("foo", None),
        (" action:foo ", "action:foo"),
    ],
)
def test_tokenexchangerequest_schema_properties(scope, action):
    """Test the TokenExchangeRequest schema properties."""
    token_exchange_request = TokenExchangeRequest(
        subject_token="fake",
        subject_token_type=AllowedSubjectTokenType(TokenType.ACCESS_TOKEN),
        grant_type="urn:ietf:params:oauth:grant-type:token-exchange",
        scope=scope,
    )
    assert token_exchange_request.action == action


def test_tokenexchangerequest_schema_decoding():
    """Test the TokenExchangeRequest schema decoding from JSON string."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenType.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "resource": "https://target-service.com",
        "audience": " target1  target2 ",
        "scope": " scope1 scope2 ",
    }

    token_exchange_request = TokenExchangeRequest.model_validate_json(json.dumps(payload))

    # Check the values are the same
    for key, value in payload.items():
        assert getattr(token_exchange_request, key) == value

    assert token_exchange_request.audiences == ["target1", "target2"]
    assert token_exchange_request.scopes == ["scope1", "scope2"]


def test_tokenexchangerequest_schema_decoding_with_only_required_fields():
    """Test the TokenExchangeRequest schema with only required fields."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenType.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
    }

    token_exchange_request = TokenExchangeRequest.model_validate_json(json.dumps(payload))

    assert token_exchange_request.resource is None
    assert token_exchange_request.audience is None
    assert token_exchange_request.scope is None
    assert token_exchange_request.requested_token_type is None
    assert token_exchange_request.actor_token is None
    assert token_exchange_request.actor_token_type is None
    assert token_exchange_request.scope is None
    assert token_exchange_request.audiences == []
    assert token_exchange_request.scopes == []


@pytest.mark.parametrize(
    ("scope", "match"),
    [
        ("action:foo action:bar", "Only one action scope is allowed per token exchange request"),
        ("action:foo scope1", "Actions cannot be combined with other scopes"),
    ],
)
def test_tokenexchangerequest_schema_scope_invalid_actions(scope, match):
    """Test the TokenExchangeRequest schema action validation rules (invalid cases)."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenType.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "scope": scope,
    }

    with pytest.raises(ValidationError, match=match):
        TokenExchangeRequest.model_validate_json(json.dumps(payload))


def test_tokenexchangerequest_schema_scope_valid_actions():
    """Test the TokenExchangeRequest schema action validation rules (valid case)."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenType.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "scope": "action:foo",
    }

    token_exchange_request = TokenExchangeRequest.model_validate_json(json.dumps(payload))
    assert token_exchange_request.scopes == ["action:foo"]


def test_tokenexchangerequest_schema_ensure_actor_token_requirements():
    """Test the TokenExchangeRequest schema ensures actor_token requirements."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenType.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "resource": "https://target-service.com",
        "scope": "action:foo",
        "audience": " target1  target2 ",
        "actor_token": "foo",
    }

    with pytest.raises(
        ValidationError,
        match="An actor_token_type is required when actor_token is provided",
    ):
        TokenExchangeRequest.model_validate_json(json.dumps(payload))

    # Now add a token type
    payload.update({"actor_token_type": AllowedActorTokenType.ACCESS_TOKEN})
    token_exchange_request = TokenExchangeRequest.model_validate_json(json.dumps(payload))
    assert token_exchange_request.actor_token == "foo"
    assert token_exchange_request.actor_token_type == AllowedActorTokenType.ACCESS_TOKEN


def test_tokenexchangerequest_schema_ensure_actor_token_type_requirements():
    """Test the TokenExchangeRequest schema ensures actor_token_type requirements."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": TokenType.ACCESS_TOKEN,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "resource": "https://target-service.com",
        "scope": "action:foo",
        "audience": " target1  target2 ",
        "actor_token_type": TokenType.ACCESS_TOKEN,
    }

    with pytest.raises(
        ValidationError,
        match="An actor_token is required when actor_token_type is provided",
    ):
        TokenExchangeRequest.model_validate_json(json.dumps(payload))

    # Now add a token
    payload.update({"actor_token": "foo"})
    token_exchange_request = TokenExchangeRequest.model_validate_json(json.dumps(payload))
    assert token_exchange_request.actor_token == "foo"
    assert token_exchange_request.actor_token_type == AllowedActorTokenType.ACCESS_TOKEN


@pytest.mark.parametrize(
    ("subject_token_type", "requested_token_type", "actor_token", "actor_token_type"),
    [
        (TokenType.REFRESH_TOKEN, None, None, None),
        (TokenType.ID_TOKEN, None, None, None),
        (TokenType.SAML1, None, None, None),
        (TokenType.SAML2, None, None, None),
        (TokenType.ACCESS_TOKEN, TokenType.REFRESH_TOKEN, None, None),
        (TokenType.ACCESS_TOKEN, TokenType.ID_TOKEN, None, None),
        (TokenType.ACCESS_TOKEN, TokenType.SAML1, None, None),
        (TokenType.ACCESS_TOKEN, TokenType.SAML2, None, None),
        (TokenType.ACCESS_TOKEN, None, "foo", TokenType.REFRESH_TOKEN),
        (TokenType.ACCESS_TOKEN, None, "foo", TokenType.ID_TOKEN),
        (TokenType.ACCESS_TOKEN, None, "foo", TokenType.SAML1),
        (TokenType.ACCESS_TOKEN, None, "foo", TokenType.SAML2),
    ],
)
def test_tokenexchangerequest_schema_not_allowed_token_types(
    subject_token_type, requested_token_type, actor_token, actor_token_type
):
    """Test the TokenExchangeRequest schema not allowed token types."""
    payload = {
        "subject_token": "fake",
        "subject_token_type": subject_token_type,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "resource": "https://target-service.com",
        "scope": "action:foo",
        "audience": " target1  target2 ",
        "requested_token_type": requested_token_type,
        "actor_token": actor_token,
        "actor_token_type": actor_token_type,
    }

    with pytest.raises(
        ValidationError,
        match="Input should be 'urn:ietf:params:oauth:token-type:",
    ):
        TokenExchangeRequest.model_validate_json(json.dumps(payload))


def test_tokenexchangeresponse_schema_decoding_with_only_required_fields():
    """Test the TokenExchangeResponse schema decoding withn only required fields."""
    payload = {
        "access_token": "fake_access",
        "issued_token_type": TokenType.ACCESS_TOKEN,
        "token_type": TokenExchangeResponseTokenType.BEARER,
    }

    token_exchange_response = TokenExchangeResponse.model_validate_json(json.dumps(payload))
    assert token_exchange_response.access_token == "fake_access"
    assert token_exchange_response.issued_token_type == TokenType.ACCESS_TOKEN
    assert token_exchange_response.token_type == TokenExchangeResponseTokenType.BEARER
    assert token_exchange_response.expires_in == 3600
    assert token_exchange_response.scope is None
    assert token_exchange_response.refresh_token is None


def test_tokenexchangeresponse_schema_decoding_with_optional_fields():
    """Test the TokenExchangeResponse schema decoding with optional fields."""
    payload = {
        "access_token": "fake_access",
        "issued_token_type": TokenType.ACCESS_TOKEN,
        "token_type": TokenExchangeResponseTokenType.BEARER,
        "expires_in": 1800,
        "scope": "foo",
        "refresh_token": "fake_refresh",
    }

    token_exchange_response = TokenExchangeResponse.model_validate_json(json.dumps(payload))
    assert token_exchange_response.access_token == "fake_access"
    assert token_exchange_response.issued_token_type == TokenType.ACCESS_TOKEN
    assert token_exchange_response.token_type == TokenExchangeResponseTokenType.BEARER
    assert token_exchange_response.expires_in == 1800
    assert token_exchange_response.scope == "foo"
    assert token_exchange_response.refresh_token == "fake_refresh"


def test_tokenexchangeresponse_schema_expires_in(settings):
    """Test the TokenExchangeResponse schema expiracy."""
    payload = {
        "access_token": "fake_access",
        "issued_token_type": TokenType.ACCESS_TOKEN,
        "token_type": TokenExchangeResponseTokenType.BEARER,
        "expires_in": settings.TOKEN_EXCHANGE_MAX_EXPIRES_IN + 1,
    }

    with pytest.raises(
        ValidationError,
        match="Input should be less than or equal to 86400",
    ):
        TokenExchangeResponse.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "token_request_schema",
    [
        IntrospectionRequest,
        RevocationRequest,
    ],
)
@pytest.mark.parametrize(
    "token_type_hint",
    [
        TokenExchangeTokenTypeHint.ACCESS_TOKEN,
        TokenExchangeTokenTypeHint.REFRESH_TOKEN,
        TokenExchangeTokenTypeHint.JWT,
    ],
)
def test_token_request_schema_decoding(token_request_schema, token_type_hint):
    """Test IntrospectionRequest & RevocationRequest schema decoding."""
    token = secrets.token_urlsafe(32)
    payload = {
        "token": token,
    }

    token_request = token_request_schema.model_validate_json(json.dumps(payload))
    assert token_request.token == token
    assert token_request.token_type_hint is None

    # With a token_type_hint
    payload.update({"token_type_hint": token_type_hint})
    token_request = token_request_schema.model_validate_json(json.dumps(payload))
    assert token_request.token == token
    assert token_request.token_type_hint == token_type_hint


@pytest.mark.parametrize(
    "token_type_hint",
    ["id_token", "saml1", "saml2", "fake_type"],
)
@pytest.mark.parametrize(
    "token_request_schema",
    [
        IntrospectionRequest,
        RevocationRequest,
    ],
)
def test_token_request_schema_with_invalid_token_type_hint(token_type_hint, token_request_schema):
    """Test ExchangedToken*Request schemas with invalid token type hint."""
    payload = {
        "token": secrets.token_urlsafe(32),
        "token_type_hint": token_type_hint,
    }

    token_request = token_request_schema.model_validate_json(json.dumps(payload))
    assert token_request.token_type_hint is None


@pytest.mark.parametrize(
    "token",
    [
        "",
        " " * 32,  # Only spaces
        " " * 14 + "fake" + " " * 14,  # 32 characters but padded with spaces
    ],
)
@pytest.mark.parametrize(
    "token_request_schema",
    [
        IntrospectionRequest,
        RevocationRequest,
    ],
)
def test_token_request_schema_invalid_token(token, token_request_schema):
    """Test ExchangedToken*Request schemas with an invalid token."""
    payload = {
        "token": token,
    }

    with pytest.raises(
        ValidationError, match=r"String should match pattern '\^\\s\*\\S\{32\,\}\\s\*\$'"
    ):
        token_request_schema.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "token_request_schema",
    [
        IntrospectionRequest,
        RevocationRequest,
    ],
)
def test_token_request_schema_valid_access_token(token_request_schema):
    """Test ExchangedToken*Request schemas with a valid access token."""
    payload = {
        "token": "f4k3" * 8,  # 32 characters
    }

    token_request = token_request_schema.model_validate_json(json.dumps(payload))
    assert token_request.token == "f4k3" * 8
    assert token_request.token_type_hint is None
