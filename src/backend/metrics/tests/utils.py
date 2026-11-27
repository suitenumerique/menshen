"""Menshen: helpers for the Prometheus metrics tests."""

from dataclasses import dataclass

from metrics.urls import METRICS_PATH


@dataclass(frozen=True)
class ClientRequest:
    """A request sent by the test client in a subprocess."""

    method: str = "GET"
    path: str = METRICS_PATH
    token: str | None = None
