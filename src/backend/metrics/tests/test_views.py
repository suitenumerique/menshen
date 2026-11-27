"""Menshen: tests for the Prometheus metrics views."""

import re
import socket

from prometheus_client.core import CounterMetricFamily

from metrics.tests.utils import ClientRequest
from metrics.views import HOSTNAME_LABEL, HostnameLabelled


def _sample(content: str, name: str, **labels: str) -> float:
    """Return the value of the sample with the given name and labels."""
    for line in content.splitlines():
        match = re.fullmatch(rf"{name}\{{(?P<labels>.*)\}} (?P<value>\S+)", line)
        if match and all(f'{key}="{value}"' in match["labels"] for key, value in labels.items()):
            return float(match["value"])
    raise AssertionError(f"no {name} sample with {labels} in:\n{content}")


def test_metrics_endpoint_requires_key(request_in_subprocess):
    """The endpoint is routed and only answers to a call presenting the key."""
    statuses, _ = request_in_subprocess(
        ClientRequest(), ClientRequest(token="wrong"), ClientRequest(token="secret")
    )
    assert statuses == [401, 401, 200]


def test_metrics_endpoint_safe_methods_only(request_in_subprocess):
    """Only GET and HEAD are answered."""
    statuses, _ = request_in_subprocess(
        ClientRequest("HEAD", token="secret"), ClientRequest("POST", token="secret")
    )
    assert statuses == [200, 405]


def test_metrics_endpoint_aggregates_processes(request_in_subprocess):
    """The metrics written by every process are added up, and labelled by host."""
    statuses, _ = request_in_subprocess(ClientRequest(path="/unknown/"))
    assert statuses == [404]
    statuses, content = request_in_subprocess(
        ClientRequest(path="/unknown/"), ClientRequest(token="secret")
    )
    assert statuses == [404, 200]

    hostname = socket.gethostname()
    # Two processes, three requests: the scrape is counted too
    assert (
        _sample(
            content,
            "django_http_requests_total_by_method_total",
            method="GET",
            **{HOSTNAME_LABEL: hostname},
        )
        == 3
    )
    # The requests that matched no route
    assert (
        _sample(
            content,
            "django_http_responses_total_by_status_view_method_total",
            status="404",
            view="<unnamed view>",
            method="GET",
        )
        == 2
    )
    # No path leaves the application through a label
    assert "/unknown/" not in content


def test_hostname_labelled():
    """Every sample of the wrapped collector is labelled with the host name."""
    family = CounterMetricFamily("requests", "Requests", labels=["method"])
    family.add_metric(["GET"], 3)

    class Wrapped:
        def collect(self):
            yield family

    (metric,) = HostnameLabelled(Wrapped()).collect()
    assert metric.name == "requests"
    assert metric.type == "counter"
    assert [sample.labels for sample in metric.samples] == [
        {"method": "GET", HOSTNAME_LABEL: socket.gethostname()}
    ]
