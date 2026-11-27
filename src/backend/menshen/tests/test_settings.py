"""Menshen: tests for the project settings."""

import os
import stat
from unittest import mock

import pytest
from django.core.exceptions import ImproperlyConfigured

AUTH_MIDDLEWARE = "metrics.middleware.PrometheusAuthMiddleware"
BEFORE_MIDDLEWARE = "django_prometheus.middleware.PrometheusBeforeMiddleware"
AFTER_MIDDLEWARE = "django_prometheus.middleware.PrometheusAfterMiddleware"


def test_settings_prometheus_disabled_by_default(client, settings):
    """Nothing is installed and /metrics is not routed unless enabled."""
    assert settings.PROMETHEUS_METRICS_ENABLED is False
    assert "django_prometheus" not in settings.INSTALLED_APPS
    assert AUTH_MIDDLEWARE not in settings.MIDDLEWARE
    assert BEFORE_MIDDLEWARE not in settings.MIDDLEWARE
    assert AFTER_MIDDLEWARE not in settings.MIDDLEWARE
    assert client.get("/metrics").status_code == 404


def test_settings_prometheus_post_setup(metrics_settings):
    """post_setup wires the metrics only when they are enabled."""
    with mock.patch.object(metrics_settings, "setup_prometheus_metrics") as setup:
        metrics_settings.post_setup()
    setup.assert_called_once_with()

    metrics_settings.PROMETHEUS_METRICS_ENABLED = False
    with mock.patch.object(metrics_settings, "setup_prometheus_metrics") as setup:
        metrics_settings.post_setup()
    setup.assert_not_called()


@pytest.mark.parametrize("api_key", [None, ""])
def test_settings_prometheus_requires_api_key(metrics_settings, api_key):
    """The application refuses to start with the metrics enabled and no key."""
    metrics_settings.PROMETHEUS_API_KEY = api_key
    with pytest.raises(
        ImproperlyConfigured,
        match="PROMETHEUS_METRICS_ENABLED requires PROMETHEUS_API_KEY to be set.",
    ):
        metrics_settings.setup_prometheus_metrics()


def test_settings_prometheus_setup(metrics_settings, tmp_path):
    """The application, middlewares, database engine and directory are wired."""
    metrics_settings.setup_prometheus_metrics()
    # Idempotent
    metrics_settings.setup_prometheus_metrics()

    assert metrics_settings.INSTALLED_APPS.count("django_prometheus") == 1
    middleware = metrics_settings.MIDDLEWARE
    assert middleware[:2] == [AUTH_MIDDLEWARE, BEFORE_MIDDLEWARE]
    assert middleware[-1] == AFTER_MIDDLEWARE
    assert middleware.count(AUTH_MIDDLEWARE) == 1
    assert middleware.count(AFTER_MIDDLEWARE) == 1
    assert (
        metrics_settings.DATABASES["default"]["ENGINE"]
        == "django_prometheus.db.backends.postgresql"
    )
    assert metrics_settings.SECURE_REDIRECT_EXEMPT == []

    multiproc_dir = str(tmp_path / "prometheus")
    assert os.environ["PROMETHEUS_MULTIPROC_DIR"] == multiproc_dir
    assert stat.S_IMODE(os.stat(multiproc_dir).st_mode) == 0o700


def test_settings_prometheus_db_metrics_disabled(metrics_settings):
    """The database engine is left alone when the SQL metrics are disabled."""
    metrics_settings.PROMETHEUS_DB_METRICS_ENABLED = False
    metrics_settings.setup_prometheus_metrics()
    assert metrics_settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"


def test_settings_prometheus_other_db_engine(metrics_settings):
    """Only the postgresql engine is swapped for its instrumented subclass."""
    metrics_settings.DATABASES["default"]["ENGINE"] = "django.db.backends.sqlite3"
    metrics_settings.setup_prometheus_metrics()
    assert metrics_settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"


def test_settings_prometheus_ssl_redirect_exempt(metrics_settings):
    """The metrics path is taken out of the redirect to https on demand only."""
    metrics_settings.PROMETHEUS_METRICS_SSL_REDIRECT_EXEMPT = True
    metrics_settings.setup_prometheus_metrics()
    metrics_settings.setup_prometheus_metrics()
    assert metrics_settings.SECURE_REDIRECT_EXEMPT == ["^metrics$"]


def test_settings_prometheus_default_multiproc_dir(metrics_settings, monkeypatch, tmp_path):
    """The directory defaults to one of the temporary directory named after the user."""
    metrics_settings.PROMETHEUS_MULTIPROC_DIR = None
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    metrics_settings.setup_prometheus_metrics()

    expected = str(tmp_path / f"menshen-prometheus-{os.getuid()}")
    assert os.environ["PROMETHEUS_MULTIPROC_DIR"] == expected
    assert os.path.isdir(expected)


def test_settings_prometheus_multiproc_dir_symlink(metrics_settings, tmp_path):
    """A symbolic link is refused, even to a directory of the user."""
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    metrics_settings.PROMETHEUS_MULTIPROC_DIR = str(link)
    with pytest.raises(ImproperlyConfigured, match="must be a directory owned by the user"):
        metrics_settings.setup_prometheus_metrics()


def test_settings_prometheus_multiproc_dir_foreign_owner(metrics_settings, monkeypatch):
    """A directory owned by another user is refused."""
    uid = os.getuid()
    monkeypatch.setattr("os.getuid", lambda: uid + 1)
    with pytest.raises(ImproperlyConfigured, match="must be a directory owned by the user"):
        metrics_settings.setup_prometheus_metrics()


def test_settings_prometheus_multiproc_dir_cannot_be_created(metrics_settings, tmp_path):
    """A directory that cannot be created is reported."""
    blocker = tmp_path / "file"
    blocker.write_text("")
    metrics_settings.PROMETHEUS_MULTIPROC_DIR = str(blocker / "prometheus")
    with pytest.raises(ImproperlyConfigured, match="cannot be created"):
        metrics_settings.setup_prometheus_metrics()
