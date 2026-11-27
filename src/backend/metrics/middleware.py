"""Menshen: Prometheus metrics middlewares."""

from secrets import compare_digest

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .urls import METRICS_PATH


class PrometheusAuthMiddleware(MiddlewareMixin):
    """
    Require PROMETHEUS_API_KEY as a bearer token on the metrics endpoint.

    Installed first, and only when PROMETHEUS_METRICS_ENABLED is set. It fails
    closed: with no key configured nothing is served, whatever is presented.
    """

    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        """Refuse a call to the metrics endpoint that does not present the key."""
        if request.path.rstrip("/") != METRICS_PATH:
            return None

        api_key = settings.PROMETHEUS_API_KEY
        authorization = request.headers.get("Authorization") or ""
        # Compared as bytes: `compare_digest` refuses non-ASCII strings, and
        # what a caller sends in a header is not ours to trust.
        if not api_key or not compare_digest(authorization.encode(), f"Bearer {api_key}".encode()):
            response = HttpResponse("Unauthorized", status=401)
            response["WWW-Authenticate"] = 'Bearer realm="metrics"'
            return response

        return None
