"""
Menshen: Prometheus metrics views.

Only imported when PROMETHEUS_METRICS_ENABLED is set, and protected by
`metrics.middleware.PrometheusAuthMiddleware` (see docs/metrics.md).
"""

import socket
from collections.abc import Iterable

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_safe
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from prometheus_client.core import Metric
from prometheus_client.multiprocess import MultiProcessCollector
from prometheus_client.registry import Collector

HOSTNAME_LABEL = "hostname"


class WorkerProcessesCollector(Collector):
    """
    The metrics of every worker process of this host.

    uvicorn runs several workers and the scrape is answered by one of them: the
    multiprocess collector reads what they all wrote to PROMETHEUS_MULTIPROC_DIR
    and adds it up, instead of reporting the numbers of that worker alone.
    """

    def collect(self) -> Iterable[Metric]:
        """Yield the aggregated metrics."""
        # A registry of its own: the collector registers itself in the one it is given.
        yield from MultiProcessCollector(CollectorRegistry()).collect()


class HostnameLabelled(Collector):
    """
    The metrics of another collector, labelled with the name of this host.

    The label is for a scraper that goes through a load balancer (an ingress in
    front of several replicas): each scrape is then answered by a different
    replica, and without it their counters would land in the same series.
    """

    def __init__(self, collector: Collector) -> None:
        """Wrap the given collector."""
        self.collector = collector
        self.hostname = socket.gethostname()

    def collect(self) -> Iterable[Metric]:
        """Yield the metrics with the hostname added to every sample."""
        for metric in self.collector.collect():
            labelled = Metric(metric.name, metric.documentation, metric.type)
            for sample in metric.samples:
                labelled.add_sample(
                    sample.name,
                    {**sample.labels, HOSTNAME_LABEL: self.hostname},
                    sample.value,
                    sample.timestamp,
                    sample.exemplar,
                )
            yield labelled


@require_safe
def metrics_view(request: HttpRequest) -> HttpResponse:
    """Serve the metrics in the Prometheus text format."""
    registry = CollectorRegistry()
    registry.register(HostnameLabelled(WorkerProcessesCollector()))
    return HttpResponse(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)
