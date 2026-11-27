"""Menshen: test fixtures shared by every backend application."""

import copy

import pytest
import structlog

from menshen.settings import Test


@pytest.fixture(autouse=True)
def clear_structlog_contextvars():
    """Prevent structlog context variables from leaking between tests."""
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


@pytest.fixture
def metrics_settings(monkeypatch, tmp_path):
    """
    Enable the metrics on copies of the settings edited in place, so that
    nothing leaks into the other tests.
    """
    for name in ("INSTALLED_APPS", "MIDDLEWARE", "SECURE_REDIRECT_EXEMPT", "DATABASES"):
        monkeypatch.setattr(Test, name, copy.deepcopy(getattr(Test, name)))
    monkeypatch.setitem(Test.DATABASES["default"], "ENGINE", "django.db.backends.postgresql")
    monkeypatch.setattr(Test, "PROMETHEUS_METRICS_ENABLED", True)
    monkeypatch.setattr(Test, "PROMETHEUS_API_KEY", "secret")
    monkeypatch.setattr(Test, "PROMETHEUS_DB_METRICS_ENABLED", True)
    monkeypatch.setattr(Test, "PROMETHEUS_METRICS_SSL_REDIRECT_EXEMPT", False)
    monkeypatch.setattr(Test, "PROMETHEUS_MULTIPROC_DIR", str(tmp_path / "prometheus"))
    # Recorded so that the value set by the settings is removed afterwards
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "unset")
    return Test
