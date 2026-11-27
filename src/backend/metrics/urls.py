"""Menshen: Prometheus metrics urls."""

from django.urls import path

from .views import metrics_view

# Where the Prometheus metrics are served when PROMETHEUS_METRICS_ENABLED is set
METRICS_PATH = "/metrics"

urlpatterns = [
    path(METRICS_PATH.lstrip("/"), metrics_view, name="prometheus-metrics"),
]
