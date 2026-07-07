"""Test the Menshen client dataclasses."""

import pytest

from menshen_client import MenshenConfiguration


@pytest.mark.parametrize("scheme", ["http", "https"])
@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (
            "menshen.example.org",
            (
                "menshen.example.org/auth/token/exchange/",
                "menshen.example.org/auth/token/introspect/",
                "menshen.example.org/auth/token/revoke/",
            ),
        ),
        (
            "menshen.example.org/",
            (
                "menshen.example.org/auth/token/exchange/",
                "menshen.example.org/auth/token/introspect/",
                "menshen.example.org/auth/token/revoke/",
            ),
        ),
        (
            "service.lasuite.org/menshen/",
            (
                "service.lasuite.org/menshen/auth/token/exchange/",
                "service.lasuite.org/menshen/auth/token/introspect/",
                "service.lasuite.org/menshen/auth/token/revoke/",
            ),
        ),
    ],
)
def test_menshen_configuration_properties(scheme, base_url, expected):
    """Test MenshenConfiguration properties."""
    config = MenshenConfiguration(
        client_id="foo",
        client_secret="bar",
        server_root_url=f"{scheme}://{base_url}",
    )
    assert config.token_url == f"{scheme}://{expected[0]}"
    assert config.introspection_url == f"{scheme}://{expected[1]}"
    assert config.revocation_url == f"{scheme}://{expected[2]}"


def test_menshen_configuration_properties_trailing_slashes():
    """Test MenshenConfiguration properties URLs with missing trailing slashes."""
    config = MenshenConfiguration(
        client_id="foo",
        client_secret="bar",
        server_root_url="https://menshen.example.org/",
        token_endpoint="/auth/token/exchange",
    )
    assert config.token_url == "https://menshen.example.org/auth/token/exchange/"
