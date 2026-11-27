"""Menshen: test fixtures for the Prometheus metrics."""

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import asdict

import pytest
from django.http import HttpResponse

from metrics.middleware import PrometheusAuthMiddleware
from metrics.tests.utils import ClientRequest


@pytest.fixture
def prometheus_auth_middleware():
    """Return the middleware wrapping a view that always answers."""
    return PrometheusAuthMiddleware(lambda request: HttpResponse("OK"))


# Run in a process of its own: prometheus_client decides whether the numbers are
# shared between processes when it is first imported, and the settings only
# enable that when the metrics are. The requests are given as a JSON list of
# ClientRequest; the statuses are printed, then the body of the last response as
# JSON.
SCRIPT = textwrap.dedent(
    """
    import json
    import sys

    import configurations

    configurations.setup()

    from django.test import Client
    from django.test.utils import setup_test_environment

    setup_test_environment()
    client = Client()
    statuses = []
    for request in json.loads(sys.argv[1]):
        token = request["token"]
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = getattr(client, request["method"].lower())(
            request["path"], headers=headers
        )
        statuses.append(response.status_code)
    sys.stdout.write(json.dumps({"statuses": statuses, "content": response.content.decode()}))
    """
)


@pytest.fixture
def request_in_subprocess(tmp_path):
    """
    Send the requests sequentially from a new subprocess.

    Every subprocess shares one metrics directory.
    """
    env = {
        **os.environ,
        "DJANGO_CONFIGURATION": "Test",
        "DJANGO_SETTINGS_MODULE": "menshen.settings",
        "PROMETHEUS_METRICS_ENABLED": "True",
        "PROMETHEUS_API_KEY": "secret",
        "PROMETHEUS_MULTIPROC_DIR": str(tmp_path / "prometheus"),
    }

    def request_in_subprocess(*requests: ClientRequest) -> tuple[list[int], str]:
        payload = json.dumps([asdict(request) for request in requests])
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", SCRIPT, payload],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        output = json.loads(result.stdout.strip().splitlines()[-1])
        return output["statuses"], output["content"]

    return request_in_subprocess
