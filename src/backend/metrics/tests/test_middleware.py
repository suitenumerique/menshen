"""Menshen: tests for the Prometheus metrics middlewares."""

import pytest
from django.test import RequestFactory


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Bearer",
        "Bearer wrong",
        "bearer secret",
        "Basic secret",
        "Bearer secret ",
        "Bearer sécret",
    ],
)
@pytest.mark.parametrize("path", ["/metrics", "/metrics/"])
def test_prometheus_auth_middleware_refused(
    prometheus_auth_middleware, settings, authorization, path
):
    """A call to the metrics endpoint without the key is refused."""
    settings.PROMETHEUS_API_KEY = "secret"
    headers = {"Authorization": authorization} if authorization is not None else {}
    response = prometheus_auth_middleware(RequestFactory().get(path, headers=headers))
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == 'Bearer realm="metrics"'


@pytest.mark.parametrize("api_key", [None, ""])
def test_prometheus_auth_middleware_no_key(prometheus_auth_middleware, settings, api_key):
    """Without a key configured nothing is served, whatever is presented."""
    settings.PROMETHEUS_API_KEY = api_key
    response = prometheus_auth_middleware(
        RequestFactory().get("/metrics", headers={"Authorization": f"Bearer {api_key}"})
    )
    assert response.status_code == 401


def test_prometheus_auth_middleware_allowed(prometheus_auth_middleware, settings):
    """A call presenting the key goes through."""
    settings.PROMETHEUS_API_KEY = "secret"
    response = prometheus_auth_middleware(
        RequestFactory().get("/metrics", headers={"Authorization": "Bearer secret"})
    )
    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/", "/auth/", "/metricsfoo", "/foo/metrics"])
def test_prometheus_auth_middleware_other_paths(prometheus_auth_middleware, settings, path):
    """Other paths are left alone."""
    settings.PROMETHEUS_API_KEY = "secret"
    assert prometheus_auth_middleware(RequestFactory().get(path)).status_code == 200
