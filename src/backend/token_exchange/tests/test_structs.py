"""Menshen: struct tests for the token_exchange application."""

from uuid import UUID

import pytest
from joserfc.jwt import ClaimsOption, JWTClaimsRegistry

from token_exchange.structs import (
    BaseStruct,
    MenshenJWTClaims,
    TokenExchangeJWTActClaim,
    TokenExchangeJWTClaims,
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
