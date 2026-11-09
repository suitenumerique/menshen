"""Menshen: tests for token exchange related settings."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from menshen.settings import Test


@pytest.mark.parametrize(("length", "min_length"), [(43, 43), (64, 43), (32, 32)])
def test_settings_opaque_token_lengths(monkeypatch, length, min_length):
    """Generated opaque tokens length should be greater than or equal to the min length."""
    monkeypatch.setattr(Test, "TOKEN_EXCHANGE_OPAQUE_TOKEN_LENGTH", length)
    monkeypatch.setattr(Test, "TOKEN_EXCHANGE_OPAQUE_TOKEN_MIN_LENGTH", min_length)
    Test.post_setup()


def test_settings_opaque_token_length_lower_than_min_length(monkeypatch):
    """Generated opaque tokens should not be shorter than the min length."""
    monkeypatch.setattr(Test, "TOKEN_EXCHANGE_OPAQUE_TOKEN_LENGTH", 42)
    monkeypatch.setattr(Test, "TOKEN_EXCHANGE_OPAQUE_TOKEN_MIN_LENGTH", 43)
    with pytest.raises(
        ImproperlyConfigured,
        match=(
            r"TOKEN_EXCHANGE_OPAQUE_TOKEN_LENGTH \(42\) should be greater than or equal to "
            r"TOKEN_EXCHANGE_OPAQUE_TOKEN_MIN_LENGTH \(43\)"
        ),
    ):
        Test.post_setup()
