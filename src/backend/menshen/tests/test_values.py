"""Menshen: tests for custom django-configurations values."""

import pytest

from menshen.values import SecretFileValue


def test_secret_file_value_default(monkeypatch):
    """Without environment variables, the default value is used."""
    monkeypatch.delenv("DJANGO_TEST_SECRET", raising=False)
    monkeypatch.delenv("DJANGO_TEST_SECRET_FILE", raising=False)
    assert SecretFileValue("default").setup("TEST_SECRET") == "default"


def test_secret_file_value_from_environment(monkeypatch):
    """The value can be read from the environment variable."""
    monkeypatch.setenv("DJANGO_TEST_SECRET", "from-env")
    assert SecretFileValue("default").setup("TEST_SECRET") == "from-env"


def test_secret_file_value_from_file(monkeypatch, tmp_path):
    """The file variant has priority and its trailing newline is stripped."""
    secret = tmp_path / "secret"
    secret.write_text("from-file\n")
    monkeypatch.setenv("DJANGO_TEST_SECRET", "from-env")
    monkeypatch.setenv("DJANGO_TEST_SECRET_FILE", str(secret))
    assert SecretFileValue("default").setup("TEST_SECRET") == "from-file"


def test_secret_file_value_custom_file_suffix(monkeypatch, tmp_path):
    """The file environment variable suffix can be customized."""
    secret = tmp_path / "secret"
    secret.write_text("from-file")
    monkeypatch.setenv("TEST_SECRET_PATH", str(secret))
    value = SecretFileValue("default", environ_prefix=None, file_suffix="PATH")
    assert value.setup("TEST_SECRET") == "from-file"


def test_secret_file_value_missing_file(monkeypatch, tmp_path):
    """A missing file should raise."""
    monkeypatch.setenv("DJANGO_TEST_SECRET_FILE", str(tmp_path / "missing"))
    with pytest.raises(ValueError, match="does not exist"):
        SecretFileValue("default").setup("TEST_SECRET")


def test_secret_file_value_unreadable_file(monkeypatch, tmp_path):
    """An unreadable file should raise."""
    monkeypatch.setenv("DJANGO_TEST_SECRET_FILE", str(tmp_path))
    with pytest.raises(ValueError, match="cannot be read"):
        SecretFileValue("default").setup("TEST_SECRET")


def test_secret_file_value_required(monkeypatch):
    """A required value should raise when not set."""
    monkeypatch.delenv("DJANGO_TEST_SECRET", raising=False)
    monkeypatch.delenv("DJANGO_TEST_SECRET_FILE", raising=False)
    with pytest.raises(ValueError, match="is required to be set"):
        SecretFileValue(environ_required=True).setup("TEST_SECRET")
